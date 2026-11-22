"""Diagnostic de qualité d'une version des données (manquants, invalides, doublons…)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from statpfe.data.types import ConversionReport, Variable

HIGH_MISSING = 0.2


def quality_report(df: pd.DataFrame, variables: list[Variable],
                   conversions: dict[str, ConversionReport]) -> dict[str, Any]:
    n = len(df)
    per_variable = []
    issues: list[dict[str, Any]] = []
    for var in variables:
        col = df[var.key]
        missing = int(col.isna().sum())
        distinct = int(col.nunique(dropna=True))
        conv = conversions.get(var.key)
        item = {
            "key": var.key,
            "name": var.name,
            "missing": missing,
            "missing_rate": (missing / n) if n else 0.0,
            "distinct": distinct,
            "invalid": conv.invalid if conv else 0,
            "invalid_examples": conv.invalid_examples if conv else [],
            "declared_missing": conv.declared_missing if conv else 0,
            "constant": n > 0 and distinct <= 1,
        }
        per_variable.append(item)
        if item["invalid"]:
            examples = ", ".join(f"« {e} »" for e in item["invalid_examples"])
            issues.append(_issue(
                "important", var,
                f"{item['invalid']} valeur(s) ne correspondent pas au type « {var.type} » et sont traitées "
                f"comme manquantes (ex. {examples}). S'il s'agit de codes (ex. « NSP »), déclarez-les comme "
                "valeurs manquantes ; sinon corrigez le type.",
            ))
        if n and missing / n >= HIGH_MISSING:
            issues.append(_issue(
                "important", var,
                f"{missing / n:.0%} de valeurs manquantes. Les analyses utilisant cette variable porteront "
                "sur un effectif réduit et peuvent être biaisées si les absences ne sont pas aléatoires.",
            ))
        if item["constant"] and n:
            issues.append(_issue("methodologique", var,
                                 "Variable constante (une seule valeur) : elle n'apporte aucune information pour les analyses."))
        if var.potential_identifier:
            issues.append(_issue("information", var,
                                 "Identifiant ou donnée personnelle potentielle : masquée dans l'aperçu par défaut. "
                                 + " ".join(var.identifier_reasons)))
        if var.type == "numerique" and var.level == "continu" and 2 <= distinct <= 7 and n >= 20:
            issues.append(_issue("suggestion", var,
                                 f"Seulement {distinct} valeurs différentes : s'agit-il d'une échelle (ex. Likert) ? "
                                 "Si oui, indiquez le niveau « Qualitative ordinale »."))
    duplicates = int(df.duplicated(keep="first").sum()) if n else 0
    if duplicates:
        issues.insert(0, {
            "level": "important", "variable": None, "variable_name": None,
            "message": f"{duplicates} ligne(s) sont des doublons exacts d'une ligne précédente. "
                       "Vérifiez s'il s'agit de réponses saisies deux fois avant de les supprimer.",
        })
    if n == 0:
        issues.insert(0, {"level": "bloquant", "variable": None, "variable_name": None,
                          "message": "Cette version ne contient aucune ligne."})
    return {
        "rows": n,
        "columns": len(variables),
        "duplicates": duplicates,
        "complete_rows": int(df.notna().all(axis=1).sum()) if n else 0,
        "variables": per_variable,
        "issues": issues,
    }


def _issue(level: str, var: Variable, message: str) -> dict[str, Any]:
    return {"level": level, "variable": var.key, "variable_name": var.name, "message": message}
