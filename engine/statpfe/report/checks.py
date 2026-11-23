"""Contrôles avant export d'un rapport (§17 du cahier des charges).

Niveaux : « bloquant » empêche l'export ; « important » et « methodologique »
sont affichés et repris dans la section Limites ; « information » renseigne.
"""

from __future__ import annotations

from typing import Any

from statpfe.core.plan import classify, describe_item, power_gap
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

    _power_checks(project, options, add, passed)
    _plan_checks(project, options, analyses, add, passed)

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
    _ai_checks(project, options, analyses, add, passed)
    marks = project.copilot.marks()
    if marks:
        add("important", f"{len(marks)} élément(s) proposé(s) par l'IA ne sont pas encore validés",
            "Relisez et validez (ou corrigez) : " + ", ".join(m["label"] for m in marks[:8])
            + (" …" if len(marks) > 8 else "") + ". Les textes non relus sont signalés comme tels dans le rapport.")
    else:
        passed.append("Aucun élément proposé par l'IA n'attend de validation.")
    passed.append("Le rapport est présenté comme un document de travail à réviser, non comme un travail validé.")
    items.sort(key=lambda i: LEVEL_ORDER[i["level"]])
    return {"items": items, "passed": passed, "blocking": sum(i["level"] == "bloquant" for i in items)}


def _power_checks(project, options: dict[str, Any], add, passed: list[str]) -> None:
    ids = options.get("power") or []
    known = {c["id"] for c in project.power.list()}
    if any(i not in known for i in ids):
        add("bloquant", "Calcul de puissance introuvable",
            "Un calcul de puissance choisi a été supprimé. Mettez à jour la sélection.")
    ids = [i for i in ids if i in known]
    if not options["sections"].get("power"):
        return
    ok = 0
    for i in ids:
        calc = project.power.get(i)
        diffs = project.power.verify(i)
        if diffs:
            add("bloquant", f"Calcul de puissance « {calc['title']} » : résultat différent au recalcul",
                "Le résultat enregistré ne correspond plus au calcul refait avec cette version de STATPFE. Refaites "
                "et enregistrez de nouveau le calcul.")
        else:
            ok += 1
        if not calc["request"].get("effect_source") and calc["result"]["mode"] != "effect":
            add("methodologique", f"Calcul de puissance « {calc['title']} » : origine de l'effet non précisée",
                "Le rapport ne pourra pas justifier l'effet attendu retenu.")
    if ids and ok == len(ids):
        passed.append(f"Calculs de puissance refaits ({ok}) : identiques aux résultats enregistrés.")
    if not ids:
        add("information", "Aucun calcul de puissance inclus",
            "La section « Taille d'échantillon et puissance » contiendra un emplacement à compléter.")


def _plan_checks(project, options: dict[str, Any], analyses: list[dict[str, Any]], add, passed: list[str]) -> None:
    sections = options["sections"]
    if not (sections.get("plan") or sections["limits"] or sections["methodology"]):
        return
    plan = project.plan.get()
    plan["first_lock_at"] = project.plan.first_lock_at()
    inferential = [a for a in analyses if METHODS.get(a["method"], {}).get("family") != "describe"]
    locked = plan["locked"]
    if locked is None:
        if not inferential:
            return
        if plan["current"] is None:
            add("methodologique", "Aucun plan d'analyse",
                "Sans plan verrouillé, le rapport ne peut pas distinguer les analyses prévues des analyses ajoutées "
                "après consultation des données (écran « Plan d'analyse »).")
        else:
            add("methodologique", "Plan d'analyse non verrouillé",
                "Le plan est en brouillon : verrouillez-le pour que les analyses puissent y être rattachées.")
        return
    if plan["current"]["status"] == "brouillon":
        add("information", f"Version {plan['current']['version']} du plan en brouillon",
            f"Le rapport présente la version verrouillée {locked['version']}.")
    in_report = {((a.get("choice") or {}).get("plan") or {}).get("item") for a in analyses}
    for item in locked["content"]["analyses"]:
        if item["id"] not in in_report:
            add("methodologique", f"Analyse prévue {item['id']} absente du rapport",
                f"{describe_item(item)} : réalisez-la et rattachez-la au plan, ou expliquez son absence. Elle sera "
                "signalée dans les limites.")
    statuses = [classify(a, plan)["status"] for a in inferential]
    off = statuses.count("hors_plan") + statuses.count("avant_plan")
    if off:
        add("information", f"{off} analyse(s) inférentielle(s) hors du plan",
            "Elles seront présentées comme non prévues, ajoutées après consultation des données.")
    for a in analyses:
        link = (a.get("choice") or {}).get("plan") or {}
        if link.get("deviation"):
            add("information", f"« {a['title']} » : écart au plan justifié",
                "L'écart et sa raison figureront dans le rapport.", a["id"])
    first_analysis = min((a["created_at"] for a in project.analyses.list()), default=None)
    for v in plan["versions"]:
        if v["status"] == "verrouille" and v["version"] > 1 and first_analysis and v["locked_at"] > first_analysis:
            add("methodologique", f"Plan modifié après le début des analyses (version {v['version']})",
                "La modification et son motif figureront dans l'historique du plan et dans les limites.")
    calcs = {c["id"] for c in project.power.list()}
    for item in locked["content"]["analyses"]:
        cid = item.get("power_calc")
        if cid not in calcs:
            continue
        res = project.power.get(cid)["result"]
        if res["mode"] != "sample_size":
            continue
        for a in analyses:
            if ((a.get("choice") or {}).get("plan") or {}).get("item") == item["id"]:
                n = a["result"].get("n_used")
                gap = power_gap(res, n) if n is not None else None
                if gap:
                    add("important", f"« {a['title']} » : effectif inférieur au calcul de puissance",
                        f"{gap} (analyse prévue {item['id']}).", a["id"])
    passed.append(f"Plan d'analyse verrouillé (version {locked['version']}) : les analyses prévues et les analyses "
                  "hors plan sont distinguées dans le rapport.")


def _ai_checks(project, options: dict[str, Any], analyses: list[dict[str, Any]], add, passed: list[str]) -> None:
    from statpfe.ai import context as ai_context
    from statpfe.ai import guard

    texts = [t for a in analyses for t in project.ai_texts.list(a["id"])]
    kept = [t for t in texts if t["status"] == "retenu"]
    pending = [t for t in texts if t["status"] == "proposition"]
    if pending:
        add("information", f"{len(pending)} proposition(s) de l'IA non relue(s)",
            "Elles ne figurent pas dans le rapport. Relisez-les et retenez-les, ou écartez-les, depuis le résultat de "
            "l'analyse.")
    if kept and not options.get("ai_texts", True):
        add("information", "Textes de l'IA non inclus",
            f"{len(kept)} texte(s) retenu(s) après relecture ne seront pas inclus (option désactivée).")
    if not kept or not options.get("ai_texts", True):
        passed.append("Aucun texte rédigé avec l'aide d'une IA n'est inclus : les lectures des résultats sont "
                      "produites par des règles fixes et signalées comme telles.")
        return
    by_id = {a["id"]: a for a in analyses}
    problems = 0
    for t in kept:
        a = by_id[t["analysis_id"]]
        name = f"« {a['title']} »"
        checks = guard.check(t["text"], t["context"])
        if checks["blocking"]:
            problems += 1
            add("bloquant", f"{name} : texte de l'IA non vérifiable",
                "Le texte retenu contient des nombres absents des résultats calculés. Corrigez-le ou écartez-le.",
                a["id"])
            continue
        try:
            now = ai_context.build(project, a)
        except Exception as exc:  # noqa: BLE001 - variable devenue identifiante, par exemple
            problems += 1
            add("important", f"{name} : texte de l'IA à revoir", getattr(exc, "message", str(exc)), a["id"])
            continue
        if now["hash"] != t["context_hash"]:
            problems += 1
            add("important", f"{name} : contexte modifié depuis la proposition de l'IA",
                "Les libellés ou informations de l'analyse transmis à l'IA ont changé depuis la rédaction du texte "
                "retenu : relisez-le.", a["id"])
    if not problems:
        passed.append(f"{len(kept)} texte(s) rédigé(s) avec l'aide de l'IA, relu(s) et retenu(s) par l'auteur, "
                      "sont signalés comme tels dans le rapport ; chacun de leurs nombres figure dans les résultats "
                      "calculés.")
