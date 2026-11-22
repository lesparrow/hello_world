"""Dictionnaire des variables : détection des types, validation et conversion.

Chaque colonne du fichier source garde une clé stable (`key`, le nom d'origine).
L'utilisateur peut modifier le nom affiché, le libellé, le type, le niveau de
mesure, le rôle, l'unité, les codes de valeurs manquantes et les modalités.
La conversion des textes bruts en valeurs typées est entièrement déterminée par
ce dictionnaire : elle est donc reproductible.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from statpfe.errors import ValidationError

TYPES = {"numerique": "Numérique", "texte": "Texte", "booleen": "Oui/Non", "date": "Date"}
LEVELS = {"nominal": "Qualitative nominale", "ordinal": "Qualitative ordinale", "continu": "Quantitative"}
ROLES = {
    "non_defini": "Non défini",
    "a_expliquer": "Variable à expliquer",
    "explicative": "Variable explicative",
    "identifiant": "Identifiant",
    "exclue": "Exclue des analyses",
}
ALLOWED_LEVELS = {
    "numerique": {"continu", "ordinal", "nominal"},
    "texte": {"nominal", "ordinal"},
    "booleen": {"nominal"},
    "date": {"continu"},
}
DETECTION_THRESHOLD = 0.9
MAX_CATEGORIES = 50
CATEGORY_DETECTION_MAX = 12

TRUE_WORDS = {"oui", "vrai", "true", "yes", "o", "y"}
FALSE_WORDS = {"non", "faux", "false", "no", "n"}

_NUM_PLAIN = re.compile(r"^[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?$")
_NUM_EU_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(\.\d{3})+(,\d+)?$")
_SPACES = re.compile(r"[\s  ]")
DATE_FORMATS = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y"]

_ID_NAME = re.compile(
    r"(^|[_\s-])(nom|prenom|prénom|name|surname|e-?mail|mail|courriel|tel|tél|telephone|téléphone|"
    r"phone|mobile|gsm|adresse|address|cin|cne|cni|matricule|passeport|ip)([_\s-]|$)",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE = re.compile(r"^\+?[\d\s().-]{8,}$")


# ---------------------------------------------------------------------- conversion
def parse_number(text: str) -> float | None:
    s = _SPACES.sub("", text)
    if _NUM_EU_THOUSANDS.match(s):
        s = s.replace(".", "").replace(",", ".")
    elif _NUM_PLAIN.match(s):
        s = s.replace(",", ".")
    else:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    return value if np.isfinite(value) else None


def parse_bool(text: str) -> bool | None:
    t = text.strip().casefold()
    if t in TRUE_WORDS:
        return True
    if t in FALSE_WORDS:
        return False
    return None


def best_date_format(values: pd.Series) -> tuple[str | None, int]:
    best, best_count = None, 0
    for fmt in DATE_FORMATS:
        count = int(pd.to_datetime(values, format=fmt, errors="coerce").notna().sum())
        if count > best_count:
            best, best_count = fmt, count
    return best, best_count


# ---------------------------------------------------------------------- dictionnaire
@dataclass
class Category:
    value: str
    label: str = ""


@dataclass
class Variable:
    key: str
    name: str
    type: str
    level: str
    role: str = "non_defini"
    label: str = ""
    unit: str = ""
    missing_codes: list[str] = field(default_factory=list)
    categories: list[Category] = field(default_factory=list)
    potential_identifier: bool = False
    identifier_reasons: list[str] = field(default_factory=list)
    detected_type: str = ""
    computed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Variable":
        d = dict(d)
        d["categories"] = [Category(**c) for c in d.get("categories", [])]
        return cls(**d)

    def updated(self, changes: Any, other_names: set[str]) -> "Variable":
        """Applique des modifications validées venant de l'interface."""
        if not isinstance(changes, dict):
            raise ValidationError("Modifications invalides.")
        allowed = {"name", "label", "type", "level", "role", "unit", "missing_codes", "categories",
                   "potential_identifier"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValidationError(f"Champ(s) non modifiable(s) : {', '.join(sorted(unknown))}.")
        v = Variable.from_dict(self.to_dict())
        if "name" in changes:
            name = changes["name"]
            if not isinstance(name, str) or not name.strip():
                raise ValidationError("Le nom de la variable est obligatoire.")
            name = name.strip()
            if len(name) > 64:
                raise ValidationError("Le nom de la variable ne doit pas dépasser 64 caractères.")
            if name.casefold() in other_names:
                raise ValidationError(f"Une autre variable s'appelle déjà « {name} ».")
            v.name = name
        for text_field, limit in (("label", 300), ("unit", 40)):
            if text_field in changes:
                value = changes[text_field]
                if not isinstance(value, str) or len(value) > limit:
                    raise ValidationError(f"Le champ « {text_field} » est invalide.")
                setattr(v, text_field, value.strip())
        if "type" in changes:
            if changes["type"] not in TYPES:
                raise ValidationError("Type de variable inconnu.")
            v.type = changes["type"]
            if v.level not in ALLOWED_LEVELS[v.type]:
                v.level = default_level(v.type)
        if "level" in changes:
            if changes["level"] not in LEVELS:
                raise ValidationError("Niveau de mesure inconnu.")
            v.level = changes["level"]
        if v.level not in ALLOWED_LEVELS[v.type]:
            raise ValidationError(
                f"Le niveau « {LEVELS[v.level]} » n'est pas compatible avec le type « {TYPES[v.type]} »."
            )
        if "role" in changes:
            if changes["role"] not in ROLES:
                raise ValidationError("Rôle inconnu.")
            v.role = changes["role"]
        if "missing_codes" in changes:
            codes = changes["missing_codes"]
            if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes) or len(codes) > 20:
                raise ValidationError("Codes de valeurs manquantes invalides.")
            v.missing_codes = sorted({c.strip() for c in codes if c.strip()})
        if "categories" in changes:
            cats = changes["categories"]
            if not isinstance(cats, list) or len(cats) > MAX_CATEGORIES:
                raise ValidationError(f"Au plus {MAX_CATEGORIES} modalités.")
            parsed = []
            for c in cats:
                if not isinstance(c, dict) or not isinstance(c.get("value"), str):
                    raise ValidationError("Modalité invalide.")
                parsed.append(Category(value=c["value"], label=str(c.get("label", ""))[:200]))
            if len({c.value for c in parsed}) != len(parsed):
                raise ValidationError("Deux modalités ont la même valeur.")
            v.categories = parsed
        if "potential_identifier" in changes:
            v.potential_identifier = bool(changes["potential_identifier"])
        return v


def default_level(type_: str) -> str:
    return {"numerique": "continu", "texte": "nominal", "booleen": "nominal", "date": "continu"}[type_]


def detect_variable(key: str, raw: pd.Series) -> Variable:
    values = raw[raw.map(lambda x: isinstance(x, str))].astype(object)
    n = len(values)
    type_ = "texte"
    if n:
        numeric_ok = values.map(lambda s: parse_number(s) is not None).sum()
        bool_ok = values.map(lambda s: parse_bool(s) is not None).sum()
        if bool_ok == n and values.str.casefold().nunique() <= 2:
            type_ = "booleen"
        elif numeric_ok / n >= DETECTION_THRESHOLD:
            type_ = "numerique"
        else:
            _, date_ok = best_date_format(values)
            if date_ok / n >= DETECTION_THRESHOLD:
                type_ = "date"
    v = Variable(key=key, name=key, type=type_, level=default_level(type_), detected_type=type_)
    distinct = values.unique()
    if type_ in ("texte", "booleen") or (type_ == "numerique" and len(distinct) <= CATEGORY_DETECTION_MAX):
        if 0 < len(distinct) <= CATEGORY_DETECTION_MAX:
            v.categories = [Category(value=str(x)) for x in sorted(distinct, key=_natural_key)]
    reasons = identifier_reasons(key, values, type_)
    v.potential_identifier = bool(reasons)
    v.identifier_reasons = reasons
    if reasons and type_ == "texte":
        v.role = "identifiant"
    return v


def identifier_reasons(key: str, values: pd.Series, type_: str) -> list[str]:
    reasons = []
    if _ID_NAME.search(key):
        reasons.append("Le nom de la colonne évoque une donnée personnelle.")
    n = len(values)
    if n:
        sample = values.head(500)
        if sample.map(lambda s: bool(_EMAIL.match(s))).mean() > 0.5:
            reasons.append("La colonne contient des adresses e-mail.")
        elif type_ == "texte" and sample.map(lambda s: bool(_PHONE.match(s))).mean() > 0.5:
            reasons.append("La colonne contient des numéros de téléphone.")
        if type_ == "texte" and n >= 10 and values.nunique() == n:
            reasons.append("Chaque ligne a une valeur différente (identifiant probable).")
    return reasons


def _natural_key(x: Any):
    s = str(x)
    num = parse_number(s)
    return (0, num, "") if num is not None else (1, 0.0, s.casefold())


# ---------------------------------------------------------------------- conversion du tableau
@dataclass
class ConversionReport:
    declared_missing: int = 0
    invalid: int = 0
    invalid_examples: list[str] = field(default_factory=list)
    date_format: str | None = None


def convert_column(raw: pd.Series, var: Variable) -> tuple[pd.Series, ConversionReport]:
    report = ConversionReport()
    series = raw.astype(object).copy()
    series = series.where(series.map(lambda x: isinstance(x, str)), None)
    if var.missing_codes:
        mask = series.isin(var.missing_codes)
        report.declared_missing = int(mask.sum())
        series = series.where(~mask, None)
    present = series.notna()
    if var.type == "numerique":
        out = series.map(lambda s: parse_number(s) if isinstance(s, str) else None)
        out = pd.to_numeric(out, errors="coerce").astype("float64")
    elif var.type == "booleen":
        out = series.map(lambda s: parse_bool(s) if isinstance(s, str) else None).astype("boolean")
    elif var.type == "date":
        fmt, _ = best_date_format(series.dropna())
        report.date_format = fmt
        out = pd.to_datetime(series, format=fmt, errors="coerce") if fmt else pd.Series(
            pd.NaT, index=series.index, dtype="datetime64[ns]")
    else:
        out = series.astype(object)
    invalid_mask = present & pd.Series(out, index=series.index).isna()
    report.invalid = int(invalid_mask.sum())
    if report.invalid:
        report.invalid_examples = [str(x) for x in pd.unique(series[invalid_mask])[:5]]
    return out, report


def build_typed_frame(raw: pd.DataFrame, variables: list[Variable]) -> tuple[pd.DataFrame, dict[str, ConversionReport]]:
    columns, reports = {}, {}
    for var in variables:
        if var.computed:
            continue
        columns[var.key], reports[var.key] = convert_column(raw[var.key], var)
    return pd.DataFrame(columns, index=raw.index), reports
