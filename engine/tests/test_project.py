import json
import os
import sqlite3
import zipfile

import pytest

from statpfe.core.project import Project
from statpfe.errors import ProjectFileError, UnsavedChangesError, ValidationError


def test_create_close_reopen_roundtrip(tmp_path, study):
    path = tmp_path / "etude.statpfe"
    p = Project.create(str(path), study)
    assert path.is_file()
    assert not p.dirty
    project_id = p.project_id
    p.close()

    q = Project.open(str(path))
    assert q.project_id == project_id
    assert q.study.to_dict() == {**study}
    assert [e.action for e in q.journal()] == ["ouverture", "creation"]
    assert not q.dirty
    q.close()


def test_update_marks_dirty_and_save_persists(tmp_path, study):
    path = tmp_path / "etude.statpfe"
    p = Project.create(str(path), study)
    changed = p.update_study({"objectives": "Nouvel objectif", "hypotheses": ["H1", "H2"]})
    assert changed == ["objectives", "hypotheses"]
    assert p.dirty
    p.save()
    assert not p.dirty
    p.close()
    q = Project.open(str(path))
    assert q.study.objectives == "Nouvel objectif"
    assert q.study.hypotheses == ["H1", "H2"]
    q.close()


def test_noop_update_does_not_dirty(tmp_path, study):
    p = Project.create(str(tmp_path / "e.statpfe"), study)
    assert p.update_study({"title": study["title"]}) == []
    assert not p.dirty
    p.close()


def test_journal_never_contains_study_content(tmp_path, study):
    path = tmp_path / "e.statpfe"
    p = Project.create(str(path), study)
    p.update_study({"problem_statement": "SECRET-CONTENU-123"})
    p.save()
    p.close()
    with zipfile.ZipFile(path) as zf:
        zf.extract("project.sqlite", tmp_path / "x")
    conn = sqlite3.connect(tmp_path / "x" / "project.sqlite")
    rows = conn.execute("SELECT summary, details FROM journal").fetchall()
    conn.close()
    assert rows and all("SECRET" not in s and "SECRET" not in d for s, d in rows)


def test_close_with_unsaved_changes_is_refused(tmp_path, study):
    path = tmp_path / "e.statpfe"
    p = Project.create(str(path), study)
    p.update_study({"objectives": "changé"})
    with pytest.raises(UnsavedChangesError):
        p.close()
    p.close(discard_changes=True)
    q = Project.open(str(path))
    assert q.study.objectives == study["objectives"]  # rien n'a été écrit
    q.close()


def test_close_removes_workdir(tmp_path, study):
    p = Project.create(str(tmp_path / "e.statpfe"), study)
    p.close()
    assert os.listdir(tmp_path / "work") == []


def test_save_keeps_backup_of_previous_version(tmp_path, study):
    path = tmp_path / "e.statpfe"
    p = Project.create(str(path), study)
    p.update_study({"objectives": "v2"})
    p.save()
    p.close()
    backup = tmp_path / "e.statpfe.bak"
    assert backup.is_file()
    # La sauvegarde est elle-même un projet valide, dans l'état précédent.
    renamed = tmp_path / "restaure.statpfe"
    backup.rename(renamed)
    r = Project.open(str(renamed))
    assert r.study.objectives == study["objectives"]
    r.close()


def test_no_temporary_file_left_after_save(tmp_path, study):
    p = Project.create(str(tmp_path / "e.statpfe"), study)
    p.save()
    p.close()
    assert sorted(f.name for f in tmp_path.iterdir() if f.is_file()) == [
        "e.statpfe",
        "e.statpfe.bak",
    ]


def test_save_as_duplicates_and_switches(tmp_path, study):
    a = tmp_path / "a.statpfe"
    b = tmp_path / "b.statpfe"
    p = Project.create(str(a), study)
    p.save_as(str(b))
    assert p.path == b
    p.update_study({"objectives": "seulement dans b"})
    p.save()
    p.close()
    assert Project.open(str(a)).study.objectives == study["objectives"]


def test_create_refuses_existing_file(tmp_path, study):
    path = tmp_path / "e.statpfe"
    Project.create(str(path), study).close()
    with pytest.raises(ProjectFileError):
        Project.create(str(path), study)
    Project.create(str(path), {"title": "Remplacé"}, overwrite=True).close()
    assert Project.open(str(path)).study.title == "Remplacé"


@pytest.mark.parametrize(
    "raw",
    ["", "relatif.statpfe", "/tmp/sans_extension", "/dossier/inexistant/e.statpfe", "/tmp/\x00.statpfe"],
)
def test_invalid_paths_on_create(raw, study):
    with pytest.raises((ValidationError, ProjectFileError)):
        Project.create(raw, study)


def test_open_missing_file(tmp_path):
    with pytest.raises(ProjectFileError):
        Project.open(str(tmp_path / "absent.statpfe"))


def test_open_not_a_zip(tmp_path):
    path = tmp_path / "faux.statpfe"
    path.write_text("ceci n'est pas un projet")
    with pytest.raises(ProjectFileError, match="pas un projet STATPFE valide"):
        Project.open(str(path))


def test_open_zip_without_manifest(tmp_path):
    path = tmp_path / "faux.statpfe"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("autre.txt", "x")
    with pytest.raises(ProjectFileError):
        Project.open(str(path))


def test_open_newer_format_is_refused(tmp_path, study):
    path = tmp_path / "e.statpfe"
    Project.create(str(path), study).close()
    _rewrite_manifest(path, format_version=99)
    with pytest.raises(ProjectFileError, match="version plus récente"):
        Project.open(str(path))


def test_open_corrupted_database(tmp_path, study):
    path = tmp_path / "e.statpfe"
    Project.create(str(path), study).close()
    with zipfile.ZipFile(path) as zf:
        manifest = zf.read("manifest.json")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", manifest)
        zf.writestr("project.sqlite", b"SQLite format 3\x00" + b"\xff" * 2000)
    with pytest.raises(ProjectFileError, match="endommag"):
        Project.open(str(path))


def test_zip_slip_entries_are_ignored(tmp_path, study):
    path = tmp_path / "e.statpfe"
    Project.create(str(path), study).close()
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr("../../evil.txt", "pwned")
    p = Project.open(str(path))
    p.close()
    assert not (tmp_path.parent / "evil.txt").exists()
    assert not any(tmp_path.rglob("evil.txt"))


def _rewrite_manifest(path, **changes):
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        db = zf.read("project.sqlite")
    manifest.update(changes)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("project.sqlite", db)
