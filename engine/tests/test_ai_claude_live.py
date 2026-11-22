"""Essai avec le vrai Claude Code (compte Claude connecté). Ignoré sauf STATPFE_CLAUDE_LIVE=1."""

from __future__ import annotations

import json
import os
import time

import pytest

from statpfe.rpc.server import Engine
from test_ai import call
from test_report import survey_csv

pytestmark = pytest.mark.skipif(os.environ.get("STATPFE_CLAUDE_LIVE") != "1", reason="Claude Code réel non demandé")


def test_real_claude_code(tmp_path):
    e = Engine()
    call(e, "project.create", path=str(tmp_path / "live.statpfe"),
         study={"title": "Essai", "hypotheses": ["Les tutorés ont de meilleures notes."]})
    call(e, "data.import", path=str(survey_csv(tmp_path)), name="Enquête")
    a = call(e, "analysis.run", dataset_id=1, method="welch",
             params={"outcome": "Note", "group": "Tutorat", "levels": ["oui", "non"]},
             choice={"mode": "direct", "purpose": "confirmatoire", "hypothesis": 0})["analysis"]
    st = call(e, "ai.update_settings", changes={"enabled": True, "provider": "claude_code", "cloud_consent": True,
                                                "model": os.environ.get("STATPFE_CLAUDE_MODEL", "sonnet")})
    assert st["state"] == "prete", st
    out = []
    for task in ("paragraphe", "limites"):
        job = call(e, "ai.generate", analysis_id=a["id"], task=task)
        end = time.monotonic() + 300
        while job["status"] == "en_cours" and time.monotonic() < end:
            time.sleep(1)
            job = call(e, "ai.job", job_id=job["id"])
        assert job["status"] == "termine", job
        item = job["ai_text"]
        assert item["text"].strip() and item["provider"] == "claude_code"
        out.append({"task": task, "model": item["model"], "duration_s": item["duration"], "text": item["text"],
                    "unverified": [u["text"] for u in item["checks"]["unverified"]],
                    "warnings": item["checks"]["warnings"]})
    path = os.environ.get("STATPFE_CLAUDE_LIVE_OUT")
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
