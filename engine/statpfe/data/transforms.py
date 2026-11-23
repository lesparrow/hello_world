"""Transformations reproductibles appliquées à une version de travail.

Une version = la liste ordonnée de ses étapes, rejouée à partir des données
d'origine. Supprimer une étape et rejouer les suivantes rend toute
transformation réversible ; l'original n'est jamais modifié.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from statpfe.data.types import Variable, parse_bool, parse_number
from statpfe.errors import ValidationError

OPERATIONS = {
    "remove_duplicates": "Supprimer les doublons",
    "filter_rows": "Filtrer les lignes",
    "drop_missing": "Exclure les lignes avec valeurs manquantes",
    "recode": "Recoder ou regrouper des modalités",
    "compute": "Créer une variable calculée",
}
OPERATORS = {
    "eq": "est égal à", "ne": "est différent de", "lt": "est inférieur à", "le": "est inférieur ou égal à",
    "gt": "est supérieur à", "ge": "est supérieur ou égal à", "in": "fait partie de",
    "not_in": "ne fait pas partie de", "missing": "est manquant", "not_missing": "n'est pas manquant",
}
ORDER_OPERATORS = {"lt", "le", "gt", "ge"}
FUNCTIONS = {
    "log": "logarithme népérien", "log10": "logarithme décimal",
    "zscore": "standardisation (score z)", "minmax": "normalisation entre 0 et 1",
}
_NAME = re.compile(r"^[^\x00-\x1f]{1,64}$")
MAX_STEPS = 100


@dataclass
class StepResult:
    rows_before: int
    rows_after: int
    description: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"rows_before": self.rows_before, "rows_after": self.rows_after,
                "description": self.description, "warnings": self.warnings}


def apply_step(df: pd.DataFrame, variables: list[Variable], step: Any) -> tuple[pd.DataFrame, list[Variable], StepResult]:
    if not isinstance(step, dict) or step.get("op") not in OPERATIONS:
        raise ValidationError("Transformation inconnue.")
    by_key = {v.key: v for v in variables}
    op = step["op"]
    before = len(df)
    warnings: list[str] = []

    if op == "remove_duplicates":
        keys = _keys(step.get("variables") or [], by_key, allow_empty=True)
        subset = keys or [v.key for v in variables if v.key in df.columns]
        out = df.drop_duplicates(subset=subset, keep="first")
        scope = "toutes les variables" if not keys else ", ".join(by_key[k].name for k in keys)
        desc = f"Suppression des lignes en double (comparaison sur {scope}), première occurrence conservée"
        return out, variables, StepResult(before, len(out), desc)

    if op == "drop_missing":
        keys = _keys(step.get("variables"), by_key)
        out = df.dropna(subset=keys)
        desc = "Exclusion des lignes où au moins une valeur manque parmi : " + ", ".join(by_key[k].name for k in keys)
        return out, variables, StepResult(before, len(out), desc)

    if op == "filter_rows":
        key = _key(step.get("variable"), by_key)
        var = by_key[key]
        operator = step.get("operator")
        if operator not in OPERATORS:
            raise ValidationError("Opérateur de filtre inconnu.")
        col = df[key]
        if operator == "missing":
            mask = col.isna()
            shown = ""
        elif operator == "not_missing":
            mask = col.notna()
            shown = ""
        else:
            if operator in ORDER_OPERATORS and var.type in ("texte", "booleen"):
                raise ValidationError("Cet opérateur ne s'applique qu'aux variables numériques ou aux dates.")
            if operator in ("in", "not_in"):
                raw_values = step.get("values")
                if not isinstance(raw_values, list) or not raw_values:
                    raise ValidationError("Choisissez au moins une valeur.")
                values = [_coerce(v, var) for v in raw_values]
                mask = col.isin(values)
                if operator == "not_in":
                    mask = ~mask & col.notna()
                shown = " " + ", ".join(str(v) for v in raw_values)
            else:
                value = _coerce(step.get("value"), var)
                comparators = {"eq": col.eq, "ne": col.ne, "lt": col.lt, "le": col.le, "gt": col.gt, "ge": col.ge}
                mask = comparators[operator](value).fillna(False).astype(bool) & col.notna()
                shown = f" {step.get('value')}"
        out = df[mask.to_numpy(dtype=bool)]
        desc = f"Conservation des lignes où « {var.name} » {OPERATORS[operator]}{shown}"
        if len(out) == 0:
            warnings.append("Aucune ligne ne correspond à ce filtre.")
        return out, variables, StepResult(before, len(out), desc, warnings)

    if op == "recode":
        key = _key(step.get("variable"), by_key)
        var = by_key[key]
        new_name = _new_name(step.get("new_name"), variables)
        mapping = step.get("mapping")
        if not isinstance(mapping, dict) or not mapping:
            raise ValidationError("Indiquez au moins une correspondance de recodage.")
        for old, new in mapping.items():
            if not isinstance(old, str) or not (new is None or isinstance(new, str)):
                raise ValidationError("Correspondance de recodage invalide.")
        as_text = df[key].map(lambda x: None if _isna(x) else _display(x))
        recoded = as_text.map(lambda s: mapping.get(s, s) if s is not None else None)
        recoded = recoded.map(lambda s: None if s is None or str(s).strip() == "" else str(s).strip())
        out = df.copy()
        out[new_name] = recoded.astype(object)
        cats = sorted({c for c in recoded.dropna().unique()}, key=str.casefold)
        from statpfe.data.types import Category  # import local : évite un cycle
        new_var = Variable(key=new_name, name=new_name, type="texte", level=var.level if var.level != "continu" else "nominal",
                           label=f"Recodage de {var.name}", categories=[Category(c) for c in cats][:50],
                           computed=True, detected_type="texte")
        unmapped = sorted(set(as_text.dropna().unique()) - set(mapping))
        if unmapped:
            warnings.append(f"{len(unmapped)} valeur(s) non recodée(s) conservée(s) telles quelles.")
        desc = f"Création de « {new_name} » par recodage de « {var.name} » ({len(mapping)} correspondance(s))"
        return out, variables + [new_var], StepResult(before, len(out), desc, warnings)

    # compute
    key = _key(step.get("variable"), by_key)
    var = by_key[key]
    if var.type != "numerique":
        raise ValidationError("Cette transformation ne s'applique qu'à une variable numérique.")
    function = step.get("function")
    if function not in FUNCTIONS:
        raise ValidationError("Fonction de calcul inconnue.")
    new_name = _new_name(step.get("new_name"), variables)
    x = df[key].astype("float64")
    if function in ("log", "log10"):
        bad = int(((x <= 0) & x.notna()).sum())
        if bad:
            warnings.append(f"{bad} valeur(s) nulles ou négatives : leur logarithme n'existe pas, elles deviennent manquantes.")
        positive = x.where(x > 0)
        result = np.log(positive) if function == "log" else np.log10(positive)
    elif function == "zscore":
        sd = x.std(ddof=1)
        if not np.isfinite(sd) or sd == 0:
            raise ValidationError("Standardisation impossible : la variable est constante ou n'a pas assez de valeurs.")
        result = (x - x.mean()) / sd
    else:
        lo, hi = x.min(), x.max()
        if not np.isfinite(hi - lo) or hi == lo:
            raise ValidationError("Normalisation impossible : la variable est constante ou vide.")
        result = (x - lo) / (hi - lo)
    out = df.copy()
    out[new_name] = result.astype("float64")
    new_var = Variable(key=new_name, name=new_name, type="numerique", level="continu",
                       label=f"{FUNCTIONS[function].capitalize()} de {var.name}", unit="" if function != "minmax" else "",
                       computed=True, detected_type="numerique")
    note = " (moyenne et écart-type calculés sur cette version des données)" if function == "zscore" else ""
    desc = f"Création de « {new_name} » : {FUNCTIONS[function]} de « {var.name} »{note}"
    return out, variables + [new_var], StepResult(before, len(out), desc, warnings)


def apply_steps(df: pd.DataFrame, variables: list[Variable], steps: list[dict]) -> tuple[pd.DataFrame, list[Variable], list[StepResult]]:
    results = []
    for step in steps:
        df, variables, result = apply_step(df, variables, step)
        results.append(result)
    return df, variables, results


# ---------------------------------------------------------------------- utilitaires
def _keys(value: Any, by_key: dict[str, Variable], allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValidationError("Choisissez au moins une variable.")
    return [_key(k, by_key) for k in value]


def _key(value: Any, by_key: dict[str, Variable]) -> str:
    if not isinstance(value, str) or value not in by_key:
        raise ValidationError("Variable inconnue dans cette version des données.")
    return value


def _new_name(value: Any, variables: list[Variable]) -> str:
    if not isinstance(value, str) or not _NAME.match(value.strip()):
        raise ValidationError("Le nom de la nouvelle variable est invalide (1 à 64 caractères).")
    value = value.strip()
    taken = {v.key.casefold() for v in variables} | {v.name.casefold() for v in variables}
    if value.casefold() in taken:
        raise ValidationError(f"Une variable s'appelle déjà « {value} ».")
    return value


def _coerce(value: Any, var: Variable) -> Any:
    if not isinstance(value, (str, int, float, bool)) or isinstance(value, bool) and var.type != "booleen":
        raise ValidationError("Valeur de filtre invalide.")
    text = str(value)
    if var.type == "numerique":
        number = parse_number(text)
        if number is None:
            raise ValidationError(f"« {text} » n'est pas un nombre.")
        return number
    if var.type == "booleen":
        b = value if isinstance(value, bool) else parse_bool(text)
        if b is None:
            raise ValidationError("Valeur attendue : oui ou non.")
        return b
    if var.type == "date":
        d = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
        if pd.isna(d):
            raise ValidationError("Date attendue au format AAAA-MM-JJ.")
        return d
    return text


def _isna(x: Any) -> bool:
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def _display(x: Any) -> str:
    if isinstance(x, (bool, np.bool_)):
        return "oui" if x else "non"
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    if isinstance(x, pd.Timestamp):
        return x.date().isoformat() if x == x.normalize() else x.isoformat(sep=" ")
    return str(x)


display_value = _display
