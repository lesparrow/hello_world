"""Outils communs aux analyses : sélection des variables, valeurs manquantes,
mise en forme française des nombres et structure des résultats.

Les résultats sont des dictionnaires JSON simples. Les nombres sont toujours
transmis bruts (non arrondis) ; l'arrondi n'intervient que dans le texte
d'interprétation et à l'affichage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from statpfe.data.transforms import display_value
from statpfe.data.types import Variable, _natural_key
from statpfe.errors import ValidationError

EXCLUDED_ROLES = {"identifiant": "identifiant", "exclue": "exclue des analyses"}
ALTERNATIVES = {"two-sided": "bilatéral", "less": "unilatéral (inférieur)", "greater": "unilatéral (supérieur)"}
CONF_LEVELS = (0.90, 0.95, 0.99)
MAX_GROUP_LEVELS = 50


class AnalysisError(ValidationError):
    """Analyse impossible avec ces données ou ces paramètres (message pour l'utilisateur)."""

    code = "analyse_impossible"


@dataclass
class Context:
    df: pd.DataFrame
    variables: list[Variable]
    params: dict[str, Any]
    by_key: dict[str, Variable] = field(init=False)

    def __post_init__(self) -> None:
        self.by_key = {v.key: v for v in self.variables}

    # ------------------------------------------------------------ paramètres
    def var(self, name: str, *, label: str, types: tuple[str, ...] | None = None) -> Variable:
        key = self.params.get(name)
        if not isinstance(key, str) or key not in self.by_key:
            raise ValidationError(f"Choisissez la variable « {label} ».")
        return self._check(self.by_key[key], types)

    @staticmethod
    def _check(v: Variable, types: tuple[str, ...] | None) -> Variable:
        if v.role in EXCLUDED_ROLES:
            raise AnalysisError(
                f"« {v.name} » a le rôle « {EXCLUDED_ROLES[v.role]} » dans le dictionnaire : elle ne peut pas "
                f"être analysée. Modifiez son rôle si c'est une erreur.")
        if v.potential_identifier:
            raise AnalysisError(
                f"« {v.name} » est signalée comme identifiant potentiel (donnée personnelle) et reste masquée. Si "
                "ce n'est pas une donnée personnelle, retirez ce signalement dans le dictionnaire des variables.")
        if types and v.type not in types:
            allowed = " ou ".join({"numerique": "numérique", "texte": "texte", "booleen": "oui/non",
                                   "date": "date"}[t] for t in types)
            raise AnalysisError(f"« {v.name} » doit être de type {allowed} pour cette analyse.")
        return v

    def var_list(self, name: str, *, label: str, types: tuple[str, ...] | None = None,
                 max_count: int = 30) -> list[Variable]:
        keys = self.params.get(name)
        if not isinstance(keys, list) or not keys:
            raise ValidationError(f"Choisissez au moins une variable ({label}).")
        if len(keys) > max_count:
            raise ValidationError(f"Au plus {max_count} variables à la fois.")
        if len(set(keys)) != len(keys):
            raise ValidationError("Une variable est choisie deux fois.")
        if not all(isinstance(k, str) and k in self.by_key for k in keys):
            raise ValidationError(f"Variable inconnue ({label}).")
        return [self._check(self.by_key[k], types) for k in keys]

    def optional_var(self, name: str, *, label: str) -> Variable | None:
        if self.params.get(name) in (None, ""):
            return None
        return self.var(name, label=label)

    def alternative(self) -> str:
        alt = self.params.get("alternative", "two-sided")
        if alt not in ALTERNATIVES:
            raise ValidationError("Hypothèse alternative inconnue.")
        return alt

    def conf_level(self) -> float:
        level = self.params.get("conf_level", 0.95)
        if not isinstance(level, (int, float)) or isinstance(level, bool) or float(level) not in CONF_LEVELS:
            raise ValidationError("Niveau de confiance : 90 %, 95 % ou 99 %.")
        return float(level)

    def alpha(self) -> float:
        return round(1 - self.conf_level(), 10)

    def flag(self, name: str, default: bool) -> bool:
        value = self.params.get(name, default)
        if not isinstance(value, bool):
            raise ValidationError(f"Paramètre « {name} » invalide.")
        return value


# ------------------------------------------------------------------ groupes et modalités
def as_labels(series: pd.Series) -> pd.Series:
    """Valeurs d'une variable qualitative sous forme de textes (clé de modalité)."""
    return series.map(lambda x: None if _isna(x) else display_value(x))


def ordered_levels(var: Variable, present: list[str]) -> list[str]:
    declared = [c.value for c in var.categories]
    known = [c for c in declared if c in present]
    others = sorted((c for c in present if c not in declared), key=_natural_key)
    return known + others


def level_label(var: Variable, value: str) -> str:
    for c in var.categories:
        if c.value == value and c.label:
            return c.label
    return value


def _isna(x: Any) -> bool:
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


# ------------------------------------------------------------------ valeurs manquantes
def missing_note(total: int, used: int, names: list[str]) -> dict[str, Any]:
    excluded = total - used
    joined = ", ".join(f"« {n} »" for n in names)
    text = (f"Analyse des observations complètes pour {joined} : {used} ligne(s) utilisée(s) sur {total}"
            + (f", {excluded} exclue(s) en raison de valeurs manquantes." if excluded else
               ", aucune exclusion."))
    return {"strategy": "cas_complets", "total": total, "used": used, "excluded": excluded, "text": text}


# ------------------------------------------------------------------ nombres
def num(x: Any) -> float | None:
    """Nombre JSON (None si non fini)."""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def fr(x: float | None, digits: int = 2) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "non calculable"
    s = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−") if s.startswith("-") else s


def fr_p(p: float | None) -> str:
    if p is None:
        return "p non calculable"
    if p < 0.001:
        return "p < 0,001"
    return f"p = {fr(p, 3)}"


def fr_pct(x: float) -> str:
    return f"{fr(100 * x, 0 if abs(100 * x - round(100 * x)) < 1e-9 else 1)} %"


# ------------------------------------------------------------------ résultat
class Result:
    def __init__(self, method: str, title: str):
        self.method = method
        self.title = title
        self.summary: list[dict[str, Any]] = []
        self.tables: list[dict[str, Any]] = []
        self.charts: list[dict[str, Any]] = []
        self.diagnostics: list[dict[str, Any]] = []
        self.interpretation: list[str] = []
        self.missing: dict[str, Any] | None = None
        self.n_used: int | None = None
        self.variables: list[str] = []
        self.values: dict[str, Any] = {}  # valeurs brutes clés, utilisées pour la reproduction et la validation

    def stat(self, key: str, label: str, value: Any, kind: str = "value", digits: int = 3) -> None:
        if isinstance(value, (float, np.floating)) and math.isinf(value):
            v: Any = "+∞" if value > 0 else "−∞"
        elif isinstance(value, (int, float, np.floating, np.integer)) and not isinstance(value, bool):
            v = num(value)
        else:
            v = value
        self.summary.append({"key": key, "label": label, "value": v, "kind": kind, "digits": digits})
        self.values[key] = v

    def table(self, title: str, columns: list[str], rows: list[list[Any]], note: str = "",
              kinds: list[str] | None = None) -> None:
        self.tables.append({"title": title, "columns": columns, "rows": [[_cell(c) for c in r] for r in rows],
                            "note": note, "kinds": kinds or []})

    def chart(self, type_: str, title: str, data: dict[str, Any]) -> None:
        self.charts.append({"type": type_, "title": title, "data": data})

    def diag(self, level: str, title: str, detail: str = "") -> None:
        self.diagnostics.append({"level": level, "title": title, "detail": detail})

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method, "title": self.title, "variables": self.variables, "n_used": self.n_used,
            "missing": self.missing, "summary": self.summary, "tables": self.tables, "charts": self.charts,
            "diagnostics": self.diagnostics, "interpretation": self.interpretation, "values": _finite(self.values),
        }


def _finite(value: Any) -> Any:
    """Remplace récursivement NaN et infinis par None (JSON strict) et convertit les types numpy."""
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return num(value)
    return value


def _cell(c: Any) -> Any:
    if isinstance(c, (bool, np.bool_)):
        return bool(c)
    if isinstance(c, (np.integer,)):
        return int(c)
    if isinstance(c, (float, np.floating)):
        return num(c)
    return c


DIAG_LEVELS = ("bloquant", "important", "methodologique", "information")
