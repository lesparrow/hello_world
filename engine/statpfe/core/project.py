"""Format de fichier projet `.statpfe` et cycle de vie d'un projet ouvert.

Un fichier `.statpfe` est une archive ZIP contenant :

- `manifest.json` : identification du format et versions ;
- `project.sqlite` : base de données de l'étude (informations, hypothèses, journal,
  dictionnaires des variables, versions de données, analyses enregistrées) ;
- `sources/<sha256>.<ext>` : copie exacte de chaque fichier de données importé.

Pendant l'édition, la base est décompressée dans un dossier de travail temporaire.
L'enregistrement écrit une nouvelle archive à côté du fichier cible puis la met en
place par renommage atomique, après avoir conservé la version précédente dans
`<nom>.statpfe.bak`. Le fichier projet n'est donc jamais laissé à moitié écrit.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from statpfe import __version__
from statpfe.ai.store import SCHEMA_V6_AI, AiTextStore
from statpfe.core.plan import SCHEMA_V5_PLAN, PlanStore
from statpfe.core.study import FIELD_LABELS, Study
from statpfe.core.timeutil import now_iso
from statpfe.data.store import SCHEMA_V2, DataStore
from statpfe.report.service import ReportService
from statpfe.stats.power_store import SCHEMA_V5_POWER, PowerStore
from statpfe.stats.store import MIGRATE_V3_TO_V4, SCHEMA_V3, AnalysisStore
from statpfe.errors import ProjectFileError, UnsavedChangesError, ValidationError

EXTENSION = ".statpfe"
FORMAT_NAME = "statpfe-project"
FORMAT_VERSION = 6
MANIFEST = "manifest.json"
DATABASE = "project.sqlite"
REQUIRED_MEMBERS = {MANIFEST, DATABASE}
SOURCE_MEMBER = re.compile(r"^sources/[0-9a-f]{64}\.(csv|txt|tsv|xlsx|xlsm)$")
MAX_ARCHIVE_MEMBER_SIZE = 2 * 1024**3  # 2 Go : garde-fou contre les archives piégées

SCHEMA = """
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE study (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    title TEXT NOT NULL,
    problem_statement TEXT NOT NULL DEFAULT '',
    objectives TEXT NOT NULL DEFAULT '',
    population TEXT NOT NULL DEFAULT '',
    sampling_method TEXT NOT NULL DEFAULT '',
    planned_sample_size INTEGER
);
CREATE TABLE hypotheses (
    position INTEGER PRIMARY KEY,
    text TEXT NOT NULL
);
CREATE TABLE journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '{}'
);
"""


def normalize_project_path(raw: Any, *, must_exist: bool) -> Path:
    """Valide un chemin de projet reçu de l'interface."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationError("Le chemin du projet est vide.")
    if "\x00" in raw:
        raise ValidationError("Le chemin du projet est invalide.")
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise ValidationError("Le chemin du projet doit être un chemin complet.")
    path = path.resolve()
    if path.suffix.lower() != EXTENSION:
        raise ValidationError(f"Le fichier projet doit avoir l'extension {EXTENSION}.")
    if must_exist:
        if not path.is_file():
            raise ProjectFileError(f"Le fichier « {path.name} » est introuvable.")
    else:
        if not path.parent.is_dir():
            raise ValidationError(f"Le dossier « {path.parent} » n'existe pas.")
        if path.is_dir():
            raise ValidationError("Le chemin indiqué est un dossier, pas un fichier.")
    return path


@dataclass
class JournalEntry:
    id: int
    at: str
    action: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "at": self.at, "action": self.action, "summary": self.summary}


class Project:
    """Un projet ouvert. Utiliser `Project.create` ou `Project.open`."""

    def __init__(self, path: Path, workdir: Path, conn: sqlite3.Connection):
        self.path = path
        self._workdir = workdir
        self._conn = conn
        self.dirty = False
        self._closed = False
        self.data = DataStore(conn, workdir, self._log)
        self.analyses = AnalysisStore(conn, self.data, self._log)
        self.power = PowerStore(conn, self._log)
        self.plan = PlanStore(conn, self._log, self._touch, self.power.exists)
        self.power.locked_references = self.plan.power_references
        self.analyses.plan = self.plan
        self.ai_texts = AiTextStore(conn, self._log)
        self.analyses.on_delete = self.ai_texts.delete_for_analysis
        self.reports = ReportService(self)

    # ------------------------------------------------------------------ création
    @classmethod
    def create(cls, raw_path: Any, study_data: Any, *, overwrite: bool = False) -> "Project":
        path = normalize_project_path(raw_path, must_exist=False)
        if path.exists() and not overwrite:
            raise ProjectFileError(f"Le fichier « {path.name} » existe déjà.")
        study = Study.from_dict(study_data)
        workdir = _make_workdir()
        conn = None
        try:
            conn = _connect(workdir / DATABASE)
            conn.executescript(SCHEMA)
            conn.executescript(SCHEMA_V2)
            conn.executescript(SCHEMA_V3)
            conn.executescript(SCHEMA_V5_POWER + SCHEMA_V5_PLAN)
            conn.executescript(SCHEMA_V6_AI)
            created = now_iso()
            conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [
                    ("project_id", str(uuid.uuid4())),
                    ("format_version", str(FORMAT_VERSION)),
                    ("created_at", created),
                    ("created_with", __version__),
                ],
            )
            _write_study(conn, study)
            project = cls(path, workdir, conn)
            project._log("creation", "Création du projet")
            project.save()
            return project
        except BaseException:
            if conn is not None:
                conn.close()
            shutil.rmtree(workdir, ignore_errors=True)
            raise

    # ------------------------------------------------------------------ ouverture
    @classmethod
    def open(cls, raw_path: Any) -> "Project":
        path = normalize_project_path(raw_path, must_exist=True)
        workdir = _make_workdir()
        try:
            _extract_archive(path, workdir)
            conn = _connect(workdir / DATABASE)
            _check_database(conn, path)
            migrated = _migrate(conn)
            project = cls(path, workdir, conn)
            if migrated:
                project._log("migration", f"Mise à jour du format du projet vers la version {FORMAT_VERSION}")
            project._log("ouverture", "Ouverture du projet")
            project.dirty = migrated  # l'ouverture seule ne doit pas exiger d'enregistrement
            return project
        except BaseException:
            shutil.rmtree(workdir, ignore_errors=True)
            raise

    # ------------------------------------------------------------------ lecture
    @property
    def project_id(self) -> str:
        return self._meta("project_id")

    @property
    def study(self) -> Study:
        self._ensure_open()
        row = self._conn.execute(
            "SELECT title, problem_statement, objectives, population, sampling_method,"
            " planned_sample_size FROM study WHERE id = 1"
        ).fetchone()
        hypotheses = [
            r[0] for r in self._conn.execute("SELECT text FROM hypotheses ORDER BY position")
        ]
        return Study(*row, hypotheses=hypotheses)

    def journal(self, limit: int = 200) -> list[JournalEntry]:
        self._ensure_open()
        rows = self._conn.execute(
            "SELECT id, at, action, summary FROM journal ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [JournalEntry(*r) for r in rows]

    def describe(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "file_name": self.path.name,
            "project_id": self.project_id,
            "format_version": int(self._meta("format_version")),
            "created_at": self._meta("created_at"),
            "created_with": self._meta("created_with"),
            "dirty": self.dirty,
            "study": self.study.to_dict(),
            "journal": [e.to_dict() for e in self.journal()],
            "datasets": self.data.list(),
            "analyses_count": self.analyses.count(),
            "power_count": self.power.count(),
            "ai_count": self.ai_texts.count(),
            "plan_status": self._plan_status(),
        }

    def _plan_status(self) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT version, status FROM plan_versions ORDER BY version DESC LIMIT 1").fetchone()
        if row is None:
            return None
        locked = self._conn.execute("SELECT MAX(version) FROM plan_versions WHERE status = 'verrouille'").fetchone()[0]
        return {"version": row[0], "status": row[1], "locked_version": locked}

    # ------------------------------------------------------------------ modification
    def update_study(self, changes: Any) -> list[str]:
        self._ensure_open()
        before = self.study
        after = before.merged(changes)
        changed = before.changed_fields(after)
        if not changed:
            return []
        _write_study(self._conn, after)
        labels = ", ".join(FIELD_LABELS[c] for c in changed)
        # Le journal ne garde que le nom des champs modifiés, jamais leur contenu.
        self._log("modification_etude", f"Modification : {labels}", {"fields": changed})
        return changed

    # ------------------------------------------------------------------ enregistrement
    def save(self) -> None:
        self._ensure_open()
        self._conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('saved_at', ?)", (now_iso(),)
        )
        self._conn.commit()
        _write_archive(self._conn, self.path, self.project_id, self.data.source_files())
        self.dirty = False

    def save_as(self, raw_path: Any, *, overwrite: bool = False) -> None:
        """Enregistre une copie sous un autre nom et continue à travailler sur la copie."""
        self._ensure_open()
        path = normalize_project_path(raw_path, must_exist=False)
        if path == self.path:
            self.save()
            return
        if path.exists() and not overwrite:
            raise ProjectFileError(f"Le fichier « {path.name} » existe déjà.")
        previous = self.path
        self.path = path
        try:
            self._log("duplication", f"Copie enregistrée depuis « {previous.name} »")
            self.save()
        except BaseException:
            self.path = previous
            raise

    # ------------------------------------------------------------------ fermeture
    def close(self, *, discard_changes: bool = False) -> None:
        if self._closed:
            return
        if self.dirty and not discard_changes:
            raise UnsavedChangesError()
        self._conn.close()
        shutil.rmtree(self._workdir, ignore_errors=True)
        self._closed = True

    # ------------------------------------------------------------------ interne
    def _ensure_open(self) -> None:
        if self._closed:
            raise ProjectFileError("Ce projet a été fermé.")

    def _meta(self, key: str) -> str:
        self._ensure_open()
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            raise ProjectFileError(f"Le projet est incomplet (information « {key} » absente).")
        return row[0]

    def _touch(self) -> None:
        self.dirty = True

    def _log(self, action: str, summary: str, details: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            "INSERT INTO journal (at, action, summary, details) VALUES (?, ?, ?, ?)",
            (now_iso(), action, summary, json.dumps(details or {}, ensure_ascii=False)),
        )
        self.dirty = True


# ---------------------------------------------------------------------- utilitaires
def _make_workdir() -> Path:
    base = os.environ.get("STATPFE_WORK_DIR")
    if base:
        Path(base).mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="statpfe-", dir=base or None))


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _write_study(conn: sqlite3.Connection, study: Study) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO study (id, title, problem_statement, objectives, population,"
        " sampling_method, planned_sample_size) VALUES (1, ?, ?, ?, ?, ?, ?)",
        (
            study.title,
            study.problem_statement,
            study.objectives,
            study.population,
            study.sampling_method,
            study.planned_sample_size,
        ),
    )
    conn.execute("DELETE FROM hypotheses")
    conn.executemany(
        "INSERT INTO hypotheses (position, text) VALUES (?, ?)",
        list(enumerate(study.hypotheses)),
    )


def _write_archive(conn: sqlite3.Connection, path: Path, project_id: str, source_files: list[Path]) -> None:
    tmp_dir = Path(tempfile.mkdtemp(prefix="statpfe-save-"))
    tmp_archive = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        snapshot = tmp_dir / DATABASE
        dest = sqlite3.connect(snapshot)
        with dest:
            conn.backup(dest)  # copie cohérente de la base, même si elle est ouverte
        dest.close()
        manifest = {
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "project_id": project_id,
            "saved_with": __version__,
            "saved_at": now_iso(),
        }
        with zipfile.ZipFile(tmp_archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
            zf.write(snapshot, DATABASE)
            for src in source_files:
                # Fichiers déjà compressés (xlsx) ou non : stockés tels quels, octet pour octet.
                zf.write(src, f"sources/{src.name}")
        # Ouverture en écriture : sous Windows, fsync échoue sur un fichier ouvert en lecture seule.
        with open(tmp_archive, "r+b") as fh:
            os.fsync(fh.fileno())
        if path.exists():
            shutil.copy2(path, path.with_name(path.name + ".bak"))
        os.replace(tmp_archive, path)
    except OSError as exc:
        raise ProjectFileError(f"Impossible d'enregistrer le projet : {exc.strerror or exc}.") from exc
    finally:
        tmp_archive.unlink(missing_ok=True)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _extract_archive(path: Path, workdir: Path) -> None:
    bad = ProjectFileError(
        f"« {path.name} » n'est pas un projet STATPFE valide ou il est endommagé."
    )
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
            if not REQUIRED_MEMBERS <= names:
                raise bad
            # On n'extrait que les fichiers attendus, dont le nom est vérifié par un
            # motif strict : aucune entrée de l'archive ne peut écrire en dehors du
            # dossier de travail.
            sources = sorted(n for n in names if SOURCE_MEMBER.match(n))
            for member in [*REQUIRED_MEMBERS, *sources]:
                if zf.getinfo(member).file_size > MAX_ARCHIVE_MEMBER_SIZE:
                    raise bad
            manifest = json.loads(zf.read(MANIFEST).decode("utf-8"))
            if not isinstance(manifest, dict) or manifest.get("format") != FORMAT_NAME:
                raise bad
            version = manifest.get("format_version")
            if not isinstance(version, int):
                raise bad
            if version > FORMAT_VERSION:
                raise ProjectFileError(
                    "Ce projet a été créé avec une version plus récente de STATPFE. "
                    "Mettez l'application à jour pour l'ouvrir."
                )
            with zf.open(DATABASE) as src, open(workdir / DATABASE, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if sources:
                (workdir / "sources").mkdir()
            for member in sources:
                with zf.open(member) as src, open(workdir / member, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    except ProjectFileError:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, UnicodeDecodeError) as exc:
        raise bad from exc
    except OSError as exc:
        raise ProjectFileError(f"Impossible de lire le projet : {exc.strerror or exc}.") from exc


def _check_database(conn: sqlite3.Connection, path: Path) -> None:
    bad = ProjectFileError(f"La base de données du projet « {path.name} » est endommagée.")
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise bad
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"meta", "study", "hypotheses", "journal"} <= tables:
            raise bad
        if conn.execute("SELECT COUNT(*) FROM study").fetchone()[0] != 1:
            raise bad
    except sqlite3.DatabaseError as exc:
        conn.close()
        raise bad from exc
    except ProjectFileError:
        conn.close()
        raise


def _migrate(conn: sqlite3.Connection) -> bool:
    """Met à jour la base d'un projet créé avec un format plus ancien."""
    version = int(conn.execute("SELECT value FROM meta WHERE key = 'format_version'").fetchone()[0])
    if version >= FORMAT_VERSION:
        return False
    if version < 2:
        conn.executescript(SCHEMA_V2)
    if version < 3:
        conn.executescript(SCHEMA_V3)  # crée directement la table au format 4
    elif version == 3:
        conn.executescript(MIGRATE_V3_TO_V4)
    if version < 5:
        conn.executescript(SCHEMA_V5_POWER + SCHEMA_V5_PLAN)
    if version < 6:
        conn.executescript(SCHEMA_V6_AI)
    conn.execute("UPDATE meta SET value = ? WHERE key = 'format_version'", (str(FORMAT_VERSION),))
    return True
