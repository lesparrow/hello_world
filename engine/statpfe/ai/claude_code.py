"""Appel de Claude Code (programme « claude » d'Anthropic) pour rédiger une proposition.

Mode en ligne, utilisé seulement après l'autorisation explicite de l'utilisateur : le
texte transmis (résultats calculés, jamais les données brutes) part vers le service
Claude d'Anthropic avec le compte Claude de l'utilisateur.

Claude Code est un agent capable de lire des fichiers et d'exécuter des commandes. Il
est donc lancé en mode le plus fermé possible :
- aucun outil (`--tools ""`), aucun serveur MCP (`--strict-mcp-config`), aucune
  personnalisation (`--safe-mode` : ni CLAUDE.md, ni hooks, ni plugins) ;
- dans un dossier temporaire vide, sans conserver la session ;
- consignes système de STATPFE (fichier), demande transmise par l'entrée standard.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Callable

from statpfe.ai.settings import AiSettings

VERSION_TIMEOUT = 15
MAX_LINE = 4 * 1024 * 1024


class ClaudeCodeError(Exception):
    pass


def executable(settings: AiSettings) -> str | None:
    if settings.claude_path:
        return settings.claude_path if os.path.isfile(settings.claude_path) else None
    found = shutil.which("claude")
    if found:
        return found
    # Emplacements d'installation habituels non présents dans le PATH d'une application graphique.
    home = os.path.expanduser("~")
    candidates = [os.path.join(home, ".local", "bin", "claude"), os.path.join(home, ".claude", "local", "claude")]
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        candidates = [os.path.join(home, ".local", "bin", "claude.exe"), os.path.join(appdata, "npm", "claude.cmd")]
    return next((c for c in candidates if os.path.isfile(c)), None)


def _no_window() -> dict[str, Any]:
    if sys.platform == "win32":
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


def version(settings: AiSettings) -> str:
    exe = executable(settings)
    if exe is None:
        raise ClaudeCodeError("Claude Code est introuvable sur cet ordinateur.")
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=VERSION_TIMEOUT,
                             stdin=subprocess.DEVNULL, **_no_window())
    except (OSError, subprocess.SubprocessError) as exc:
        raise ClaudeCodeError(f"Claude Code ne démarre pas ({exc.__class__.__name__}).") from None
    if out.returncode != 0:
        raise ClaudeCodeError("Claude Code ne répond pas correctement (« claude --version » a échoué).")
    return out.stdout.strip()[:100]


def auth_status(settings: AiSettings) -> dict[str, Any]:
    """État de connexion au compte Claude (« claude auth status --json »). N'envoie aucune donnée d'étude."""
    exe = executable(settings)
    if exe is None:
        return {"logged_in": None, "method": None, "error": "Claude Code est introuvable."}
    try:
        out = subprocess.run([exe, "auth", "status", "--json"], capture_output=True, text=True,
                             timeout=VERSION_TIMEOUT, stdin=subprocess.DEVNULL, **_no_window())
        data = json.loads(out.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"logged_in": None, "method": None, "error": "État de connexion illisible."}
    if not isinstance(data, dict) or not isinstance(data.get("loggedIn"), bool):
        return {"logged_in": None, "method": None, "error": "État de connexion illisible."}
    method = data.get("authMethod")
    return {"logged_in": data["loggedIn"], "method": method if isinstance(method, str) else None, "error": None}


def command(exe: str, settings: AiSettings, system_file: str) -> list[str]:
    return [exe, "-p", "--safe-mode", "--tools", "", "--strict-mcp-config", "--no-session-persistence",
            "--output-format", "stream-json", "--include-partial-messages", "--verbose",
            "--model", settings.model or "sonnet", "--system-prompt-file", system_file]


def stream_chat(settings: AiSettings, messages: list[dict[str, str]], cancel: threading.Event,
                on_text: Callable[[str], None]) -> dict[str, Any]:
    exe = executable(settings)
    if exe is None:
        raise ClaudeCodeError("Claude Code est introuvable sur cet ordinateur.")
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
    meta: dict[str, Any] = {"finish": None, "model": settings.model}
    with tempfile.TemporaryDirectory(prefix="statpfe-claude-") as work:
        system_file = os.path.join(work, "consignes.txt")
        with open(system_file, "w", encoding="utf-8") as f:
            f.write(system)
        empty = os.path.join(work, "vide")
        os.mkdir(empty)
        try:
            proc = subprocess.Popen(command(exe, settings, system_file), cwd=empty, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_no_window())
        except OSError as exc:
            raise ClaudeCodeError(f"Claude Code ne démarre pas ({exc.__class__.__name__}).") from None
        timed_out = threading.Event()
        killer = threading.Thread(target=_watch, args=(proc, cancel, settings.timeout, timed_out), daemon=True)
        killer.start()
        try:
            assert proc.stdin and proc.stdout
            proc.stdin.write(user.encode("utf-8"))
            proc.stdin.close()
            streamed = False
            final = None
            error = None
            for raw in iter(lambda: proc.stdout.readline(MAX_LINE), b""):
                if cancel.is_set() or timed_out.is_set():
                    break
                try:
                    data = json.loads(raw.decode("utf-8", "replace"))
                except ValueError:
                    continue
                kind = data.get("type")
                if kind == "stream_event":
                    ev = data.get("event") or {}
                    if ev.get("type") == "message_start":
                        model = (ev.get("message") or {}).get("model")
                        if isinstance(model, str):
                            meta["model"] = model
                    elif ev.get("type") == "content_block_delta":
                        delta = ev.get("delta") or {}
                        if delta.get("type") == "text_delta" and delta.get("text"):
                            streamed = True
                            on_text(delta["text"])
                elif kind == "result":
                    final = data
                    if data.get("is_error"):
                        error = str(data.get("result") or data.get("subtype") or "erreur")
                    meta["finish"] = data.get("stop_reason") or data.get("subtype") or "stop"
                    if isinstance(data.get("total_cost_usd"), (int, float)):
                        meta["cost_usd"] = data["total_cost_usd"]
            proc.wait(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
        if timed_out.is_set():
            raise ClaudeCodeError(f"Claude Code n'a pas répondu dans le délai maximal ({settings.timeout} s).")
        if cancel.is_set():
            meta["finish"] = "annule"
            return meta
        stderr = (proc.stderr.read(4000).decode("utf-8", "replace") if proc.stderr else "").strip()
        if error:
            raise ClaudeCodeError(f"Claude Code a renvoyé une erreur : {error[:300]}")
        if final is None:
            hint = stderr.splitlines()[-1][:300] if stderr else f"code de sortie {proc.returncode}"
            raise ClaudeCodeError(f"Claude Code s'est arrêté sans réponse ({hint}). Vérifiez qu'il est connecté "
                                  "à votre compte (lancez « claude » une fois dans un terminal).")
        if not streamed and isinstance(final.get("result"), str):
            on_text(final["result"])
    return meta


def _watch(proc: subprocess.Popen, cancel: threading.Event, timeout: int, timed_out: threading.Event) -> None:
    """Arrête Claude Code en cas d'annulation ou de délai dépassé."""
    cancelled = cancel.wait(timeout)
    if proc.poll() is None:
        if not cancelled:
            timed_out.set()
        proc.kill()
