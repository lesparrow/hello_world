"""Contrôles avant export d'un rapport (§17 du cahier des charges).

Niveaux : « bloquant » empêche l'export ; « important » et « methodologique »
sont affichés et repris dans la section Limites ; « information » renseigne.
"""

from __future__ import annotations

from typing import Any

from statpfe.stats.catalog import METHODS

LEVEL_ORDER = {"bloquant": 0, "important": 1, "methodologique": 2, "information": 3}


def run_checks(project, options: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    passed: list[str] = []

    def add(level: str, title: str, detail: str = "", analysis_id: int | None = None) -> None:
        items.append({"level": level, "title": title, "detail": detail, "analysis_id": analysis_id})

    ids = options["analyses"]
    existing = {a["id"] for a in project.analyses.list()}
    unknown = [i for i in ids if i not in existing]
    if unknown:
        add("bloquant", "Analyse introuvable", "Une analyse choisie a été supprimée. Mettez à jour la sélection.")
    ids = [i for i in ids if i in existing]
    sections = options["sections"]
    if not ids:
        add("bloquant" if sections["descriptive"] or sections["inferential"] else "important",
            "Aucune analyse sélectionnée", "Choisissez au moins une analyse enregistrée à inclure dans le rapport.")

    analyses = [project.analyses.get(i) for i in ids]
    verified, identical = 0, 0
    for a in analyses:
        name = f"« {a['title']} »"
        if a["method"] not in METHODS:
            add("bloquant", f"{name} : méthode inconnue", "Cette méthode n'existe pas dans cette version de STATPFE.",
                a["id"])
            continue
        v = project.analyses.verify(a["id"])
        if v["status"] != "a_jour":
            add("bloquant", f"{name} : {v['status_label'].lower()}",
                "Les données utilisées par cette analyse ne sont plus celles du projet : relancez l'analyse sur les "
                "données actuelles ou retirez-la du rapport.", a["id"])
            continue
        if v["error"]:
            add("bloquant", f"{name} : recalcul impossible", v["error"], a["id"])
            continue
        verified += 1
        n_used = a["result"].get("n_used")
        if n_used is not None and v["rows"] is not None and n_used > v["rows"]:
            add("bloquant", f"{name} : effectif incohérent",
                f"{n_used} observations utilisées pour {v['rows']} lignes dans les données.", a["id"])
        if v["differences"]:
            paths = ", ".join(d["path"] for d in v["differences"][:3])
            add("bloquant", f"{name} : résultats différents au recalcul",
                f"Les valeurs, effectifs, tableaux ou graphiques enregistrés ne correspondent plus au recalcul ({paths}"
                "…). Relancez l'analyse.", a["id"])
        else:
            identical += 1
        for d in a["result"].get("diagnostics") or []:
            if d["level"] in ("bloquant", "important"):
                add("important", f"{name} : {d['title']}",
                    (d.get("detail") or "") + (" Ce point sera repris dans la section Limites."
                                               if sections["limits"] else ""), a["id"])
        c = a.get("choice") or {}
        if not c.get("mode"):
            add("information", f"{name} : choix de la méthode non enregistré",
                "Analyse créée avant l'assistant méthodologique : la justification du choix n'est pas disponible.",
                a["id"])
        elif c.get("mode") == "assistant" and not c.get("followed"):
            add("information", f"{name} : méthode différente de la recommandation",
                "La justification enregistrée figurera dans la méthodologie.", a["id"])
        if c.get("purpose") == "exploratoire":
            add("information", f"{name} : analyse exploratoire",
                "Elle sera présentée comme exploratoire dans le rapport.", a["id"])
        if c.get("purpose") == "confirmatoire" and c.get("hypothesis") is None and project.study.hypotheses:
            add("methodologique", f"{name} : analyse confirmatoire sans hypothèse liée",
                "Indiquez quelle hypothèse elle met à l'épreuve (en la relançant avec l'assistant ou en choix direct).",
                a["id"])

    if analyses:
        if verified == len(analyses):
            passed.append(f"Version des données vérifiée pour les {verified} analyse(s) : données inchangées depuis le "
                          "calcul.")
        if identical == len(analyses):
            passed.append("Effectifs, valeurs, tableaux et graphiques recalculés : identiques aux résultats "
                          "enregistrés.")
        passed.append("Méthode et paramètres enregistrés pour chaque analyse (méthodologie et annexe de traçabilité).")
        if len({str(a["environment"]) for a in analyses}) > 1:
            add("information", "Versions de logiciel différentes",
                "Les analyses n'ont pas toutes été calculées avec les mêmes versions ; l'annexe de traçabilité les "
                "précise.")

    important = [i for i in items if i["level"] == "important"]
    if important and not sections["limits"]:
        add("important", "Section « Limites » désactivée",
            f"{len(important)} avertissement(s) important(s) ne seraient pas repris dans le rapport. Activez la "
            "section Limites.")
    elif sections["limits"]:
        passed.append("Les avertissements des analyses et les choix de méthode justifiés sont repris dans la section "
                      "Limites.")
    hyps = project.study.hypotheses
    if hyps and (sections["hypotheses"] or sections["limits"]):
        linked = {(a.get("choice") or {}).get("hypothesis") for a in analyses}
        missing = [f"H{i + 1}" for i in range(len(hyps)) if i not in linked]
        if missing:
            add("methodologique", "Hypothèse(s) sans analyse liée", ", ".join(missing) + " : aucune analyse du rapport "
                "n'y est explicitement liée.")
    if sections["introduction"] and not project.study.problem_statement.strip():
        add("methodologique", "Problématique non renseignée",
            "La section « Présentation de l'étude » contiendra un emplacement à compléter.")
    todo = [lbl for key, lbl in (("discussion", "Discussion"), ("conclusion", "Conclusion")) if sections[key]]
    if todo:
        add("information", "Sections à rédiger", f"{', '.join(todo)} : emplacements marqués « à rédiger » pour "
                                                   "l'auteur.")
    passed.append("Aucun texte généré par intelligence artificielle : les lectures des résultats sont produites par "
                  "des règles fixes et signalées comme telles.")
    passed.append("Le rapport est présenté comme un document de travail à réviser, non comme un travail validé.")
    items.sort(key=lambda i: LEVEL_ORDER[i["level"]])
    return {"items": items, "passed": passed, "blocking": sum(i["level"] == "bloquant" for i in items)}
