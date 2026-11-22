"""Assistants d'installation avec les vrais programmes (CI GitHub uniquement, accès à Internet).

- STATPFE_SETUP_LIVE_CLAUDE=1 : installe réellement Claude Code par la commande officielle,
  comme le ferait le bouton « Installer Claude Code », puis vérifie la détection.
- STATPFE_SETUP_LIVE_PULL=<modèle> (avec STATPFE_AI_LIVE_URL) : télécharge un modèle par Ollama
  comme le bouton « Télécharger ».
"""

from __future__ import annotations

import os

import pytest

from statpfe.rpc.server import Engine
from test_ai import call
from test_ai_setup import wait_setup


@pytest.mark.skipif(os.environ.get("STATPFE_SETUP_LIVE_CLAUDE") != "1", reason="installation réelle : CI seulement")
def test_real_claude_code_install():
    e = Engine()
    before = call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code"})
    print("avant :", before["state"], before["claude_executable"])
    snap = wait_setup(e, call(e, "ai.setup_claude_install", confirm=True)["id"], timeout=900)
    print("\n".join(snap["log"]))
    assert snap["status"] == "termine", snap
    assert snap["result"]["executable"] and "Claude Code" in snap["result"]["version"]
    st = call(e, "ai.status")
    print("après :", st["state"], st["claude_executable"], st["claude_auth"])
    # Le CI n'a pas de compte Claude : l'étape suivante doit être la connexion.
    assert st["claude_executable"] == snap["result"]["executable"]
    assert st["state"] == "claude_non_connecte" and st["claude_auth"]["logged_in"] is False


@pytest.mark.skipif(not (os.environ.get("STATPFE_SETUP_LIVE_PULL") and os.environ.get("STATPFE_AI_LIVE_URL")),
                    reason="téléchargement réel : CI seulement")
def test_real_ollama_pull():
    model = os.environ["STATPFE_SETUP_LIVE_PULL"]
    e = Engine()
    call(e, "ai.update_settings", changes={"enabled": True, "provider": "ollama",
                                           "base_url": os.environ["STATPFE_AI_LIVE_URL"]})
    snap = wait_setup(e, call(e, "ai.setup_ollama_pull", model=model, confirm=True)["id"], timeout=1200)
    print("\n".join(snap["log"]))
    assert snap["status"] == "termine" and snap["progress"] == 1.0, snap
    st = call(e, "ai.update_settings", changes={"model": model})
    assert st["state"] == "prete", st
