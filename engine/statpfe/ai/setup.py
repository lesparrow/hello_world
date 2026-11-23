"""Assistants d'installation : Claude Code (installation, connexion) et IA locale (Ollama, modèles).

Chaque étape qui télécharge quelque chose depuis Internet n'est lancée qu'après une
confirmation explicite (`confirm: true`), et la commande exacte est affichée avant.
Aucune de ces étapes n'envoie de données d'étude : elles installent un programme, ouvrent
la connexion au compte de l'utilisateur ou téléchargent un modèle.

Les étapes longues tournent dans un fil séparé (comme les rédactions) ; l'interface suit
leur journal par `ai.setup_job` et peut les annuler.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from typing import Any, Callable

from statpfe.ai import settings as ai_settings
from statpfe.errors import ValidationError

# Commandes d'installation officielles de Claude Code (documentation d'Anthropic, novembre 2026).
CLAUDE_INSTALL = {
    "windows": {"display": "irm https://claude.ai/install.ps1 | iex", "shell": "PowerShell",
                "argv": ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                         "[Console]::OutputEncoding = [Text.Encoding]::UTF8; irm https://claude.ai/install.ps1 | iex"]},
    "unix": {"display": "curl -fsSL https://claude.ai/install.sh | bash", "shell": "Terminal",
             "argv": ["bash", "-c", "set -o pipefail; curl -fsSL https://claude.ai/install.sh | bash"]},
}
CLAUDE_DOC = "https://code.claude.com/docs/fr/setup"
OLLAMA_DOWNLOAD = "https://ollama.com/download"
# Liens qu'il est permis d'ouvrir dans le navigateur de l'utilisateur.
LINK_PREFIXES = ("https://claude.ai/", "https://code.claude.com/", "https://ollama.com/", "https://www.anthropic.com/")
LOGIN_URL = re.compile(r"https://claude\.(?:ai|com)/\S+")
LOG_LINES = 200
INSTALL_TIMEOUT = 900
LOGIN_TIMEOUT = 600
PULL_TIMEOUT = 6 * 3600
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\r")


def platform_key() -> str:
    return "windows" if sys.platform == "win32" else "unix"


def claude_install_info() -> dict[str, Any]:
    c = CLAUDE_INSTALL[platform_key()]
    return {"command": c["display"], "shell": c["shell"], "doc": CLAUDE_DOC}


# --------------------------------------------------------------------------- tâches
@dataclass
class SetupJob:
    id: int
    kind: str  # claude_install | claude_login | ollama_pull
    label: str
    status: str = "en_cours"  # en_cours | termine | erreur | annule
    log: list[str] = field(default_factory=list)
    error: str | None = None
    url: str | None = None  # page de connexion (claude_login)
    waiting_code: bool = False
    progress: float | None = None  # 0..1 (ollama_pull)
    detail: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    started: float = field(default_factory=time.monotonic)
    ended: float | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    proc: subprocess.Popen | None = None

    def add(self, line: str) -> None:
        line = ANSI.sub("", line).rstrip()
        if not line:
            return
        with self.lock:
            self.log.append(line[:500])
            del self.log[:-LOG_LINES]

    def finish(self, status: str, error: str | None = None) -> None:
        with self.lock:
            if self.status == "en_cours":
                self.status, self.error = status, error
            if self.ended is None:
                self.ended = time.monotonic()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            end = self.ended or time.monotonic()
            return {"id": self.id, "kind": self.kind, "label": self.label, "status": self.status,
                    "log": list(self.log[-60:]), "error": self.error, "url": self.url,
                    "waiting_code": self.waiting_code, "progress": self.progress, "detail": self.detail,
                    "result": dict(self.result), "elapsed": round(end - self.started, 1)}


class SetupManager:
    def __init__(self) -> None:
        self._jobs: dict[int, SetupJob] = {}
        self._ids = itertools.count(1)

    def running(self) -> SetupJob | None:
        return next((j for j in self._jobs.values() if j.status == "en_cours"), None)

    def get(self, job_id: Any) -> SetupJob:
        job = self._jobs.get(job_id) if isinstance(job_id, int) else None
        if job is None:
            raise ValidationError("Cette étape d'installation n'existe plus.")
        return job

    def _start(self, kind: str, label: str, target: Callable[[SetupJob], None]) -> SetupJob:
        if self.running() is not None:
            raise ValidationError("Une étape d'installation est déjà en cours : attendez-la ou annulez-la.")
        job = SetupJob(next(self._ids), kind, label)
        self._jobs[job.id] = job

        def run() -> None:
            try:
                target(job)
                job.finish("termine")
            except _StepError as exc:
                job.finish("erreur", str(exc))
            except Exception as exc:  # noqa: BLE001 - le fil ne doit jamais faire tomber le moteur
                job.finish("erreur", f"Erreur inattendue pendant l'installation ({exc.__class__.__name__}).")
            finally:
                _kill(job)

        threading.Thread(target=run, name=f"statpfe-setup-{job.id}", daemon=True).start()
        for old in [j for j in self._jobs.values() if j.status != "en_cours"][:-5]:
            self._jobs.pop(old.id, None)
        return job

    def cancel(self, job_id: Any) -> SetupJob:
        job = self.get(job_id)
        if job.status == "en_cours":
            job.cancel.set()
            job.finish("annule")
            _kill(job)
        return job

    def cancel_all(self) -> None:
        for job in list(self._jobs.values()):
            if job.status == "en_cours":
                self.cancel(job.id)

    def send_code(self, job_id: Any, code: Any) -> SetupJob:
        job = self.get(job_id)
        if job.kind != "claude_login" or job.status != "en_cours" or job.proc is None or job.proc.stdin is None:
            raise ValidationError("Aucune connexion à Claude n'attend de code.")
        if not isinstance(code, str) or not code.strip() or len(code) > 2000 or "\n" in code.strip():
            raise ValidationError("Collez le code affiché par la page de connexion de Claude.")
        try:
            job.proc.stdin.write((code.strip() + "\n").encode("utf-8"))
            job.proc.stdin.flush()
        except OSError:
            raise ValidationError("Claude Code n'attend plus de code : relancez la connexion.") from None
        with job.lock:
            job.waiting_code = False
        job.add("Code transmis à Claude Code.")
        return job

    # ------------------------------------------------------------------ Claude Code
    def claude_install(self, confirm: Any) -> SetupJob:
        if confirm is not True:
            raise ValidationError("L'installation de Claude Code télécharge un programme depuis Internet : "
                                  "confirmez-la d'abord.")
        argv = CLAUDE_INSTALL[platform_key()]["argv"]

        def target(job: SetupJob) -> None:
            job.add("> " + CLAUDE_INSTALL[platform_key()]["display"])
            code = _run_process(job, argv, INSTALL_TIMEOUT)
            if job.cancel.is_set():
                return
            if code != 0:
                raise _StepError("L'installation a échoué (code de sortie {}). Vérifiez la connexion à Internet, "
                                 "ou installez Claude Code vous-même avec la commande affichée.".format(code))
            from statpfe.ai import claude_code

            s = ai_settings.load()
            exe = claude_code.executable(s)
            if exe is None:
                raise _StepError("L'installation s'est terminée, mais le programme « claude » reste introuvable. "
                                 "Redémarrez STATPFE ou indiquez son chemin dans les réglages.")
            job.result = {"executable": exe, "version": claude_code.version(s)}
            job.add(f"Claude Code installé : {job.result['version']}")

        return self._start("claude_install", "Installation de Claude Code", target)

    def claude_login(self) -> SetupJob:
        from statpfe.ai import claude_code

        s = ai_settings.load()
        exe = claude_code.executable(s)
        if exe is None:
            raise ValidationError("Installez d'abord Claude Code.")

        def target(job: SetupJob) -> None:
            job.add("> claude auth login")
            code = _run_process(job, [exe, "auth", "login"], LOGIN_TIMEOUT, keep_stdin=True, on_line=_login_line(job))
            if job.cancel.is_set():
                return
            auth = claude_code.auth_status(s)
            job.result = {"auth": auth}
            if code != 0 or not auth.get("logged_in"):
                raise _StepError("La connexion à votre compte Claude n'a pas abouti. Réessayez ; si la page ne "
                                 "s'ouvre pas, ouvrez le lien affiché.")
            job.add("Connecté à votre compte Claude.")

        return self._start("claude_login", "Connexion à votre compte Claude", target)

    # ------------------------------------------------------------------ Ollama
    def ollama_pull(self, model: Any, confirm: Any) -> SetupJob:
        s = ai_settings.load()
        if s.provider != "ollama":
            raise ValidationError("Le téléchargement d'un modèle n'est possible qu'avec Ollama.")
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._\-/]*(:[A-Za-z0-9._\-]+)?", model) \
                or len(model) > 120:
            raise ValidationError("Nom de modèle invalide.")
        if confirm is not True:
            raise ValidationError("Le téléchargement d'un modèle (plusieurs Go) doit être confirmé.")

        def target(job: SetupJob) -> None:
            job.add(f"> ollama pull {model}")
            _pull(job, s, model)

        return self._start("ollama_pull", f"Téléchargement du modèle {model}", target)


class _StepError(Exception):
    pass


def _kill(job: SetupJob) -> None:
    proc = job.proc
    if proc is not None and proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass


def _no_window() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    if sys.platform == "win32":
        # Un PSModulePath hérité de PowerShell 7 empêche Windows PowerShell 5.1 de charger ses
        # modules (Get-FileHash introuvable pendant l'installation, constaté dans le CI) : on
        # donne explicitement les dossiers de modules de Windows PowerShell.
        windir = env.get("SystemRoot") or env.get("windir") or r"C:\Windows"
        program_files = env.get("ProgramFiles") or r"C:\Program Files"
        docs = os.path.join(os.path.expanduser("~"), "Documents", "WindowsPowerShell", "Modules")
        env["PSModulePath"] = os.pathsep.join([
            docs, os.path.join(program_files, "WindowsPowerShell", "Modules"),
            os.path.join(windir, "System32", "WindowsPowerShell", "v1.0", "Modules")])
    return env


def _run_process(job: SetupJob, argv: list[str], timeout: int, keep_stdin: bool = False,
                 on_line: Callable[[str], None] | None = None) -> int:
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE if keep_stdin else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=_child_env(), **_no_window())
    except OSError as exc:
        raise _StepError(f"Impossible de lancer « {argv[0]} » ({exc.__class__.__name__}).") from None
    job.proc = proc
    done = threading.Event()

    def stop_later() -> None:
        if not done.wait(timeout) and proc.poll() is None:
            job.add(f"Délai maximal dépassé ({timeout // 60} min) : étape arrêtée.")
            proc.kill()

    threading.Thread(target=stop_later, daemon=True).start()
    assert proc.stdout is not None
    buf = b""
    while True:
        chunk = proc.stdout.read1(4096) if hasattr(proc.stdout, "read1") else proc.stdout.read(1)
        if not chunk:
            break
        buf += chunk
        # Les invites (« Paste code here if prompted > ») ne finissent pas par un saut de ligne.
        *lines, buf = re.split(rb"\r?\n", buf)
        for raw in lines + ([buf] if buf.rstrip().endswith(b">") else []):
            text = raw.decode("utf-8", "replace")
            job.add(text)
            if on_line:
                on_line(text)
        if buf.rstrip().endswith(b">"):
            buf = b""
    if buf:
        job.add(buf.decode("utf-8", "replace"))
    code = proc.wait()
    done.set()  # arrête le surveillant
    return code


def _login_line(job: SetupJob) -> Callable[[str], None]:
    def on_line(text: str) -> None:
        m = LOGIN_URL.search(text)
        with job.lock:
            if m and job.url is None:
                job.url = m.group(0)
            if "code" in text.lower() and text.rstrip().endswith(">"):
                job.waiting_code = True
    return on_line


def _pull(job: SetupJob, s: ai_settings.AiSettings, model: str) -> None:
    """Téléchargement par l'API locale d'Ollama (/api/pull) : c'est Ollama qui télécharge."""
    from statpfe.ai import client

    url = ai_settings.connect_host(s.base_url) + "/api/pull"
    body = json.dumps({"model": model, "stream": True}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = client._OPENER.open(req, timeout=60)  # noqa: SLF001 - même ouvreur sans mandataire
    except urllib.error.HTTPError as exc:
        detail = exc.read(300).decode("utf-8", "replace")
        raise _StepError(f"Ollama a refusé le téléchargement (HTTP {exc.code}) : {detail}") from None
    except (urllib.error.URLError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise _StepError(f"Ollama ne répond pas ({reason}) : vérifiez qu'il est installé et lancé, puis "
                         "réessayez.") from None
    started = time.monotonic()
    last_status = ""
    with resp:
        for raw in resp:
            if job.cancel.is_set():
                return
            if time.monotonic() - started > PULL_TIMEOUT:
                raise _StepError("Téléchargement trop long : arrêté.")
            try:
                data = json.loads(raw.decode("utf-8"))
            except ValueError:
                continue
            if data.get("error"):
                raise _StepError(f"Ollama a refusé le téléchargement : {str(data['error'])[:200]}")
            status = str(data.get("status") or "")
            total, done = data.get("total"), data.get("completed")
            with job.lock:
                if isinstance(total, (int, float)) and total > 0 and isinstance(done, (int, float)):
                    job.progress = max(0.0, min(1.0, done / total))
                    job.detail = f"{status} : {done / 1e9:.2f} / {total / 1e9:.2f} Go"
                else:
                    job.detail = status
            if status and status != last_status:
                job.add(status)
                last_status = status
    if last_status != "success":
        raise _StepError("Le téléchargement s'est interrompu avant la fin.")
    job.progress = 1.0
    job.result = {"model": model}


# --------------------------------------------------------------------------- Ollama, liens
def ollama_executable() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    candidates = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        candidates.append(os.path.join(local, "Programs", "Ollama", "ollama.exe"))
    elif sys.platform == "darwin":
        candidates += ["/Applications/Ollama.app/Contents/Resources/ollama", "/usr/local/bin/ollama"]
    else:
        candidates += ["/usr/local/bin/ollama", "/usr/bin/ollama"]
    return next((c for c in candidates if os.path.isfile(c)), None)


def ollama_start() -> dict[str, Any]:
    exe = ollama_executable()
    if exe is None:
        raise ValidationError("Ollama n'est pas installé sur cet ordinateur.")
    kwargs: dict[str, Any] = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    env = dict(os.environ)
    env["OLLAMA_HOST"] = "127.0.0.1:11434"  # jamais exposé au réseau
    try:
        subprocess.Popen([exe, "serve"], env=env, **kwargs)
    except OSError as exc:
        raise ValidationError(f"Ollama ne démarre pas ({exc.__class__.__name__}).") from None
    return {"started": True}


def open_link(url: Any) -> dict[str, Any]:
    if not isinstance(url, str) or not url.startswith(LINK_PREFIXES) or any(c in url for c in " \r\n\"'<>"):
        raise ValidationError("Ce lien ne peut pas être ouvert depuis STATPFE.")
    return {"opened": bool(webbrowser.open(url))}
