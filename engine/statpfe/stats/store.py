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
from statpfe.stats import advisor, catalog

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
    note TEXT NOT NULL DEFAULT '',
    choice TEXT NOT NULL DEFAULT '{}'
);
"""
# Format 4 : ajout du choix de méthode (assistant méthodologique) aux projets au format 3.
MIGRATE_V3_TO_V4 = "ALTER TABLE analyses ADD COLUMN choice TEXT NOT NULL DEFAULT '{}';"


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
        self.plan = None  # PlanStore, attaché par le projet
        self.on_delete: Callable[[int], None] = lambda _id: None

    # ------------------------------------------------------------------ exécution
    def advise(self, dataset_id: Any, version_id: Any, request: Any) -> dict[str, Any]:
        ds = self._data._dataset_row(dataset_id)
        df, variables, _ = self._materialize(ds["id"], version_id)
        return advisor.advise(df, variables, request, self._hypotheses())

    def run(self, dataset_id: Any, version_id: Any, method: Any, params: Any, title: Any = None,
            choice: Any = None) -> int:
        ds = self._data._dataset_row(dataset_id)
        version_name = self._version_name(ds["id"], version_id)
        df, variables, _ = self._materialize(ds["id"], version_id)
        result = catalog.run(method, df, variables, params)
        recorded_choice = self._choice(choice, method, df, variables, result["variables"])
        clean_params = json.loads(json.dumps(params or {}, ensure_ascii=False))
        name = _clean_title(title) if title else result["title"]
        cur = self._conn.execute(
            "INSERT INTO analyses (dataset_id, version_id, version_name, data_fingerprint, method, params, result,"
            " environment, created_at, title, choice) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (ds["id"], version_id, version_name, fingerprint(df), method,
             json.dumps(clean_params, ensure_ascii=False), json.dumps(result, ensure_ascii=False, allow_nan=False),
             json.dumps(environment()), now_iso(), name, json.dumps(recorded_choice, ensure_ascii=False)))
        analysis_id = int(cur.lastrowid)
        self._log("analyse", f"Analyse : {result['method_label']} ({', '.join(result['variables'])}) sur "
                             f"« {ds['name']} », {version_name}", {"analysis_id": analysis_id, "method": method})
        if recorded_choice.get("mode") == "assistant" and not recorded_choice.get("followed"):
            self._log("choix_methode", f"Méthode choisie différente de la recommandation "
                                       f"({recorded_choice.get('recommended_label') or 'aucune'} → "
                                       f"{recorded_choice['chosen_label']}), justification enregistrée",
                      {"analysis_id": analysis_id})
        return analysis_id

    def _hypotheses(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT text FROM hypotheses ORDER BY position")]

    def _choice(self, choice: Any, method: str, df, variables, names: list[str] | None = None) -> dict[str, Any]:
        """Choix de la méthode, recalculé et validé par le moteur (l'interface ne fait que le transmettre)."""
        if choice is None:
            choice = {"mode": "direct"}
        if not isinstance(choice, dict) or choice.get("mode") not in ("assistant", "direct"):
            raise ValidationError("Choix de méthode invalide.")
        reason = choice.get("reason", "")
        if not isinstance(reason, str) or len(reason) > 2000:
            raise ValidationError("La justification ne doit pas dépasser 2000 caractères.")
        reason = reason.strip()
        purpose = choice.get("purpose")
        if purpose not in (None, *advisor.PURPOSES):
            raise ValidationError("Nature de l'analyse inconnue.")
        hypotheses = self._hypotheses()
        hyp = choice.get("hypothesis")
        if hyp is not None and (not isinstance(hyp, int) or isinstance(hyp, bool) or not 0 <= hyp < len(hypotheses)):
            raise ValidationError("Hypothèse inconnue.")
        out: dict[str, Any] = {
            "mode": choice["mode"], "chosen": method, "chosen_label": catalog.METHODS[method]["label"],
            "reason": reason, "purpose": purpose, "purpose_label": advisor.PURPOSES.get(purpose) if purpose else None,
            "hypothesis": hyp, "hypothesis_text": hypotheses[hyp] if hyp is not None else None,
        }
        if choice.get("plan_item") is not None:
            if self.plan is None:
                raise ValidationError("Plan d'analyse indisponible.")
            out["plan"] = self.plan.link(choice["plan_item"], method, names or [], choice.get("plan_reason"))
        if choice["mode"] == "assistant":
            request = choice.get("request")
            if not isinstance(request, dict):
                raise ValidationError("Demande d'assistance manquante.")
            request = {**request, "purpose": purpose, "hypothesis": hyp}
            advice = advisor.advise(df, variables, request, hypotheses)
            rec = advice["recommendation"]
            followed = rec is not None and rec["method"] == method
            if not followed and not reason:
                raise ValidationError("Vous avez choisi une autre méthode que celle recommandée : indiquez la raison de "
                                      "ce choix.")
            out.update(rules_version=advice["rules_version"], objective=advice["objective"],
                       objective_label=advice["objective_label"],
                       recommended=rec["method"] if rec else None, recommended_label=rec["label"] if rec else None,
                       recommendation_reasons=rec["reasons"] if rec else [], followed=followed,
                       missing_information=advice["missing_information"])
        return out

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

    def verify(self, analysis_id: Any) -> dict[str, Any]:
        """Contrôle avant rapport : recalcule l'analyse et compare valeurs, effectifs, tableaux et graphiques.

        Contrairement à `reproduce`, rien n'est inscrit au journal."""
        row = self._row(analysis_id)
        status, _ = self._status(row)
        out: dict[str, Any] = {"status": status, "status_label": STATUS[status], "checked": False,
                               "differences": [], "error": None, "rows": None}
        if status != "a_jour":
            return out
        if row["method"] not in catalog.METHODS:
            out["error"] = "Méthode inconnue de cette version du logiciel."
            return out
        df, variables, _ = self._materialize(row["dataset_id"], row["version_id"])
        out["rows"] = len(df)
        try:
            fresh = catalog.run(row["method"], df, variables, json.loads(row["params"]))
        except StatpfeError as exc:
            out["error"] = exc.message
            return out
        fresh = json.loads(json.dumps(fresh, ensure_ascii=False, allow_nan=False))
        stored = json.loads(row["result"])
        keys = ("values", "n_used", "summary", "tables", "charts")
        out["checked"] = True
        out["differences"] = _compare({k: stored.get(k) for k in keys}, {k: fresh.get(k) for k in keys})[:20]
        return out

    def levels(self, dataset_id: Any, version_id: Any, key: Any) -> list[dict[str, Any]]:
        """Modalités présentes d'une variable (ordre du dictionnaire), pour choisir les groupes à comparer."""
        from statpfe.stats.common import MAX_GROUP_LEVELS, as_labels, level_label, ordered_levels

        ds = self._data._dataset_row(dataset_id)
        df, variables, _ = self._materialize(ds["id"], version_id)
        var = next((v for v in variables if v.key == key), None)
        if var is None:
            raise ValidationError("Variable inconnue.")
        if var.potential_identifier or var.role == "identifiant":
            raise ValidationError("Les modalités d'une variable identifiante ne sont pas affichées.")
        labels = as_labels(df[var.key])
        counts = labels.value_counts()
        present = ordered_levels(var, sorted(set(labels.dropna())))
        if len(present) > MAX_GROUP_LEVELS:
            raise ValidationError(f"« {var.name} » a plus de {MAX_GROUP_LEVELS} valeurs différentes.")
        return [{"value": v, "label": level_label(var, v), "count": int(counts.get(v, 0))} for v in present]

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
            "status": status, "status_label": STATUS[status], "choice": json.loads(row["choice"]),
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
        self.on_delete(row["id"])
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
            " created_at, title, note, choice FROM analyses WHERE id = ?", (analysis_id,))
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
