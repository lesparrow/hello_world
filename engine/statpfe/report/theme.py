"""Thèmes de couleurs des rapports et des graphiques.

Les thèmes en couleur utilisent pour les séries la palette d'Okabe et Ito,
distinguable par les personnes daltoniennes. Le thème « sobre » garde le rendu
en niveaux de gris avec hachures, exigé par certains établissements pour l'impression.
"""

from __future__ import annotations

from dataclasses import dataclass

from statpfe.errors import ValidationError

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#F0E442", "#000000"]
GREYS = ["#4d4d4d", "#bdbdbd", "#8c8c8c", "#e0e0e0", "#666666", "#a6a6a6", "#d9d9d9", "#333333"]
HATCHES = ["", "//", "..", "xx", "\\\\", "--", "++", "oo"]


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    color: bool
    primary: str        # titres, traits principaux
    fill: str           # barres et boîtes (une seule série)
    light: str          # fond léger (boîtes, en-têtes clairs)
    header_fill: str    # fond de l'en-tête des tableaux
    header_text: str    # texte de l'en-tête des tableaux
    series: tuple[str, ...]

    @property
    def hatches(self) -> list[str]:
        return HATCHES if not self.color else [""] * len(HATCHES)


THEMES: dict[str, Theme] = {t.key: t for t in [
    Theme("bleu", "Bleu", True, "#1F4E79", "#2E75B6", "#DCE9F5", "#1F4E79", "#FFFFFF", tuple(OKABE_ITO)),
    Theme("vert", "Vert", True, "#1E5631", "#3A8E5C", "#DDEFE3", "#1E5631", "#FFFFFF", tuple(OKABE_ITO)),
    Theme("bordeaux", "Bordeaux", True, "#7B1E3A", "#A63D5A", "#F3DDE4", "#7B1E3A", "#FFFFFF", tuple(OKABE_ITO)),
    Theme("sobre", "Sobre (noir et blanc, pour l'impression)", False, "#000000", "#bdbdbd", "#e0e0e0", "#E7E7E7",
          "#000000", tuple(GREYS)),
]}
DEFAULT_THEME = "bleu"


def get(key: str | None) -> Theme:
    if key is None:
        return THEMES[DEFAULT_THEME]
    if key not in THEMES:
        raise ValidationError("Thème de couleurs inconnu.")
    return THEMES[key]


def choices() -> list[dict[str, object]]:
    return [{"key": t.key, "label": t.label, "color": t.color, "primary": t.primary} for t in THEMES.values()]
