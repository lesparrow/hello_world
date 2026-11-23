"""Parcours réel avec le moteur INSTALLÉ (exécutable autonome) : projet, import CSV, test de
Welch, calcul de puissance, rapports Word et PDF, réouverture du projet.

Usage : python packaging/engine_functional.py <moteur> <dossier de travail> [create|reopen]
- create : crée le projet dans le dossier de travail (avant une mise à jour) ;
- reopen : rouvre ce projet (après une mise à jour) et vérifie que tout y est encore.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(engine: str, requests: list[dict]) -> list[dict]:
    lines = "\n".join(json.dumps({"jsonrpc": "2.0", "id": i + 1, **r}) for i, r in enumerate(requests)) + "\n"
    out = subprocess.run([engine], input=lines, capture_output=True, text=True, encoding="utf-8", timeout=300)
    responses = [json.loads(line) for line in out.stdout.splitlines() if line.strip()]
    for req, res in zip(requests, responses):
        if "error" in res:
            raise SystemExit(f"{req['method']} : {res['error']['message']}")
    if len(responses) != len(requests):
        raise SystemExit(f"réponses manquantes ({len(responses)}/{len(requests)}) :\n{out.stderr[-2000:]}")
    return [r["result"] for r in responses]


def main() -> int:
    engine, work, mode = sys.argv[1], Path(sys.argv[2]), (sys.argv[3] if len(sys.argv) > 3 else "create")
    work.mkdir(parents=True, exist_ok=True)
    project = work / "etude.statpfe"
    if mode == "create":
        csv = work / "enquete.csv"
        csv.write_bytes("groupe;note\nA;12,5\nA;13\nA;11,5\nB;9\nB;10\nB;8,5\n".encode("cp1252"))
        project.unlink(missing_ok=True)
        res = run(engine, [
            {"method": "project.create", "params": {"path": str(project), "study": {"title": "Étude d'essai"}}},
            {"method": "data.import", "params": {"path": str(csv), "name": "Enquête"}},
            {"method": "analysis.run", "params": {"dataset_id": 1, "method": "welch",
                                                  "params": {"outcome": "note", "group": "groupe"}}},
            {"method": "power.save", "params": {"request": {"design": "t_two", "mode": "sample_size",
                                                            "effects": [{"d": 0.5}]}}},
            {"method": "report.export", "params": {"path": str(work / "rapport.docx"), "format": "docx",
                                                   "options": {"analyses": [1]}}},
            {"method": "report.export", "params": {"path": str(work / "rapport.pdf"), "format": "pdf",
                                                   "options": {"analyses": [1]}}},
            {"method": "project.save", "params": {}},
        ])
        dump = json.dumps(res[2])
        assert '"key": "t", "label": "t", "value": 5.07796' in dump, dump[:500]
        t = 5.07796
        assert (work / "rapport.pdf").read_bytes()[:5] == b"%PDF-" and (work / "rapport.docx").stat().st_size > 20000
        print(f"projet créé : t = {t:.5f}, rapports Word et PDF produits")
    else:
        res = run(engine, [
            {"method": "engine.info", "params": {}},
            {"method": "project.open", "params": {"path": str(project)}},
            {"method": "app.recent_projects", "params": {}},
        ])
        state = res[1]
        assert state["study"]["title"] == "Étude d'essai", state["study"]
        assert state["analyses_count"] == 1 and len(state["datasets"]) == 1 and state["power_count"] == 1, state
        assert any(r["path"] == str(project) for r in res[2]), res[2]
        print(f"projet rouvert après mise à jour (moteur {res[0]['version']}) : étude, données, analyse, "
              "projets récents conservés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
