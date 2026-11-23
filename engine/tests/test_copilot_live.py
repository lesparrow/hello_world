"""Copilote IA avec un vrai modèle local (exécuté dans le CI GitHub, Ollama + petit modèle).

Ignoré sans STATPFE_AI_LIVE_URL et STATPFE_AI_LIVE_MODEL. Un très petit modèle (0,5 milliard de
paramètres) produit souvent un JSON incomplet ou des choix discutables : on ne juge pas la qualité.
On vérifie que chaque demande aboutit à une proposition enregistrée et vérifiée par le moteur
(« proposée » ou « illisible »), ou à une erreur expliquée si le modèle boucle, que rien n'est modifié sans application, et qu'une proposition
illisible ne peut pas être appliquée. Les propositions sont écrites dans STATPFE_AI_LIVE_OUT.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from statpfe.rpc.server import Engine
from test_ai import call, call_error
from test_report import survey_csv

URL = os.environ.get("STATPFE_AI_LIVE_URL")
MODEL = os.environ.get("STATPFE_AI_LIVE_MODEL")
pytestmark = pytest.mark.skipif(not (URL and MODEL), reason="pas de modèle local configuré")


def test_real_model_copilot(tmp_path):
    e = Engine()
    call(e, "project.create", path=str(tmp_path / "copilote.statpfe"),
         study={"title": "Essai", "hypotheses": ["Les étudiants tutorés ont de meilleures notes."]})
    call(e, "data.import", path=str(survey_csv(tmp_path)), name="Enquête")
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "ollama", "base_url": URL,
                                                "model": MODEL, "timeout": 900})
    assert st["state"] == "prete", st
    before = call(e, "project.current")["study"]
    outputs = []
    for action, params in (("study", {"subject": "Le tutorat améliore-t-il les notes des étudiants de L1 ?"}),
                           ("variables", {}), ("plan", {})):
        job = call(e, "ai.copilot_start", action=action, params=params)
        end = time.monotonic() + 900
        while job["status"] == "en_cours" and time.monotonic() < end:
            time.sleep(1)
            job = call(e, "ai.job", job_id=job["id"])
        assert job["status"] in ("termine", "erreur"), job
        if job["status"] == "erreur":
            # Un très petit modèle peut boucler (Ollama l'arrête) : erreur expliquée, rien d'enregistré.
            assert job["error"] and job["proposal"] is None, job
            outputs.append({"action": action, "status": "erreur", "error": job["error"]})
            continue
        p = job["proposal"]
        assert p and p["status"] in ("proposee", "illisible"), p
        if p["status"] == "illisible":
            assert "illisible" in call_error(e, "ai.copilot_apply", proposal_id=p["id"])
        outputs.append({"action": action, "model": p["model"], "duration_s": p["duration"], "status": p["status"],
                        "issues": p["issues"], "proposal": p["proposal"]})
    # Rien n'est appliqué sans l'accord de l'utilisateur.
    assert call(e, "project.current")["study"] == before
    assert call(e, "ai.marks")["marks"] == []
    out = os.environ.get("STATPFE_AI_LIVE_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for o in outputs:
                f.write(json.dumps({"copilote": o}, ensure_ascii=False) + "\n")
