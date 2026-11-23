"""Assistants d'installation : Claude Code (installation, connexion) et IA locale (Ollama).

Les programmes réels sont remplacés par des faux (installateur, « claude », serveur Ollama
factice). L'installation réelle de Claude Code et le téléchargement réel d'un modèle
sont essayés dans le CI GitHub (accès à Internet).
"""

from __future__ import annotations

import os
import stat
import sys
import time

import pytest

from statpfe.ai import setup, system
from statpfe.rpc.server import Engine
from test_ai import call, call_error  # noqa: F401
from test_ai_claude import FAKE
from fake_model_server import FakeModelServer

posix = pytest.mark.skipif(sys.platform == "win32", reason="faux exécutables POSIX")


def wait_setup(e: Engine, job_id: int, timeout: float = 15, until=None) -> dict:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        snap = call(e, "ai.setup_job", job_id=job_id)
        if (until and until(snap)) or snap["status"] != "en_cours":
            return snap
        time.sleep(0.05)
    raise AssertionError(f"étape trop longue : {snap}")


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Ordinateur sans Claude Code : PATH réduit, dossier personnel vide."""
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    monkeypatch.setenv("PATH", os.path.dirname(sys.executable) + os.pathsep + "/usr/bin" + os.pathsep + "/bin")
    return h


@posix
def test_install_requires_confirmation_then_installs(tmp_path, home, monkeypatch):
    # Faux installateur : dépose un faux « claude » là où l'installateur officiel le met.
    target = home / ".local" / "bin" / "claude"
    log = tmp_path / "call.json"
    installer = tmp_path / "install.sh"
    installer.write_text("#!/bin/sh\necho 'Installing Claude Code...'\nmkdir -p \"$(dirname \"$1\")\"\n"
                         "cat \"$2\" > \"$1\"\nchmod +x \"$1\"\necho 'Installation complete'\n", encoding="utf-8")
    fake = tmp_path / "fake-claude"
    fake.write_text(FAKE.format(python=sys.executable, log=str(log)), encoding="utf-8")
    monkeypatch.setitem(setup.CLAUDE_INSTALL, "unix", {"display": "curl … | bash", "shell": "Terminal",
                                                       "argv": ["sh", str(installer), str(target), str(fake)]})
    e = Engine()
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code"})
    assert st["state"] == "claude_absent"
    # Rien n'est téléchargé sans confirmation explicite.
    assert "confirmez" in call_error(e, "ai.setup_claude_install")
    assert "confirmez" in call_error(e, "ai.setup_claude_install", confirm="oui")
    assert not target.exists()
    snap = wait_setup(e, call(e, "ai.setup_claude_install", confirm=True)["id"])
    assert snap["status"] == "termine", snap
    assert snap["result"]["executable"] == str(target) and "9.9.9" in snap["result"]["version"]
    assert "Installing Claude Code..." in snap["log"]
    # Étape suivante : connecté (faux claude sans fichier d'état), donc autorisation à donner.
    assert call(e, "ai.status")["state"] == "consentement_requis"


@posix
def test_install_failure_is_readable(tmp_path, home, monkeypatch):
    monkeypatch.setitem(setup.CLAUDE_INSTALL, "unix", {"display": "x", "shell": "Terminal",
                                                       "argv": ["sh", "-c", "echo 'curl: (6) Could not resolve host'; exit 6"]})
    e = Engine()
    call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code"})
    snap = wait_setup(e, call(e, "ai.setup_claude_install", confirm=True)["id"])
    assert snap["status"] == "erreur" and "code de sortie 6" in snap["error"]
    assert any("Could not resolve host" in line for line in snap["log"])


@posix
def test_login_flow_with_pasted_code(tmp_path, home, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "claude"
    exe.write_text(FAKE.format(python=sys.executable, log=str(tmp_path / "c.json")), encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    auth = tmp_path / "auth-ok"
    monkeypatch.setenv("FAKE_CLAUDE_AUTH_FILE", str(auth))
    e = Engine()
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code"})
    assert st["state"] == "claude_non_connecte" and st["claude_auth"]["logged_in"] is False
    # Mauvais code : échec lisible.
    job = call(e, "ai.setup_claude_login")
    snap = wait_setup(e, job["id"], until=lambda s: s["waiting_code"])
    assert snap["url"] == "https://claude.ai/oauth/authorize?code=true&state=test"
    call(e, "ai.setup_code", job_id=job["id"], code="mauvais")
    snap = wait_setup(e, job["id"])
    assert snap["status"] == "erreur" and "n'a pas abouti" in snap["error"]
    # Bon code : connecté.
    job = call(e, "ai.setup_claude_login")
    wait_setup(e, job["id"], until=lambda s: s["waiting_code"])
    assert "Collez" in call_error(e, "ai.setup_code", job_id=job["id"], code="")
    call(e, "ai.setup_code", job_id=job["id"], code="bon-code")
    snap = wait_setup(e, job["id"])
    assert snap["status"] == "termine" and snap["result"]["auth"]["logged_in"] is True, snap
    st = call(e, "ai.status")
    assert st["state"] == "consentement_requis"
    st = call(e, "ai.update_settings", changes={"cloud_consent": True})
    assert st["state"] == "prete"


@posix
def test_login_can_be_cancelled(tmp_path, home, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "claude"
    exe.write_text(FAKE.format(python=sys.executable, log=str(tmp_path / "c.json")), encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_CLAUDE_AUTH_FILE", str(tmp_path / "auth-ok"))
    e = Engine()
    call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code"})
    job = call(e, "ai.setup_claude_login")
    wait_setup(e, job["id"], until=lambda s: s["waiting_code"])
    assert "déjà en cours" in call_error(e, "ai.setup_claude_login")
    assert call(e, "ai.setup_cancel", job_id=job["id"])["status"] == "annule"
    time.sleep(0.3)
    assert call(e, "ai.setup_job", job_id=job["id"])["status"] == "annule"
    assert call(e, "ai.status")["state"] == "claude_non_connecte"


def test_login_requires_claude(home):
    e = Engine()
    call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code"})
    assert "Installez d'abord" in call_error(e, "ai.setup_claude_login")


def test_ollama_pull_with_confirmation_and_progress(home):
    server = FakeModelServer(models=())
    server.delay = 0.05
    try:
        e = Engine()
        st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "ollama", "base_url": server.url})
        assert st["state"] == "aucun_modele" and st["ollama_installed"] is True
        assert any(m["recommended"] for m in st["local_catalog"]) or st["resources"]["memory_total"] is None
        assert "confirmé" in call_error(e, "ai.setup_ollama_pull", model="qwen2.5:3b")
        assert "invalide" in call_error(e, "ai.setup_ollama_pull", model="x; rm -rf /", confirm=True)
        snap = wait_setup(e, call(e, "ai.setup_ollama_pull", model="qwen2.5:3b", confirm=True)["id"])
        assert snap["status"] == "termine" and snap["progress"] == 1.0, snap
        assert "success" in snap["log"]
        pulled = [r for r in server.requests if r["path"] == "/api/pull"]
        assert pulled == [{"path": "/api/pull", "body": {"model": "qwen2.5:3b", "stream": True}}]
        st = call(e, "ai.update_settings", changes={"model": "qwen2.5:3b"})
        assert st["state"] == "prete"
        assert next(m for m in st["local_catalog"] if m["name"] == "qwen2.5:3b")["installed"] is True
        # Modèle inconnu : refus d'Ollama affiché.
        snap = wait_setup(e, call(e, "ai.setup_ollama_pull", model="inexistant:1b", confirm=True)["id"])
        assert snap["status"] == "erreur" and "file does not exist" in snap["error"]
    finally:
        server.close()


def test_ollama_absent_is_detected(home, monkeypatch):
    monkeypatch.setattr(setup, "ollama_executable", lambda: None)
    e = Engine()
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "ollama",
                                                "base_url": "http://127.0.0.1:9"})
    assert st["state"] == "serveur_absent" and st["ollama_installed"] is False
    assert st["ollama_download"] == "https://ollama.com/download"
    assert "pas installé" in call_error(e, "ai.setup_ollama_start")
    snap = wait_setup(e, call(e, "ai.setup_ollama_pull", model="qwen2.5:3b", confirm=True)["id"])
    assert snap["status"] == "erreur" and "Ollama ne répond pas" in snap["error"]


def test_local_catalog_follows_memory():
    gb = system.GB
    small = system.local_catalog(8 * gb)
    assert [m["name"] for m in small if m["recommended"]] == ["llama3.2:3b", "qwen2.5:3b"]
    assert not next(m for m in small if m["name"] == "qwen2.5:7b")["fits"]
    big = system.local_catalog(16 * gb, {"mistral:7b"})
    assert {m["name"] for m in big if m["recommended"]} == {"mistral:7b", "qwen2.5:7b"}
    assert next(m for m in big if m["name"] == "mistral:7b")["installed"]
    assert all(not m["recommended"] for m in system.local_catalog(2 * gb))


def test_only_known_links_can_be_opened(monkeypatch):
    opened = []
    monkeypatch.setattr(setup.webbrowser, "open", lambda url: opened.append(url) or True)
    e = Engine()
    assert call(e, "ai.open_link", url="https://ollama.com/download")["opened"]
    assert call(e, "ai.open_link", url="https://claude.ai/oauth/authorize?x=1")["opened"]
    for bad in ("http://ollama.com/download", "https://evil.example/", "file:///etc/passwd",
                "https://claude.ai.evil.example/", "javascript:alert(1)"):
        assert "ne peut pas" in call_error(e, "ai.open_link", url=bad)
    assert opened == ["https://ollama.com/download", "https://claude.ai/oauth/authorize?x=1"]
