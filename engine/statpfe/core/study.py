"""Informations générales d'une étude et leur validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from statpfe.errors import ValidationError

TITLE_MAX = 300
TEXT_MAX = 20_000
HYPOTHESIS_MAX = 2_000
HYPOTHESES_MAX_COUNT = 50
SAMPLE_SIZE_MAX = 1_000_000_000

TEXT_FIELDS = ("problem_statement", "objectives", "population", "sampling_method")
FIELD_LABELS = {
    "title": "Titre",
    "problem_statement": "Problématique",
    "objectives": "Objectifs",
    "population": "Population étudiée",
    "sampling_method": "Méthode d'échantillonnage",
    "planned_sample_size": "Taille d'échantillon prévue",
    "hypotheses": "Hypothèses",
}


@dataclass
class Study:
    title: str
    problem_statement: str = ""
    objectives: str = ""
    population: str = ""
    sampling_method: str = ""
    planned_sample_size: int | None = None
    hypotheses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> "Study":
        """Construit une étude validée à partir de données externes (non fiables)."""
        if not isinstance(data, dict):
            raise ValidationError("Les informations de l'étude sont invalides.")
        unknown = set(data) - set(FIELD_LABELS)
        if unknown:
            raise ValidationError(f"Champ(s) inconnu(s) : {', '.join(sorted(unknown))}.")
        return cls(
            title=_clean_title(data.get("title")),
            **{name: _clean_text(name, data.get(name, "")) for name in TEXT_FIELDS},
            planned_sample_size=_clean_sample_size(data.get("planned_sample_size")),
            hypotheses=_clean_hypotheses(data.get("hypotheses", [])),
        )

    def merged(self, changes: Any) -> "Study":
        """Retourne une nouvelle étude avec les champs modifiés, validée."""
        if not isinstance(changes, dict):
            raise ValidationError("Les modifications de l'étude sont invalides.")
        return Study.from_dict({**self.to_dict(), **changes})

    def changed_fields(self, other: "Study") -> list[str]:
        mine, theirs = self.to_dict(), other.to_dict()
        return [name for name in FIELD_LABELS if mine[name] != theirs[name]]


def _clean_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Le titre de l'étude est obligatoire.")
    value = value.strip()
    if len(value) > TITLE_MAX:
        raise ValidationError(f"Le titre ne doit pas dépasser {TITLE_MAX} caractères.")
    return value


def _clean_text(name: str, value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"Le champ « {FIELD_LABELS[name]} » doit être un texte.")
    value = value.strip()
    if len(value) > TEXT_MAX:
        raise ValidationError(
            f"Le champ « {FIELD_LABELS[name]} » ne doit pas dépasser {TEXT_MAX} caractères."
        )
    return value


def _clean_sample_size(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("La taille d'échantillon prévue doit être un nombre entier.")
    if not 1 <= value <= SAMPLE_SIZE_MAX:
        raise ValidationError("La taille d'échantillon prévue doit être un entier positif.")
    return value


def _clean_hypotheses(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError("Les hypothèses doivent être une liste.")
    cleaned = []
    for item in value:
        if not isinstance(item, str):
            raise ValidationError("Chaque hypothèse doit être un texte.")
        item = item.strip()
        if not item:
            continue
        if len(item) > HYPOTHESIS_MAX:
            raise ValidationError(
                f"Une hypothèse ne doit pas dépasser {HYPOTHESIS_MAX} caractères."
            )
        cleaned.append(item)
    if len(cleaned) > HYPOTHESES_MAX_COUNT:
        raise ValidationError(f"Au plus {HYPOTHESES_MAX_COUNT} hypothèses sont acceptées.")
    return cleaned
