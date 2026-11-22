"""Mise en forme des nombres pour les rapports.

Mêmes règles que l'interface (apps/desktop/src/lib/stats.ts) : décimales fixes,
virgule décimale, valeurs p à trois décimales et « < 0,001 » en dessous.
"""

from __future__ import annotations

import math
from typing import Any

NBSP = " "
MINUS = "−"


def fixed(x: float, digits: int = 2) -> str:
    if not math.isfinite(x):
        return "non calculable"
    s = f"{abs(x):,.{digits}f}".replace(",", NBSP).replace(".", ",")
    # « -0,000 » s'affiche « 0,000 »
    negative = x < 0 and any(c not in "0," + NBSP for c in s)
    return (MINUS if negative else "") + s


def p_value(p: float) -> str:
    return "< 0,001" if p < 0.001 else fixed(p, 3)


def stat(value: Any, kind: str, digits: int = 3) -> str:
    if value is None:
        return "non calculable"
    if isinstance(value, str):
        return value
    if kind == "p":
        return p_value(float(value))
    if kind == "df":
        return fixed(float(value), 0 if float(value).is_integer() else 2)
    return fixed(float(value), digits)


def cell(v: Any, kind: str | None) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "oui" if v else "non"
    if isinstance(v, str):
        return v
    v = float(v)
    if kind == "int":
        return fixed(v, 0)
    if kind == "pct":
        return f"{fixed(v * 100, 1)}{NBSP}%"
    if kind == "text":
        return str(v)
    if v != 0 and (abs(v) >= 1e6 or abs(v) < 1e-3):
        mant, exp = f"{v:.3e}".split("e")
        return f"{mant.replace('.', ',')}e{int(exp)}".replace("-", MINUS)
    return fixed(v, 3)


def stat_line(s: dict[str, Any]) -> str:
    """« p = 0,012 » ou « p < 0,001 » pour une statistique de synthèse."""
    text = stat(s.get("value"), s.get("kind", "value"), s.get("digits", 3))
    if s.get("kind") == "p" and isinstance(s.get("value"), (int, float)):
        return text if text.startswith("<") else f"= {text}"
    return text
