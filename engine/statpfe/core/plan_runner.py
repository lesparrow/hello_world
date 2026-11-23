"""Lancement, en un clic, des analyses prévues dans le plan verrouillé.

Chaque analyse est lancée exactement comme si l'utilisateur la lançait à la main
depuis l'analyse prévue : mêmes contrôles, rattachement au plan (donc postérieure
au verrouillage), méthode et variables du plan. Une analyse déjà lancée pour une
analyse prévue de la même version n'est pas relancée.
"""

from __future__ import annotations

from typing import Any

from statpfe.errors import ValidationError
from statpfe.stats import catalog


def _params(item: dict[str, Any]) -> dict[str, Any]:
    spec = catalog.METHODS[item["method"]]
    params: dict[str, Any] = {}
    for role in spec["variables"]:
        names = item["variables"].get(role["name"]) or []
        if names:
            params[role["name"]] = list(names) if role["multiple"] else names[0]
    if "alternative" in spec["params"]:
        params["alternative"] = item.get("alternative", "two-sided")
    return params


def run_planned(project, dataset_id: Any, version_id: Any = None) -> dict[str, Any]:
    locked = project.plan.latest_locked()
    if locked is None:
        raise ValidationError("Verrouillez d'abord le plan d'analyse : les analyses prévues ne peuvent être lancées "
                              "qu'après le verrouillage.")
    if not isinstance(dataset_id, int) or isinstance(dataset_id, bool):
        raise ValidationError("Choisissez le jeu de données.")
    content = locked["content"]
    done = set()
    for a in project.analyses.list():
        c = project.analyses.get(a["id"]).get("choice") or {}
        link = c.get("plan") or {}
        if link.get("version") == locked["version"] and link.get("item"):
            done.add(link["item"])
    study_hyps = project.study.hypotheses
    results = []
    for item in content["analyses"]:
        label = f"{item['id']} : {catalog.METHODS[item['method']]['label']}"
        if item["id"] in done:
            results.append({"item": item["id"], "label": label, "status": "deja_lancee", "analysis_id": None,
                            "message": "Déjà lancée pour cette version du plan."})
            continue
        hyp_text = content["hypotheses"][item["hypothesis"]] if item.get("hypothesis") is not None else None
        hyp = study_hyps.index(hyp_text) if hyp_text in study_hyps else None
        choice = {"mode": "direct", "purpose": "confirmatoire" if item.get("role") == "principale" else "exploratoire",
                  "hypothesis": hyp, "plan_item": item["id"],
                  "reason": "Analyse prévue au plan verrouillé, lancée depuis le plan."}
        try:
            aid = project.analyses.run(dataset_id, version_id, item["method"], _params(item), choice=choice)
            results.append({"item": item["id"], "label": label, "status": "lancee", "analysis_id": aid,
                            "message": "Analyse calculée par le moteur."})
        except ValidationError as exc:
            results.append({"item": item["id"], "label": label, "status": "erreur", "analysis_id": None,
                            "message": exc.message})
    ran = sum(r["status"] == "lancee" for r in results)
    project._log("plan", f"Analyses du plan lancées en un clic : {ran} calculée(s) sur {len(results)}",
                 {"version": locked["version"]})
    return {"version": locked["version"], "results": results, "ran": ran}
