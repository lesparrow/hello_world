"""Calculs de puissance enregistrés dans le projet, avec leurs hypothèses."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable

from statpfe.core.timeutil import now_iso
from statpfe.errors import ValidationError
from statpfe.stats import power
from statpfe.stats.store import _compare, environment

SCHEMA_V5_POWER = """
CREATE TABLE IF NOT EXISTS power_calcs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    request TEXT NOT NULL,
    result TEXT NOT NULL,
    environment TEXT NOT NULL
);
"""
TITLE_MAX = 200
MAX_CALCS = 500


class PowerStore:
    def __init__(self, conn: sqlite3.Connection, log: Callable[..., None]):
        self._conn = conn
        self._log = log
        self.locked_references: Callable[[int], list[int]] = lambda _id: []

    def compute(self, request: Any) -> dict[str, Any]:
        return power.compute(request)

    def save(self, request: Any, title: Any = None) -> int:
        result = power.compute(request)
        if self.count() >= MAX_CALCS:
            raise ValidationError(f"Au plus {MAX_CALCS} calculs de puissance par projet.")
        name = _clean_title(title) if title not in (None, "") else result["title"]
        cur = self._conn.execute(
            "INSERT INTO power_calcs (created_at, title, request, result, environment) VALUES (?, ?, ?, ?, ?)",
            (now_iso(), name, json.dumps(result["request"], ensure_ascii=False),
             json.dumps(result, ensure_ascii=False, allow_nan=False), json.dumps(environment())))
        calc_id = int(cur.lastrowid)
        self._log("puissance", f"Calcul de puissance enregistré : {result['mode_label'].lower()} "
                               f"({power.DESIGNS[result['design']]['label'].split(' (')[0].lower()})",
                  {"power_id": calc_id})
        return calc_id

    def list(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT id, created_at, title, result FROM power_calcs ORDER BY id").fetchall()
        out = []
        for r in rows:
            res = json.loads(r[3])
            out.append({"id": r[0], "created_at": r[1], "title": r[2], "design": res["design"],
                        "design_label": res["design_label"], "mode": res["mode"], "mode_label": res["mode_label"],
                        "headline": res["interpretation"][0] if res["interpretation"] else "",
                        "locked_in_plan": self.locked_references(r[0])})
        return out

    def get(self, calc_id: Any) -> dict[str, Any]:
        row = self._row(calc_id)
        return {"id": row[0], "created_at": row[1], "title": row[2], "request": json.loads(row[3]),
                "result": json.loads(row[4]), "environment": json.loads(row[5]),
                "locked_in_plan": self.locked_references(row[0])}

    def exists(self, calc_id: int) -> bool:
        return self._conn.execute("SELECT 1 FROM power_calcs WHERE id = ?", (calc_id,)).fetchone() is not None

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM power_calcs").fetchone()[0])

    def rename(self, calc_id: Any, title: Any) -> None:
        row = self._row(calc_id)
        name = _clean_title(title)
        if name == row[2]:
            return
        self._conn.execute("UPDATE power_calcs SET title = ? WHERE id = ?", (name, row[0]))
        self._log("puissance", f"Calcul de puissance n° {row[0]} renommé", {"power_id": row[0]})

    def delete(self, calc_id: Any) -> None:
        row = self._row(calc_id)
        locked = self.locked_references(row[0])
        if locked:
            raise ValidationError(
                f"Ce calcul justifie la taille d'échantillon du plan d'analyse verrouillé (version "
                f"{', '.join(map(str, locked))}) : il ne peut pas être supprimé.")
        self._conn.execute("DELETE FROM power_calcs WHERE id = ?", (row[0],))
        self._log("puissance", f"Calcul de puissance n° {row[0]} supprimé", {"power_id": row[0]})

    def verify(self, calc_id: int) -> list[dict[str, Any]]:
        """Refait le calcul et compare au résultat enregistré (contrôle avant export)."""
        row = self._row(calc_id)
        stored = json.loads(row[4])
        fresh = json.loads(json.dumps(power.compute(json.loads(row[3])), ensure_ascii=False))
        return _compare({"rows": stored["rows"], "values": stored["values"]},
                        {"rows": fresh["rows"], "values": fresh["values"]})

    def _row(self, calc_id: Any):
        if isinstance(calc_id, bool) or not isinstance(calc_id, int):
            raise ValidationError("Calcul de puissance inconnu.")
        row = self._conn.execute("SELECT id, created_at, title, request, result, environment FROM power_calcs "
                                 "WHERE id = ?", (calc_id,)).fetchone()
        if row is None:
            raise ValidationError("Ce calcul de puissance n'existe plus.")
        return row


def _clean_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Le titre du calcul est vide.")
    value = value.strip()
    if len(value) > TITLE_MAX:
        raise ValidationError(f"Le titre ne doit pas dépasser {TITLE_MAX} caractères.")
    return value
