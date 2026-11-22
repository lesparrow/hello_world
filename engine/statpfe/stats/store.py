"""Analyses enregistrées dans le projet.

Une analyse conserve tout ce qu'il faut pour la reproduire et la vérifier :
jeu de données, version (et son nom au moment du calcul), empreinte du contenu
des données utilisées, méthode, paramètres, versions du moteur et des
bibliothèques de calcul, date, et le résultat complet.
"""

from __future__ import annotations

import json
import math
import platform
import sqlite3
from typing import Any, Callable

import numpy as np
import pandas as pd
import scipy

from statpfe import __version__
from statpfe.core.timeutil import now_iso
from statpfe.data.store import DataStore, fingerprint
from statpfe.errors import StatpfeError, ValidationError
from statpfe.stats import catalog

SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL,
    version_id INTEGER,
    version_name TEXT NOT NULL,
    data_fingerprint TEXT NOT NULL,
    method TEXT NOT NULL,
    params TEXT NOT NULL,
    result TEXT NOT NULL,
    environment TEXT NOT NULL,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
"""

ORIGINAL = "Données d'origine"
STATUS = {
    "a_jour": "Données inchangées depuis le calcul",
    "donnees_modifiees": "Les données ont changé depuis le calcul (dictionnaire ou étapes de la version)",
    "version_supprimee": "La version de données utilisée a été supprimée",
    "jeu_supprime": "Le jeu de données utilisé a été supprimé",
    "version_a_corriger": "La version de données utilisée ne peut plus être calculée",
}


def environment() -> dict[str, str]:
    return {"statpfe": __version__, "python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "pandas": pd.__version__}


class AnalysisStore:
    def __init__(self, conn: sqlite3.Connection, data: DataStore, log: Callable[..., None]):
        self._conn = conn
        self._data = data
        self._log = log

    # ------------------------------------------------------------------ exécution
    def run(self, dataset_id: Any, version_id: Any, method: Any, params: Any, title: Any = None) -> int:
        ds = self._data._dataset_row(dataset_id)
        version_name = self._version_name(ds["id"], version_id)
        df, variables, _ = self._materialize(ds["id"], version_id)
        result = catalog.run(method, df, variables, params)
        clean_params = json.loads(json.dumps(params or {}, ensure_ascii=False))
        name = _clean_title(title) if title else result["title"]
        cur = self._conn.execute(
            "INSERT INTO analyses (dataset_id, version_id, version_name, data_fingerprint, method, params, result,"
            " environment, created_at, title) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ds["id"], version_id, version_name, fingerprint(df), method,
             json.dumps(clean_params, ensure_ascii=False), json.dumps(result, ensure_ascii=False, allow_nan=False),
             json.dumps(environment()), now_iso(), name))
        analysis_id = int(cur.lastrowid)
        self._log("analyse", f"Analyse : {result['method_label']} ({', '.join(result['variables'])}) sur "
                             f"« {ds['name']} », {version_name}", {"analysis_id": analysis_id, "method": method})
        return analysis_id

    def reproduce(self, analysis_id: Any) -> dict[str, Any]:
        """Recalcule l'analyse à l'identique sur les données actuelles et compare (sans rien enregistrer)."""
        row = self._row(analysis_id)
        status, current_fp = self._status(row)
        if status in ("jeu_supprime", "version_supprimee", "version_a_corriger"):
            return {"status": status, "status_label": STATUS[status], "identical_data": False,
                    "identical_results": False, "differences": [], "checked_at": now_iso()}
        df, variables, _ = self._materialize(row["dataset_id"], row["version_id"])
        try:
            fresh = catalog.run(row["method"], df, variables, json.loads(row["params"]))
        except StatpfeError as exc:
            return {"status": status, "status_label": STATUS[status], "identical_data": status == "a_jour",
                    "identical_results": False, "differences": [], "error": exc.message, "checked_at": now_iso()}
        stored = json.loads(row["result"])
        differences = _compare(stored.get("values", {}), fresh.get("values", {}))
        same_env = json.loads(row["environment"]) == environment()
        self._log("reproduction", f"Reproduction de l'analyse « {row['title']} » : "
                                  + ("résultats identiques" if not differences else
                                     f"{len(differences)} différence(s)"), {"analysis_id": row["id"]})
        return {"status": status, "status_label": STATUS[status], "identical_data": status == "a_jour",
                "identical_results": not differences, "differences": differences[:50],
                "same_environment": same_env, "environment": environment(), "checked_at": now_iso()}

    # ------------------------------------------------------------------ lecture
    def list(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT a.id, a.dataset_id, a.version_id, a.version_name, a.data_fingerprint, a.method, a.created_at,"
            " a.title, d.name FROM analyses a LEFT JOIN datasets d ON d.id = a.dataset_id ORDER BY a.id DESC"
        ).fetchall()
        fp_cache: dict[tuple[int, Any], str | None] = {}
        out = []
        for r in rows:
            row = {"id": r[0], "dataset_id": r[1], "version_id": r[2], "version_name": r[3],
                   "data_fingerprint": r[4], "method": r[5], "created_at": r[6], "title": r[7], "dataset_name": r[8]}
            status, _ = self._status(row, fp_cache)
            out.append({**row, "method_label": catalog.METHODS.get(r[5], {}).get("label", r[5]),
                        "status": status, "status_label": STATUS[status]})
        return out

    def get(self, analysis_id: Any) -> dict[str, Any]:
        row = self._row(analysis_id)
        status, current_fp = self._status(row)
        ds_name = self._conn.execute("SELECT name FROM datasets WHERE id = ?", (row["dataset_id"],)).fetchone()
        return {
            "id": row["id"], "title": row["title"], "note": row["note"], "method": row["method"],
            "method_label": catalog.METHODS.get(row["method"], {}).get("label", row["method"]),
            "dataset_id": row["dataset_id"], "dataset_name": ds_name[0] if ds_name else None,
            "version_id": row["version_id"], "version_name": row["version_name"],
            "data_fingerprint": row["data_fingerprint"], "current_fingerprint": current_fp,
            "params": json.loads(row["params"]), "result": json.loads(row["result"]),
            "environment": json.loads(row["environment"]), "created_at": row["created_at"],
            "status": status, "status_label": STATUS[status],
        }

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM analyses").fetchone()[0])

    # ------------------------------------------------------------------ modification
    def update(self, analysis_id: Any, changes: Any) -> None:
        row = self._row(analysis_id)
        if not isinstance(changes, dict) or set(changes) - {"title", "note"}:
            raise ValidationError("Modification d'analyse invalide.")
        if "title" in changes:
            self._conn.execute("UPDATE analyses SET title = ? WHERE id = ?", (_clean_title(changes["title"]),
                                                                               row["id"]))
        if "note" in changes:
            note = changes["note"]
            if not isinstance(note, str) or len(note) > 5000:
                raise ValidationError("La note ne doit pas dépasser 5000 caractères.")
            self._conn.execute("UPDATE analyses SET note = ? WHERE id = ?", (note.strip(), row["id"]))
        self._log("analyse", f"Modification de l'analyse « {row['title']} » ({', '.join(sorted(changes))})",
                  {"analysis_id": row["id"]})

    def delete(self, analysis_id: Any) -> None:
        row = self._row(analysis_id)
        self._conn.execute("DELETE FROM analyses WHERE id = ?", (row["id"],))
        self._log("analyse", f"Suppression de l'analyse « {row['title']} »", {"analysis_id": row["id"]})

    # ------------------------------------------------------------------ interne
    def _materialize(self, dataset_id: int, version_id: Any):
        try:
            return self._data.materialize(dataset_id, version_id)
        except ValidationError as exc:
            if version_id is None:
                raise
            raise ValidationError(f"Cette version des données doit d'abord être corrigée : {exc.message}") from exc

    def _version_name(self, dataset_id: int, version_id: Any) -> str:
        if version_id is None:
            return ORIGINAL
        return self._data._version_row(version_id, dataset_id)["name"]

    def _status(self, row: dict[str, Any], cache: dict | None = None) -> tuple[str, str | None]:
        cache = {} if cache is None else cache
        key = (row["dataset_id"], row["version_id"])
        if key not in cache:
            cache[key] = self._current_fingerprint(row["dataset_id"], row["version_id"])
        fp = cache[key]
        if isinstance(fp, tuple):
            return fp[0], None
        return ("a_jour" if fp == row["data_fingerprint"] else "donnees_modifiees"), fp

    def _current_fingerprint(self, dataset_id: int, version_id: Any):
        if self._conn.execute("SELECT 1 FROM datasets WHERE id = ?", (dataset_id,)).fetchone() is None:
            return ("jeu_supprime",)
        if version_id is not None and self._conn.execute(
                "SELECT 1 FROM versions WHERE id = ? AND dataset_id = ?", (version_id, dataset_id)).fetchone() is None:
            return ("version_supprimee",)
        try:
            df, _, _ = self._data.materialize(dataset_id, version_id)
        except ValidationError:
            return ("version_a_corriger",)
        return fingerprint(df)

    def _row(self, analysis_id: Any) -> dict[str, Any]:
        if not isinstance(analysis_id, int) or isinstance(analysis_id, bool):
            raise ValidationError("Analyse inconnue.")
        cur = self._conn.execute(
            "SELECT id, dataset_id, version_id, version_name, data_fingerprint, method, params, result, environment,"
            " created_at, title, note FROM analyses WHERE id = ?", (analysis_id,))
        r = cur.fetchone()
        if r is None:
            raise ValidationError("Analyse inconnue.")
        return dict(zip([d[0] for d in cur.description], r))


def _clean_title(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Le titre de l'analyse est obligatoire.")
    if len(value.strip()) > 200:
        raise ValidationError("Le titre ne doit pas dépasser 200 caractères.")
    return value.strip()


def _compare(a: Any, b: Any, path: str = "") -> list[dict[str, Any]]:
    """Compare deux arbres de valeurs ; les nombres sont comparés à 1e-12 près (relatif)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += _compare(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += _compare(x, y, f"{path}[{i}]")
        return out
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) \
            and not isinstance(b, bool):
        if math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-15):
            return []
    elif a == b:
        return []
    return [{"path": path, "stored": a, "recomputed": b}]
