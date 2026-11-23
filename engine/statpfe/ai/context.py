"""Construction du contexte transmis au modèle, contrôlé et minimisé.

Seuls des résultats déjà calculés sont transmis : méthode, noms et libellés des variables
analysées, effectifs, indicateurs, tableaux de synthèse, descriptions des figures,
diagnostics et lecture automatique. Jamais de ligne de données brutes, jamais de
variable signalée comme identifiante, jamais la note libre de l'utilisateur.
L'utilisateur peut afficher exactement ce texte avant l'envoi.
"""

from __future__ import annotations

import hashlib
from typing import Any

from statpfe.data.types import LEVELS
from statpfe.errors import ValidationError
from statpfe.report import charts
from statpfe.report.fmt import cell, stat

MAX_TABLE_ROWS = 30
MAX_TABLES = 6
MAX_CONTEXT = 12_000


def _variables_lines(project, a: dict[str, Any]) -> list[str]:
    names = a["result"].get("variables") or []
    try:
        variables = {v.name: v for v in project.data._variables(a["dataset_id"])} if a.get("dataset_id") else {}
    except Exception:  # noqa: BLE001 - jeu supprimé : on garde les seuls noms
        variables = {}
    lines = []
    for name in names:
        v = variables.get(name)
        if v is not None and (v.potential_identifier or v.role == "identifiant"):
            raise ValidationError(
                f"« {name} » est signalée comme identifiant ou donnée personnelle : les résultats de cette analyse "
                "ne sont pas transmis à l'IA.")
        if v is None:
            lines.append(f"- {name}")
            continue
        extra = [x for x in (v.label, f"unité : {v.unit}" if v.unit else "") if x]
        level = LEVELS.get(v.level, v.level).lower()
        lines.append(f"- {name} ({level}{', ' + ', '.join(extra) if extra else ''})")
    return lines


def build(project, a: dict[str, Any]) -> dict[str, Any]:
    """Renvoie le texte exact transmis au modèle et la liste de ce qu'il contient."""
    r = a["result"]
    c = a.get("choice") or {}
    sections: list[tuple[str, list[str]]] = []
    head = [f"Méthode : {a['method_label']}.", f"Titre de l'analyse : {a['title']}."]
    if r.get("n_used") is not None:
        head.append(f"Observations utilisées : n = {r['n_used']}.")
    if r.get("missing") and r["missing"].get("text"):
        head.append(r["missing"]["text"])
    if c.get("purpose_label"):
        head.append(f"Nature de l'analyse : {c['purpose_label'].lower()}.")
    if c.get("hypothesis_text"):
        head.append(f"Hypothèse de recherche mise à l'épreuve : {c['hypothesis_text']}")
    link = c.get("plan") or {}
    if link.get("item"):
        head.append(f"Analyse prévue au plan d'analyse ({link['item']})"
                    + (" avec un écart justifié." if link.get("deviation") else "."))
    sections.append(("Analyse", head))
    sections.append(("Variables analysées", _variables_lines(project, a)))
    summary = r.get("summary") or []
    if summary:
        sections.append(("Résultats principaux", [
            f"- {s['label']} : {stat(s.get('value'), s.get('kind', 'value'), s.get('digits', 3))}" for s in summary]))
    tables = r.get("tables") or []
    for t in tables[:MAX_TABLES]:
        kinds = t.get("kinds") or []
        lines = [" | ".join(str(x) for x in t["columns"])]
        for row in t["rows"][:MAX_TABLE_ROWS]:
            lines.append(" | ".join(cell(v, kinds[j] if j < len(kinds) else None) for j, v in enumerate(row)))
        if len(t["rows"]) > MAX_TABLE_ROWS:
            lines.append(f"(tableau tronqué : {MAX_TABLE_ROWS} premières lignes sur {len(t['rows'])})")
        if t.get("note"):
            lines.append(f"Note : {t['note']}")
        sections.append((f"Tableau : {t['title']}", lines))
    figures = [f"- {ch['title']} : {charts.describe(ch)}" for ch in r.get("charts") or []]
    if figures:
        sections.append(("Figures", figures))
    diags = [f"- [{d['level']}] {d['title']}" + (f" {d['detail']}" if d.get("detail") else "")
             for d in r.get("diagnostics") or []]
    if diags:
        sections.append(("Diagnostics calculés par le logiciel", diags))
    if r.get("interpretation"):
        sections.append(("Lecture automatique du logiciel (déterministe)", list(r["interpretation"])))
    text = "\n\n".join(f"## {title}\n" + "\n".join(lines) for title, lines in sections)
    truncated = False
    if len(text) > MAX_CONTEXT:
        text, truncated = text[:MAX_CONTEXT] + "\n(contexte tronqué)", True
    return {
        "text": text,
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "sections": [t for t, _ in sections],
        "excluded": [
            "Aucune ligne de données brutes (seulement les résultats déjà calculés).",
            "Aucune variable signalée comme identifiante ou donnée personnelle.",
            "Ni la note libre de l'analyse, ni le titre de l'étude, ni les noms des auteurs.",
        ],
        "truncated": truncated,
        "chars": len(text),
    }
