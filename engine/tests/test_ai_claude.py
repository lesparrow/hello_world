"""Mode « Claude Code » : autorisation explicite, lancement sans outils, flux, erreurs.

Un faux programme « claude » (script Python) imite la sortie stream-json de Claude Code.
L'essai avec le vrai Claude Code est dans test_ai_claude_live.py.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import textwrap
import time

import pytest

from statpfe.ai import settings
from statpfe.errors import ValidationError
from test_ai import _engine_with_project, call, call_error, wait  # noqa: F401
from fake_model_server import FakeModelServer

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="faux exécutable POSIX")

FAKE = r'''#!{python}
import json, os, sys, time
log = {{"argv": sys.argv[1:], "cwd": os.getcwd(), "cwd_files": os.listdir(os.getcwd())}}
if sys.argv[1:] == ["--version"]:
    print("9.9.9 (Claude Code)"); sys.exit(0)
args = sys.argv[1:]
log["system"] = open(args[args.index("--system-prompt-file") + 1], encoding="utf-8").read()
log["stdin"] = sys.stdin.read()
open({log!r}, "w", encoding="utf-8").write(json.dumps(log))
mode = os.environ.get("FAKE_CLAUDE_MODE", "ok")
def out(d): print(json.dumps(d), flush=True)
out({{"type": "system", "subtype": "init", "tools": [], "mcp_servers": []}})
if mode == "error":
    out({{"type": "result", "subtype": "success", "is_error": True, "result": "Not logged in · Please run /login"}}); sys.exit(1)
if mode == "silent":
    print("boom", file=sys.stderr); sys.exit(3)
out({{"type": "stream_event", "event": {{"type": "message_start", "message": {{"model": "claude-sonnet-test"}}}}}})
for piece in ["La statistique ", "vaut 99,9 ", "selon le modèle."]:
    if mode == "slow": time.sleep(1)
    out({{"type": "stream_event", "event": {{"type": "content_block_delta", "delta": {{"type": "text_delta", "text": piece}}}}}})
out({{"type": "result", "subtype": "success", "is_error": False, "result": "x", "stop_reason": "end_turn", "total_cost_usd": 0.001}})
'''


@pytest.fixture
def fake_claude(tmp_path, monkeypatch):
    d = tmp_path / "bin"
    d.mkdir()
    exe = d / "claude"
    log = tmp_path / "claude-call.json"
    exe.write_text(FAKE.format(python=sys.executable, log=str(log)), encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    return exe, log


def test_claude_path_validation(tmp_path):
    other = tmp_path / "evil.sh"
    other.write_text("x")
    with pytest.raises(ValidationError):
        settings.claude_path(str(other))
    with pytest.raises(ValidationError):
        settings.claude_path("claude")  # chemin relatif
    with pytest.raises(ValidationError):
        settings.claude_path(str(tmp_path / "claude"))  # absent
    assert settings.claude_path("") == ""


def test_consent_is_required_and_recorded(tmp_path, fake_claude):
    server = FakeModelServer()
    try:
        e, a = _engine_with_project(tmp_path, server)
        st = call(e, "ai.update_settings", changes={"provider": "claude_code"})
        assert st["settings"]["model"] == "sonnet" and st["state"] == "consentement_requis" and not st["ready"]
        assert "autorisation" in call_error(e, "ai.generate", analysis_id=a["id"], task="paragraphe")
        st = call(e, "ai.update_settings", changes={"cloud_consent": True})
        assert st["state"] == "prete" and st["settings"]["cloud_consent_at"]
        assert st["claude_executable"] == str(fake_claude[0])
        assert [m["name"] for m in st["models"]] == ["sonnet", "opus", "fable"]
        st = call(e, "ai.update_settings", changes={"cloud_consent": False})
        assert st["state"] == "consentement_requis" and st["settings"]["cloud_consent_at"] is None
        # Retour au mode local : modèle à rechoisir.
        st = call(e, "ai.update_settings", changes={"provider": "ollama"})
        assert st["settings"]["model"] == "" and st["settings"]["base_url"] == "http://127.0.0.1:11434"
    finally:
        server.close()


def test_claude_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    e = __import__("statpfe.rpc.server", fromlist=["Engine"]).Engine()
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code", "cloud_consent": True})
    assert st["state"] == "claude_absent" and "introuvable" in st["server"]["error"]


def test_generation_runs_claude_without_tools(tmp_path, fake_claude):
    server = FakeModelServer()
    try:
        e, a = _engine_with_project(tmp_path, server)
        call(e, "ai.update_settings", changes={"provider": "claude_code", "cloud_consent": True, "model": "opus"})
        snap = wait(e, call(e, "ai.generate", analysis_id=a["id"], task="paragraphe")["id"])
        assert snap["status"] == "termine", snap
        item = snap["ai_text"]
        assert item["provider"] == "claude_code" and item["model"] == "claude-sonnet-test"
        assert item["text"] == "La statistique vaut 99,9 selon le modèle."
        assert [u["text"] for u in item["checks"]["unverified"]] == ["99,9"]  # même contrôle qu'en local
        log = json.loads(fake_claude[1].read_text(encoding="utf-8"))
        argv = log["argv"]
        for flag in ("-p", "--safe-mode", "--strict-mcp-config", "--no-session-persistence"):
            assert flag in argv
        assert argv[argv.index("--tools") + 1] == ""  # aucun outil : ni fichiers ni commandes
        assert argv[argv.index("--model") + 1] == "opus"
        assert log["cwd_files"] == []  # dossier de travail vide
        assert "N'écris aucun nombre" in log["system"] and log["stdin"].startswith("<resultats>")
        assert "Alami" not in log["stdin"]
        journal = [j["summary"] for j in call(e, "project.current")["journal"]]
        assert any("Proposition de Claude (en ligne, via Claude Code)" in s for s in journal)
        # Le rapport nomme le service en ligne.
        call(e, "ai.keep", text_id=item["id"], text="Le paragraphe est à rédiger.", reviewed=True)
        from statpfe.report.build import build
        from statpfe.report.options import clean_options
        text = build(e.project, clean_options(e.project.reports.options())).text()
        assert "Texte rédigé avec l'aide de Claude (service en ligne d'Anthropic, via Claude Code)" in text
        assert "avec l'autorisation explicite de l'auteur" in text
    finally:
        server.close()


@pytest.mark.parametrize("mode,expected", [("error", "Not logged in"), ("silent", "sans réponse")])
def test_claude_errors_are_readable(tmp_path, fake_claude, monkeypatch, mode, expected):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    server = FakeModelServer()
    try:
        e, a = _engine_with_project(tmp_path, server)
        call(e, "ai.update_settings", changes={"provider": "claude_code", "cloud_consent": True})
        snap = wait(e, call(e, "ai.generate", analysis_id=a["id"], task="methode")["id"])
        assert snap["status"] == "erreur" and expected in snap["error"]
        assert call(e, "ai.texts", analysis_id=a["id"]) == []
    finally:
        server.close()


def test_claude_cancel(tmp_path, fake_claude, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "slow")
    server = FakeModelServer()
    try:
        e, a = _engine_with_project(tmp_path, server)
        call(e, "ai.update_settings", changes={"provider": "claude_code", "cloud_consent": True})
        job = call(e, "ai.generate", analysis_id=a["id"], task="methode")
        time.sleep(0.5)
        assert call(e, "ai.cancel", job_id=job["id"])["status"] == "annule"
        time.sleep(1.5)
        assert call(e, "ai.texts", analysis_id=a["id"]) == []
    finally:
        server.close()
