"""Modèles de rapport et validation des options d'export."""

from __future__ import annotations

from typing import Any

from statpfe.errors import ValidationError

SECTIONS: dict[str, str] = {
    "cover": "Page de garde",
    "toc": "Sommaire",
    "introduction": "Présentation de l'étude (problématique, objectifs)",
    "hypotheses": "Hypothèses",
    "plan": "Plan d'analyse (prévu avant l'analyse, historique des versions)",
    "population": "Population et échantillonnage",
    "power": "Taille d'échantillon et puissance",
    "variables": "Description des variables",
    "preparation": "Préparation des données",
    "methodology": "Méthodologie statistique",
    "descriptive": "Statistiques descriptives",
    "inferential": "Analyses inférentielles",
    "discussion": "Discussion (à rédiger)",
    "limits": "Limites",
    "conclusion": "Conclusion (à rédiger)",
    "annex_traceability": "Annexe : traçabilité des analyses",
    "annex_journal": "Annexe : journal méthodologique",
}

_ALL = set(SECTIONS)
_NO_ANNEX_JOURNAL = _ALL - {"annex_journal"}

TEMPLATES: dict[str, dict[str, Any]] = {
    "pfe": {"label": "Projet de fin d'études (PFE)", "document": "Projet de fin d'études",
            "sections": _NO_ANNEX_JOURNAL},
    "memoire": {"label": "Mémoire de master", "document": "Mémoire de master", "sections": _NO_ANNEX_JOURNAL},
    "these": {"label": "Thèse de doctorat", "document": "Thèse de doctorat", "sections": _ALL},
    "article": {"label": "Article scientifique", "document": "Article",
                "sections": _ALL - {"cover", "toc", "annex_journal", "population", "preparation"}},  # plan, puissance gardés
    "enquete": {"label": "Rapport d'enquête", "document": "Rapport d'enquête",
                "sections": _NO_ANNEX_JOURNAL - {"hypotheses", "discussion"}},
}

COVER_FIELDS: dict[str, str] = {
    "authors": "Auteur(s)",
    "supervisor": "Encadrant(e) ou directeur(trice)",
    "institution": "Établissement",
    "program": "Filière, spécialité ou laboratoire",
    "year": "Année universitaire",
    "city": "Lieu",
}
COVER_MAX = 300
FORMATS = {"docx": "Word (.docx)", "pdf": "PDF"}
MAX_ANALYSES = 200
MAX_POWER = 50


def templates() -> dict[str, Any]:
    return {
        "templates": [{"key": k, "label": t["label"], "document": t["document"],
                       "sections": [s for s in SECTIONS if s in t["sections"]]} for k, t in TEMPLATES.items()],
        "sections": [{"key": k, "label": v} for k, v in SECTIONS.items()],
        "cover_fields": [{"key": k, "label": v} for k, v in COVER_FIELDS.items()],
        "formats": [{"key": k, "label": v} for k, v in FORMATS.items()],
    }


def default_options(analysis_ids: list[int], power_ids: list[int] | None = None) -> dict[str, Any]:
    return {
        "template": "pfe",
        "cover": {k: "" for k in COVER_FIELDS},
        "sections": {k: k in TEMPLATES["pfe"]["sections"] for k in SECTIONS},
        "analyses": analysis_ids,
        "power": power_ids or [],
        "figures": True,
    }


def clean_options(raw: Any) -> dict[str, Any]:
    """Valide les options reçues de l'interface (données non fiables)."""
    if not isinstance(raw, dict):
        raise ValidationError("Options du rapport invalides.")
    template = raw.get("template", "pfe")
    if template not in TEMPLATES:
        raise ValidationError("Modèle de rapport inconnu.")
    cover_in = raw.get("cover") or {}
    if not isinstance(cover_in, dict) or set(cover_in) - set(COVER_FIELDS):
        raise ValidationError("Champs de la page de garde invalides.")
    cover = {}
    for k in COVER_FIELDS:
        v = cover_in.get(k, "")
        if not isinstance(v, str) or len(v) > COVER_MAX:
            raise ValidationError(f"« {COVER_FIELDS[k]} » : texte invalide ou trop long ({COVER_MAX} caractères au "
                                  "plus).")
        cover[k] = v.strip()
    sections_in = raw.get("sections")
    if sections_in is None:
        sections = {k: k in TEMPLATES[template]["sections"] for k in SECTIONS}
    else:
        if not isinstance(sections_in, dict) or set(sections_in) - set(SECTIONS) \
                or not all(isinstance(v, bool) for v in sections_in.values()):
            raise ValidationError("Sections du rapport invalides.")
        # Section absente (options enregistrées par une version plus ancienne) : valeur du modèle.
        sections = {k: bool(sections_in.get(k, k in TEMPLATES[template]["sections"])) for k in SECTIONS}
    analyses = raw.get("analyses", [])
    if not isinstance(analyses, list) or len(analyses) > MAX_ANALYSES \
            or not all(isinstance(a, int) and not isinstance(a, bool) for a in analyses):
        raise ValidationError("Liste des analyses invalide.")
    if len(set(analyses)) != len(analyses):
        raise ValidationError("Une analyse figure deux fois dans le rapport.")
    power = raw.get("power")
    if power is not None:
        if not isinstance(power, list) or len(power) > MAX_POWER \
                or not all(isinstance(a, int) and not isinstance(a, bool) for a in power) or len(set(power)) != len(power):
            raise ValidationError("Liste des calculs de puissance invalide.")
    figures = raw.get("figures", True)
    if not isinstance(figures, bool):
        raise ValidationError("Option « figures » invalide.")
    return {"template": template, "cover": cover, "sections": sections, "analyses": analyses, "power": power,
            "figures": figures}
