"""Contrôles automatiques d'un texte proposé par le modèle.

Le contrôle principal compare chaque nombre du texte à ceux des résultats transmis :
un nombre absent (ou plus précis que celui fourni) est signalé et empêche de retenir
le texte tel quel. Les formulations trop affirmatives sont signalées sans blocage.
Ces contrôles ne garantissent pas que le texte est juste : la relecture reste nécessaire.
"""

from __future__ import annotations

import math
import re
from typing import Any

# Nombre isolé : pas collé à une lettre (H1, Q3, t2…), séparateur de milliers = espace insécable seulement.
NUMBER = re.compile(
    r"(?<![\w.,])(?:[−\-–]\s?)?(?:\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,]\d+)?(?:[eE][−\-+]?\d+)?(?![\w])"
    r"|(?<![\w.,\d])[.,]\d+(?![\w])")
SMALL_INTEGERS = set(range(0, 11))
THINK = re.compile(r"<think>.*?(</think>|$)", re.S | re.I)

WORDING = [
    (re.compile(r"\bprouv\w*|\bdémontr\w*|\bpreuve\b", re.I),
     "Formulation trop affirmative (« prouve », « démontre », « preuve ») : un test statistique ne prouve rien, "
     "il apporte des éléments en faveur d'une hypothèse."),
    (re.compile(r"\bvalid\w*\s+scientifiquement|\bscientifiquement\s+valid\w*", re.I),
     "Le texte se présente comme une validation scientifique : seul l'auteur (et son encadrant) peut en juger."),
    (re.compile(r"\b(cause|causal\w*|provoqu\w*|entraîn\w*|engendr\w*)\b", re.I),
     "Formulation causale : vérifiez que le plan d'étude (expérimental, randomisé) permet de conclure à un lien "
     "de cause à effet ; sinon, parlez d'association ou de différence."),
    (re.compile(r"(absence|pas)\s+d['’]effet|aucun\s+effet|n['’]a\s+aucun\s+(impact|effet)", re.I),
     "Un résultat non significatif ne démontre pas l'absence d'effet : il indique seulement que les données ne "
     "permettent pas de le mettre en évidence."),
    (re.compile(r"\bet\s+al\.|\(\s*[A-Z][a-zé]+,?\s+\d{4}\s*\)|\b(19|20)\d{2}\b"),
     "Le texte semble citer une référence ou une date : le modèle peut inventer des références ; vérifiez-les "
     "ou supprimez-les."),
]


NEGATABLE = {0, 1, 2}
NEGATION = re.compile(r"\b(ne|n['’]|pas|ni|sans|aucun\w*|jamais)\b[^.;:!?]*$", re.I)


def strip_thinking(text: str) -> str:
    return THINK.sub("", text).strip()


def parse_number(token: str) -> tuple[float, int] | None:
    """(valeur absolue, nombre de décimales) d'un nombre écrit à la française ou à l'anglaise."""
    t = token.strip().lstrip("−-–").strip().replace(" ", "").replace(" ", "")
    exp = 0
    if "e" in t.lower():
        t, _, e = t.lower().partition("e")
        try:
            exp = int(e.replace("−", "-"))
        except ValueError:
            return None
    t = t.replace(",", ".")
    try:
        value = float(t)
    except ValueError:
        return None
    decimals = len(t.split(".")[1]) if "." in t else 0
    if exp:
        value *= 10 ** exp
        decimals = max(0, decimals - exp)
    return abs(value), decimals


def numbers(text: str) -> list[dict[str, Any]]:
    out = []
    for m in NUMBER.finditer(text):
        parsed = parse_number(m.group(0))
        if parsed is not None:
            out.append({"text": m.group(0).strip(), "start": m.start(), "end": m.end(),
                        "value": parsed[0], "decimals": parsed[1]})
    return out


def allowed_numbers(context: str) -> list[tuple[float, int]]:
    return [(n["value"], n["decimals"]) for n in numbers(context)]


def _matches(value: float, decimals: int, allowed: list[tuple[float, int]]) -> bool:
    if decimals == 0 and value in SMALL_INTEGERS:
        return True
    tol = 0.5 * 10 ** (-decimals) + 1e-12
    for a, da in allowed:
        if decimals > da:
            continue  # plus de décimales que la valeur fournie : chiffres inventés
        if abs(round(a, decimals) - value) < 1e-9 or abs(a - value) < 1e-12:
            return True
        # Arrondi « à la main » d'un nombre déjà arrondi (5,075 → 5,08 puis 5,1).
        if decimals < da and abs(a - value) <= tol:
            return True
    return False


def check(text: str, context: str) -> dict[str, Any]:
    allowed = allowed_numbers(context)
    found = numbers(text)
    unverified = [{"text": n["text"], "start": n["start"], "end": n["end"]}
                  for n in found if not _matches(n["value"], n["decimals"], allowed)]
    warnings = []
    for i, (pattern, message) in enumerate(WORDING):
        matches = list(pattern.finditer(text))
        if i in NEGATABLE:
            # « ne permet pas d'établir un lien de cause à effet » est justement la prudence attendue.
            matches = [m for m in matches if not NEGATION.search(text[max(0, m.start() - 60):m.start()])]
        if matches:
            warnings.append(message)
    empty = not text.strip()
    return {
        "numbers_total": len(found),
        "unverified": unverified,
        "warnings": warnings,
        "empty": empty,
        "blocking": bool(unverified) or empty,
    }


def finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
