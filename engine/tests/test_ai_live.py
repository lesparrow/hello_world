"""Essai avec un vrai modèle de langage local (exécuté dans le CI GitHub).

Ignoré si STATPFE_AI_LIVE_URL et STATPFE_AI_LIVE_MODEL ne sont pas définis. Le CI installe
Ollama et un petit modèle, puis vérifie le parcours complet par les deux protocoles
(Ollama natif et compatible OpenAI). On ne juge pas la qualité du texte : on vérifie
que la rédaction aboutit, que les contrôles s'appliquent et que tout est tracé.
Les textes produits sont écrits dans STATPFE_AI_LIVE_OUT pour être relus.
"""

from __future__ import annotations

import json
import os
import time

import pytest

from statpfe.rpc.server import Engine
from test_ai import call
from test_report import survey_csv

URL = os.environ.get("STATPFE_AI_LIVE_URL")
MODEL = os.environ.get("STATPFE_AI_LIVE_MODEL")
pytestmark = pytest.mark.skipif(not (URL and MODEL), reason="pas de modèle local configuré")


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_real_local_model(tmp_path, provider):
    e = Engine()
    call(e, "project.create", path=str(tmp_path / "live.statpfe"),
         study={"title": "Essai", "hypotheses": ["Les tutorés ont de meilleures notes."]})
    call(e, "data.import", path=str(survey_csv(tmp_path)), name="Enquête")
    a = call(e, "analysis.run", dataset_id=1, method="welch",
             params={"outcome": "Note", "group": "Tutorat", "levels": ["oui", "non"]},
             choice={"mode": "direct", "purpose": "confirmatoire", "hypothesis": 0})["analysis"]
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": provider, "base_url": URL,
                                                "model": MODEL, "max_tokens": 400, "timeout": 600})
    assert st["state"] == "prete", st
    outputs = []
    for task in ("paragraphe", "limites"):
        job = call(e, "ai.generate", analysis_id=a["id"], task=task)
        end = time.monotonic() + 900
        while job["status"] == "en_cours" and time.monotonic() < end:
            time.sleep(1)
            job = call(e, "ai.job", job_id=job["id"])
        assert job["status"] == "termine", job
        item = job["ai_text"]
        assert item and item["text"].strip() and item["status"] == "proposition"
        assert item["model"] and item["prompt_version"] and len(item["context_hash"]) == 64
        outputs.append({"provider": provider, "task": task, "model": item["model"], "duration_s": item["duration"],
                        "text": item["text"], "unverified_numbers": [u["text"] for u in item["checks"]["unverified"]],
                        "numbers_total": item["checks"]["numbers_total"], "warnings": item["checks"]["warnings"]})
    assert len(call(e, "ai.texts", analysis_id=a["id"])) == 2
    out = os.environ.get("STATPFE_AI_LIVE_OUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for o in outputs:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")
