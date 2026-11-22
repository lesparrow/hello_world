"""Serveur JSON-RPC 2.0 du moteur STATPFE.

L'application lance le moteur comme processus enfant et échange avec lui un message
JSON par ligne sur l'entrée et la sortie standard. Aucun port réseau n'est ouvert.
La sortie standard est réservée au protocole ; les journaux techniques vont sur
la sortie d'erreur et ne contiennent jamais le contenu des études.
"""

from __future__ import annotations

import io
import json
import logging
import platform
import sys
from typing import Any, Callable, TextIO

from statpfe import __version__
from statpfe.core import recent
from statpfe.core.project import FORMAT_VERSION, Project
from statpfe.errors import (
    NoProjectOpenError,
    ProjectAlreadyOpenError,
    StatpfeError,
    ValidationError,
)

log = logging.getLogger("statpfe.rpc")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
BUSINESS_ERROR = -32000


class Engine:
    """État du moteur : au plus un projet ouvert à la fois."""

    def __init__(self) -> None:
        self.project: Project | None = None
        self.methods: dict[str, Callable[[dict[str, Any]], Any]] = {
            "engine.info": self.info,
            "app.recent_projects": self.recent_projects,
            "app.forget_recent": self.forget_recent,
            "project.create": self.create,
            "project.open": self.open,
            "project.current": self.current,
            "project.update_study": self.update_study,
            "project.save": self.save,
            "project.save_as": self.save_as,
            "project.close": self.close,
            "data.inspect_file": self.data_inspect,
            "data.import": self.data_import,
            "data.get": self.data_get,
            "data.delete": self.data_delete,
            "data.preview": self.data_preview,
            "data.quality": self.data_quality,
            "data.update_variable": self.data_update_variable,
            "data.create_version": self.data_create_version,
            "data.rename_version": self.data_rename_version,
            "data.delete_version": self.data_delete_version,
            "data.add_step": self.data_add_step,
            "data.remove_step": self.data_remove_step,
            "analysis.catalog": self.analysis_catalog,
            "analysis.run": self.analysis_run,
            "analysis.list": self.analysis_list,
            "analysis.get": self.analysis_get,
            "analysis.update": self.analysis_update,
            "analysis.delete": self.analysis_delete,
            "analysis.reproduce": self.analysis_reproduce,
            "analysis.levels": self.analysis_levels,
            "analysis.advise": self.analysis_advise,
        }

    # -------------------------------------------------------------- méthodes
    def info(self, _: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": "statpfe-engine",
            "version": __version__,
            "project_format_version": FORMAT_VERSION,
            "python": platform.python_version(),
            "platform": platform.platform(terse=True),
        }

    def recent_projects(self, _: dict[str, Any]) -> list[dict[str, Any]]:
        return recent.load()

    def forget_recent(self, params: dict[str, Any]) -> None:
        recent.forget(_require_str(params, "path"))

    def create(self, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_none_open()
        project = Project.create(
            params.get("path"), params.get("study"), overwrite=bool(params.get("overwrite"))
        )
        return self._activate(project)

    def open(self, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_none_open()
        return self._activate(Project.open(params.get("path")))

    def current(self, _: dict[str, Any]) -> dict[str, Any] | None:
        return self.project.describe() if self.project else None

    def update_study(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.update_study(params.get("changes"))
        return project.describe()

    def save(self, _: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.save()
        return project.describe()

    def save_as(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.save_as(params.get("path"), overwrite=bool(params.get("overwrite")))
        self._remember(project)
        return project.describe()

    def close(self, params: dict[str, Any]) -> None:
        project = self._require_project()
        project.close(discard_changes=bool(params.get("discard_changes")))
        self.project = None

    # -------------------------------------------------------------- données
    def data_inspect(self, params: dict[str, Any]) -> dict[str, Any]:
        from statpfe.data.store import DataStore

        return DataStore.inspect(params.get("path"), params.get("options"))

    def data_import(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        dataset_id = project.data.import_file(params.get("path"), params.get("options"), params.get("name"))
        return {"dataset_id": dataset_id, "project": project.describe()}

    def data_get(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._require_project().data.get(params.get("dataset_id"))

    def data_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.data.delete_dataset(params.get("dataset_id"))
        return project.describe()

    def data_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._require_project().data.preview(
            params.get("dataset_id"), params.get("version_id"), params.get("offset"), params.get("limit"),
            bool(params.get("reveal_identifiers")))

    def data_quality(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._require_project().data.version_quality(params.get("dataset_id"), params.get("version_id"))

    def data_update_variable(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.data.update_variable(params.get("dataset_id"), params.get("key"), params.get("changes"))
        return self._dataset_and_project(project, params)

    def data_create_version(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        version_id = project.data.create_version(params.get("dataset_id"), params.get("name"),
                                                 params.get("from_version_id"))
        return {"version_id": version_id, **self._dataset_and_project(project, params)}

    def data_rename_version(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.data.rename_version(params.get("version_id"), params.get("name"))
        return self._dataset_and_project(project, params)

    def data_delete_version(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.data.delete_version(params.get("version_id"))
        return self._dataset_and_project(project, params)

    def data_add_step(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.data.add_step(params.get("version_id"), params.get("step"))
        return self._dataset_and_project(project, params)

    def data_remove_step(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.data.remove_step(params.get("version_id"), params.get("index"))
        return self._dataset_and_project(project, params)

    # -------------------------------------------------------------- analyses
    def analysis_catalog(self, _: dict[str, Any]) -> dict[str, Any]:
        from statpfe.stats.catalog import catalog

        return catalog()

    def analysis_run(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        analysis_id = project.analyses.run(params.get("dataset_id"), params.get("version_id"),
                                           params.get("method"), params.get("params"), params.get("title"),
                                           params.get("choice"))
        return {"analysis": project.analyses.get(analysis_id), "project": project.describe()}

    def analysis_advise(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._require_project().analyses.advise(params.get("dataset_id"), params.get("version_id"),
                                                       params.get("request"))

    def analysis_levels(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        return self._require_project().analyses.levels(params.get("dataset_id"), params.get("version_id"),
                                                       params.get("key"))

    def analysis_list(self, _: dict[str, Any]) -> list[dict[str, Any]]:
        return self._require_project().analyses.list()

    def analysis_get(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._require_project().analyses.get(params.get("analysis_id"))

    def analysis_update(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.analyses.update(params.get("analysis_id"), params.get("changes"))
        return {"analysis": project.analyses.get(params.get("analysis_id")), "project": project.describe()}

    def analysis_delete(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        project.analyses.delete(params.get("analysis_id"))
        return project.describe()

    def analysis_reproduce(self, params: dict[str, Any]) -> dict[str, Any]:
        project = self._require_project()
        report = project.analyses.reproduce(params.get("analysis_id"))
        return {"report": report, "project": project.describe()}

    @staticmethod
    def _dataset_and_project(project: Project, params: dict[str, Any]) -> dict[str, Any]:
        return {"dataset": project.data.get(params.get("dataset_id")), "project": project.describe()}

    def shutdown(self) -> None:
        """Arrêt du moteur : les modifications non enregistrées sont abandonnées,
        le fichier projet sur disque reste intact."""
        if self.project:
            self.project.close(discard_changes=True)
            self.project = None

    # -------------------------------------------------------------- interne
    def _activate(self, project: Project) -> dict[str, Any]:
        self.project = project
        self._remember(project)
        return project.describe()

    @staticmethod
    def _remember(project: Project) -> None:
        from statpfe.core.project import now_iso

        recent.remember(project.path, project.study.title, now_iso())

    def _ensure_none_open(self) -> None:
        if self.project is not None:
            raise ProjectAlreadyOpenError()

    def _require_project(self) -> Project:
        if self.project is None:
            raise NoProjectOpenError()
        return self.project

    # -------------------------------------------------------------- protocole
    def handle(self, line: str) -> dict[str, Any] | None:
        try:
            request = json.loads(line)
        except ValueError:
            return _error(None, PARSE_ERROR, "Message illisible.")
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "Requête invalide.")
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        if not isinstance(method, str):
            return _error(req_id, INVALID_REQUEST, "Requête invalide.")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return _error(req_id, INVALID_PARAMS, "Paramètres invalides.")
        handler = self.methods.get(method)
        if handler is None:
            return _error(req_id, METHOD_NOT_FOUND, f"Méthode inconnue : {method}.")
        try:
            result = handler(params)
        except StatpfeError as exc:
            return _error(req_id, BUSINESS_ERROR, exc.message, {"kind": exc.code})
        except Exception:  # noqa: BLE001 - toute erreur imprévue doit rester lisible
            log.exception("Erreur interne pendant %s", method)
            return _error(
                req_id,
                INTERNAL_ERROR,
                "Une erreur interne est survenue. Le fichier projet enregistré n'a pas été modifié.",
                {"kind": "interne"},
            )
        if req_id is None:
            return None  # notification : pas de réponse
        return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _require_str(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value:
        raise ValidationError(f"Paramètre « {key} » manquant.")
    return value


def _error(req_id: Any, code: int, message: str, data: dict[str, Any] | None = None):
    err: dict[str, Any] = {"code": code, "message": message}
    if data:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def serve(stdin: TextIO, stdout: TextIO, engine: Engine | None = None) -> None:
    engine = engine or Engine()
    try:
        for line in stdin:
            if not line.strip():
                continue
            response = engine.handle(line)
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()
    finally:
        engine.shutdown()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(message)s"
    )
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", newline="\n")
    # Tout `print` accidentel part sur la sortie d'erreur pour ne pas corrompre le protocole.
    sys.stdout = sys.stderr
    log.info("Moteur STATPFE %s prêt", __version__)
    serve(stdin, stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
