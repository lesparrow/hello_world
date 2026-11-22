"""Jeux de données d'un projet : import, dictionnaire, versions et aperçu.

Le fichier importé est copié tel quel (octet pour octet) dans le projet et
identifié par son empreinte SHA-256. Toutes les vues des données sont
recalculées à partir de cette copie, du dictionnaire et des étapes de chaque
version : rien n'est modifié en place.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from statpfe.core.timeutil import now_iso
from statpfe.data import sources
from statpfe.data.quality import quality_report
from statpfe.data.sources import ReadOptions, SourceError
from statpfe.data.transforms import MAX_STEPS, OPERATIONS, apply_step, display_value
from statpfe.data.types import LEVELS, ROLES, TYPES, ConversionReport, Variable, build_typed_frame, detect_variable
from statpfe.errors import StatpfeError, ValidationError

SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_file TEXT NOT NULL,
    source_sha256 TEXT NOT NULL,
    source_ext TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    read_options TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS variables (
    dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    key TEXT NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (dataset_id, key)
);
CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    steps TEXT NOT NULL DEFAULT '[]'
);
"""

PREVIEW_MAX = 500
MASK = "•••"


class DataStore:
    def __init__(self, conn: sqlite3.Connection, workdir: Path, log: Callable[..., None]):
        self._conn = conn
        self._sources_dir = workdir / "sources"
        self._log = log
        self._raw_cache: dict[int, pd.DataFrame] = {}

    # ------------------------------------------------------------------ fichiers
    def source_files(self) -> list[Path]:
        if not self._sources_dir.is_dir():
            return []
        return sorted(p for p in self._sources_dir.iterdir() if p.is_file())

    @staticmethod
    def inspect(raw_path: Any, raw_options: Any) -> dict[str, Any]:
        path, data = sources.read_source_file(raw_path)
        kind = sources.file_kind(path)
        table = sources.parse(data, kind, ReadOptions.from_dict(raw_options))
        frame = table.frame
        detected = [detect_variable(c, frame[c]) for c in frame.columns]
        return {
            "file_name": path.name,
            "size": len(data),
            "kind": kind,
            "sheets": table.sheets,
            "options": table.options.to_dict(),
            "rows": len(frame),
            "columns": [
                {"key": v.key, "type": v.type, "type_label": TYPES[v.type],
                 "potential_identifier": v.potential_identifier}
                for v in detected
            ],
            "preview": [
                [None if v is None else (MASK if detected[i].potential_identifier else v)
                 for i, v in enumerate(row)]
                for row in frame.head(30).itertuples(index=False, name=None)
            ],
            "notes": table.notes,
        }

    # ------------------------------------------------------------------ import
    def import_file(self, raw_path: Any, raw_options: Any, raw_name: Any) -> int:
        path, data = sources.read_source_file(raw_path)
        kind = sources.file_kind(path)
        table = sources.parse(data, kind, ReadOptions.from_dict(raw_options))
        name = _clean_name(raw_name if raw_name else path.stem)
        digest = sources.sha256(data)
        ext = path.suffix.lower()
        self._sources_dir.mkdir(exist_ok=True)
        target = self._sources_dir / f"{digest}{ext}"
        if not target.exists():
            target.write_bytes(data)
        cur = self._conn.execute(
            "INSERT INTO datasets (name, source_file, source_sha256, source_ext, source_kind, read_options,"
            " imported_at, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, path.name, digest, ext, kind, json.dumps(table.options.to_dict()), now_iso(),
             json.dumps(table.notes, ensure_ascii=False)),
        )
        dataset_id = int(cur.lastrowid)
        variables = [detect_variable(c, table.frame[c]) for c in table.frame.columns]
        self._write_variables(dataset_id, variables)
        self._raw_cache[dataset_id] = table.frame
        self._log("import_donnees",
                  f"Import de « {path.name} » ({len(table.frame)} lignes, {len(variables)} variables)",
                  {"dataset_id": dataset_id, "sha256": digest})
        return dataset_id

    def delete_dataset(self, dataset_id: Any) -> None:
        ds = self._dataset_row(dataset_id)
        self._conn.execute("DELETE FROM versions WHERE dataset_id = ?", (ds["id"],))
        self._conn.execute("DELETE FROM variables WHERE dataset_id = ?", (ds["id"],))
        self._conn.execute("DELETE FROM datasets WHERE id = ?", (ds["id"],))
        still_used = self._conn.execute(
            "SELECT COUNT(*) FROM datasets WHERE source_sha256 = ?", (ds["source_sha256"],)).fetchone()[0]
        if not still_used:
            (self._sources_dir / f"{ds['source_sha256']}{ds['source_ext']}").unlink(missing_ok=True)
        self._raw_cache.pop(ds["id"], None)
        self._log("suppression_donnees", f"Suppression du jeu de données « {ds['name']} »",
                  {"dataset_id": ds["id"]})

    # ------------------------------------------------------------------ lecture
    def list(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, name, source_file, imported_at FROM datasets ORDER BY id").fetchall()
        return [{"id": r[0], "name": r[1], "source_file": r[2], "imported_at": r[3]} for r in rows]

    def get(self, dataset_id: Any) -> dict[str, Any]:
        ds = self._dataset_row(dataset_id)
        variables = self._variables(ds["id"])
        typed, conversions = self._typed(ds["id"], variables)
        versions = []
        for vid, vname, created, steps_json in self._conn.execute(
                "SELECT id, name, created_at, steps FROM versions WHERE dataset_id = ? ORDER BY id", (ds["id"],)):
            versions.append(self._describe_version(vid, vname, created, json.loads(steps_json), typed, variables))
        return {
            "id": ds["id"],
            "name": ds["name"],
            "source": {
                "file_name": ds["source_file"],
                "sha256": ds["source_sha256"],
                "kind": ds["source_kind"],
                "read_options": json.loads(ds["read_options"]),
                "imported_at": ds["imported_at"],
                "notes": json.loads(ds["notes"]),
            },
            "original": {"rows": len(typed), "columns": len(variables), "fingerprint": fingerprint(typed)},
            "variables": [_variable_view(v) for v in variables],
            "quality": quality_report(typed, variables, conversions),
            "versions": versions,
            "vocabulary": {"types": TYPES, "levels": LEVELS, "roles": ROLES, "operations": OPERATIONS},
        }

    def preview(self, dataset_id: Any, version_id: Any, offset: Any, limit: Any, reveal: Any) -> dict[str, Any]:
        ds = self._dataset_row(dataset_id)
        df, variables, _ = self.materialize(ds["id"], version_id)
        offset = _int(offset, 0, 0, max(len(df), 0))
        limit = _int(limit, 100, 1, PREVIEW_MAX)
        page = df.iloc[offset:offset + limit]
        hide = {v.key for v in variables if v.potential_identifier} if not reveal else set()
        rows = []
        for row in page.itertuples(index=False, name=None):
            rows.append([
                None if _missing(x) else (MASK if variables[i].key in hide else _json_value(x))
                for i, x in enumerate(row)
            ])
        return {
            "total": len(df),
            "offset": offset,
            "columns": [{"key": v.key, "name": v.name, "type": v.type, "masked": v.key in hide} for v in variables],
            "rows": rows,
            "row_numbers": [int(i) + 1 for i in page.index],
        }

    def version_quality(self, dataset_id: Any, version_id: Any) -> dict[str, Any]:
        ds = self._dataset_row(dataset_id)
        df, variables, conversions = self.materialize(ds["id"], version_id)
        return quality_report(df, variables, conversions)

    # ------------------------------------------------------------------ dictionnaire
    def update_variable(self, dataset_id: Any, key: Any, changes: Any) -> dict[str, Any]:
        ds = self._dataset_row(dataset_id)
        variables = self._variables(ds["id"])
        index = next((i for i, v in enumerate(variables) if v.key == key), None)
        if index is None:
            raise ValidationError("Variable inconnue.")
        others = {v.name.casefold() for i, v in enumerate(variables) if i != index}
        updated = variables[index].updated(changes, others)
        changed = [f for f in ("name", "label", "type", "level", "role", "unit", "missing_codes", "categories",
                               "potential_identifier")
                   if getattr(updated, f) != getattr(variables[index], f)]
        if not changed:
            return _variable_view(variables[index])
        variables[index] = updated
        self._write_variables(ds["id"], variables)
        self._log("dictionnaire", f"Dictionnaire : « {updated.name} » ({', '.join(changed)})",
                  {"dataset_id": ds["id"], "variable": updated.key, "fields": changed})
        return _variable_view(updated)

    # ------------------------------------------------------------------ versions
    def create_version(self, dataset_id: Any, raw_name: Any, from_version: Any) -> int:
        ds = self._dataset_row(dataset_id)
        steps: list = []
        if from_version is not None:
            steps = self._version_row(from_version, ds["id"])["steps"]
        name = _clean_name(raw_name or "Version de travail")
        cur = self._conn.execute(
            "INSERT INTO versions (dataset_id, name, created_at, steps) VALUES (?, ?, ?, ?)",
            (ds["id"], name, now_iso(), json.dumps(steps, ensure_ascii=False)))
        self._log("version", f"Création de la version « {name} »", {"dataset_id": ds["id"]})
        return int(cur.lastrowid)

    def rename_version(self, version_id: Any, raw_name: Any) -> None:
        row = self._version_row(version_id)
        name = _clean_name(raw_name)
        self._conn.execute("UPDATE versions SET name = ? WHERE id = ?", (name, row["id"]))
        self._log("version", f"Version « {row['name']} » renommée en « {name} »", {})

    def delete_version(self, version_id: Any) -> None:
        row = self._version_row(version_id)
        self._conn.execute("DELETE FROM versions WHERE id = ?", (row["id"],))
        self._log("version", f"Suppression de la version « {row['name']} »", {})

    def add_step(self, version_id: Any, step: Any) -> None:
        row = self._version_row(version_id)
        if len(row["steps"]) >= MAX_STEPS:
            raise ValidationError(f"Une version ne peut pas dépasser {MAX_STEPS} étapes.")
        df, variables, _ = self.materialize(row["dataset_id"], row["id"])
        step = _clean_step(step)
        _, _, result = apply_step(df, variables, step)  # valide l'étape sur les données réelles
        steps = row["steps"] + [step]
        self._conn.execute("UPDATE versions SET steps = ? WHERE id = ?",
                           (json.dumps(steps, ensure_ascii=False), row["id"]))
        self._log("transformation", f"« {row['name']} » : {OPERATIONS[step['op']]}",
                  {"version_id": row["id"], "op": step["op"]})

    def remove_step(self, version_id: Any, index: Any) -> None:
        row = self._version_row(version_id)
        steps = row["steps"]
        if not isinstance(index, int) or not 0 <= index < len(steps):
            raise ValidationError("Étape inconnue.")
        remaining = steps[:index] + steps[index + 1:]
        ds_id = row["dataset_id"]
        variables = self._variables(ds_id)
        typed, _ = self._typed(ds_id, variables)
        df, current = typed, variables
        for i, step in enumerate(remaining):
            try:
                df, current, _ = apply_step(df, current, step)
            except ValidationError as exc:
                raise ValidationError(
                    f"Impossible de retirer cette étape : l'étape {i + 2 if i >= index else i + 1} en dépend "
                    f"({exc.message}). Retirez d'abord l'étape qui en dépend."
                ) from exc
        self._conn.execute("UPDATE versions SET steps = ? WHERE id = ?",
                           (json.dumps(remaining, ensure_ascii=False), row["id"]))
        self._log("transformation", f"« {row['name']} » : retrait de l'étape {index + 1} "
                                    f"({OPERATIONS[steps[index]['op']]})", {"version_id": row["id"]})

    # ------------------------------------------------------------------ calcul
    def materialize(self, dataset_id: int, version_id: Any) -> tuple[pd.DataFrame, list[Variable], dict[str, ConversionReport]]:
        variables = self._variables(dataset_id)
        typed, conversions = self._typed(dataset_id, variables)
        if version_id is None:
            return typed, variables, conversions
        row = self._version_row(version_id, dataset_id)
        df, current = typed, variables
        for step in row["steps"]:
            df, current, _ = apply_step(df, current, step)
        return df, current, conversions

    def _typed(self, dataset_id: int, variables: list[Variable]):
        raw = self._raw(dataset_id)
        return build_typed_frame(raw, variables)

    def _raw(self, dataset_id: int) -> pd.DataFrame:
        if dataset_id not in self._raw_cache:
            ds = self._dataset_row(dataset_id)
            path = self._sources_dir / f"{ds['source_sha256']}{ds['source_ext']}"
            try:
                data = path.read_bytes()
            except OSError as exc:
                raise StatpfeError("Le fichier source de ce jeu de données est absent du projet.") from exc
            if sources.sha256(data) != ds["source_sha256"]:
                raise StatpfeError("Le fichier source de ce jeu de données a été altéré (empreinte différente).")
            table = sources.parse(data, ds["source_kind"], ReadOptions.from_dict(json.loads(ds["read_options"])))
            self._raw_cache[dataset_id] = table.frame
        return self._raw_cache[dataset_id]

    def _describe_version(self, vid, name, created, steps, typed, variables) -> dict[str, Any]:
        df, current = typed, variables
        described, error = [], None
        for i, step in enumerate(steps):
            try:
                df, current, result = apply_step(df, current, step)
                described.append({"index": i, "op": step["op"], "step": step, **result.to_dict()})
            except (ValidationError, SourceError) as exc:
                error = f"L'étape {i + 1} ne peut plus être appliquée : {exc.message}"
                described.append({"index": i, "op": step["op"], "step": step, "description": OPERATIONS[step["op"]],
                                  "rows_before": len(df), "rows_after": None, "warnings": [], "error": exc.message})
                break
        return {
            "id": vid, "name": name, "created_at": created, "steps": described, "error": error,
            "rows": None if error else len(df), "columns": None if error else len(current),
            "fingerprint": None if error else fingerprint(df),
            "variables": [_variable_view(v) for v in current],
        }

    # ------------------------------------------------------------------ stockage
    def _dataset_row(self, dataset_id: Any) -> dict[str, Any]:
        if not isinstance(dataset_id, int):
            raise ValidationError("Jeu de données inconnu.")
        cur = self._conn.execute(
            "SELECT id, name, source_file, source_sha256, source_ext, source_kind, read_options, imported_at, notes"
            " FROM datasets WHERE id = ?", (dataset_id,))
        row = cur.fetchone()
        if row is None:
            raise ValidationError("Jeu de données inconnu.")
        return dict(zip([d[0] for d in cur.description], row))

    def _version_row(self, version_id: Any, dataset_id: int | None = None) -> dict[str, Any]:
        if not isinstance(version_id, int):
            raise ValidationError("Version inconnue.")
        row = self._conn.execute("SELECT id, dataset_id, name, steps FROM versions WHERE id = ?",
                                 (version_id,)).fetchone()
        if row is None or (dataset_id is not None and row[1] != dataset_id):
            raise ValidationError("Version inconnue.")
        return {"id": row[0], "dataset_id": row[1], "name": row[2], "steps": json.loads(row[3])}

    def _variables(self, dataset_id: int) -> list[Variable]:
        rows = self._conn.execute(
            "SELECT data FROM variables WHERE dataset_id = ? ORDER BY position", (dataset_id,)).fetchall()
        return [Variable.from_dict(json.loads(r[0])) for r in rows]

    def _write_variables(self, dataset_id: int, variables: list[Variable]) -> None:
        self._conn.execute("DELETE FROM variables WHERE dataset_id = ?", (dataset_id,))
        self._conn.executemany(
            "INSERT INTO variables (dataset_id, position, key, data) VALUES (?, ?, ?, ?)",
            [(dataset_id, i, v.key, json.dumps(v.to_dict(), ensure_ascii=False)) for i, v in enumerate(variables)])


# ---------------------------------------------------------------------- utilitaires
def fingerprint(df: pd.DataFrame) -> str:
    """Empreinte du contenu d'une version : deux versions identiques ont la même."""
    payload = df.to_csv(index=False, lineterminator="\n", date_format="%Y-%m-%dT%H:%M:%S").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _variable_view(v: Variable) -> dict[str, Any]:
    d = v.to_dict()
    d["type_label"] = TYPES[v.type]
    d["level_label"] = LEVELS[v.level]
    d["role_label"] = ROLES[v.role]
    return d


def _clean_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("Le nom est obligatoire.")
    value = value.strip()
    if len(value) > 120:
        raise ValidationError("Le nom ne doit pas dépasser 120 caractères.")
    return value


def _clean_step(step: Any) -> dict[str, Any]:
    if not isinstance(step, dict):
        raise ValidationError("Transformation invalide.")
    raw = json.dumps(step, ensure_ascii=False)
    if len(raw) > 20_000:
        raise ValidationError("Transformation trop volumineuse.")
    return json.loads(raw)


def _int(value: Any, default: int, lo: int, hi: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError("Paramètre numérique invalide.")
    return max(lo, min(hi, value))


def _missing(x: Any) -> bool:
    try:
        return bool(pd.isna(x))
    except (TypeError, ValueError):
        return False


def _json_value(x: Any) -> Any:
    if isinstance(x, (bool, np.bool_)):
        return display_value(bool(x))
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        x = float(x)
        return x if math.isfinite(x) else None
    if isinstance(x, pd.Timestamp):
        return display_value(x)
    return x if isinstance(x, (int, str)) else str(x)
