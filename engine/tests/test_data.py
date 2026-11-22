import zipfile

import pandas as pd
import pytest

from statpfe.core.project import Project
from statpfe.data.sources import ReadOptions, SourceError, parse
from statpfe.data.store import DataStore, fingerprint
from statpfe.data.types import parse_number
from statpfe.errors import ValidationError

from data_helpers import SURVEY_CSV, write_csv, write_xlsx


@pytest.fixture
def project(tmp_path, study):
    p = Project.create(str(tmp_path / "etude.statpfe"), study)
    yield p
    p.close(discard_changes=True)


def var(ds, key):
    return next(v for v in ds["variables"] if v["key"] == key)


# --------------------------------------------------------------- lecture des sources
@pytest.mark.parametrize("text,expected", [
    ("12,5", 12.5), ("12.5", 12.5), ("-3", -3.0), ("1 234,5", 1234.5), ("1 234", 1234.0),
    ("1.234,5", 1234.5), ("1.234", 1.234), ("0.125", 0.125), ("1.234.567", 1234567.0), ("2e3", 2000.0), (",5", 0.5), ("abc", None), ("12,5,3", None), ("", None),
])
def test_parse_number(text, expected):
    assert parse_number(text) == expected


def test_inspect_detects_encoding_delimiter_and_types(tmp_path):
    info = DataStore.inspect(str(write_csv(tmp_path)), None)
    assert info["options"]["encoding"] == "cp1252"
    assert info["options"]["delimiter"] == ";"
    assert info["rows"] == 11
    types = {c["key"]: c["type"] for c in info["columns"]}
    assert types == {"id": "numerique", "Nom": "texte", "Email": "texte", "Sexe": "texte", "Âge": "numerique",
                     "Note": "numerique", "Tutorat": "booleen", "Satisfaction": "numerique",
                     "Date entretien": "date"}
    assert any("UTF-8" in n for n in info["notes"])
    # Les colonnes identifiantes sont masquées dès l'aperçu d'import.
    email_col = [c["key"] for c in info["columns"]].index("Email")
    assert info["preview"][0][email_col] == "•••"


def test_utf8_bom_and_comma_delimiter(tmp_path):
    path = write_csv(tmp_path, text="﻿a,b\n1,été\n2,hiver\n", encoding="utf-8")
    info = DataStore.inspect(str(path), None)
    assert info["options"] == {"encoding": "utf-8", "delimiter": ",", "sheet": None, "header": True}
    assert info["preview"][0] == ["1", "été"]
    assert info["notes"] == []


def test_wrong_encoding_is_flagged(tmp_path):
    path = write_csv(tmp_path, text="ville\nFès\nSalé\n", encoding="utf-8")
    info = DataStore.inspect(str(path), {"encoding": "cp1252"})
    assert any("mal décodés" in n for n in info["notes"])


def test_irregular_rows_and_empty_header(tmp_path):
    path = write_csv(tmp_path, text="a;;a\n1;2;3\n4;5\n6;7;8;9\n", encoding="utf-8")
    info = DataStore.inspect(str(path), None)
    assert [c["key"] for c in info["columns"]] == ["a", "V2", "a_2", "V4"]
    assert any("nombre de colonnes" in n for n in info["notes"])


def test_no_header_option(tmp_path):
    path = write_csv(tmp_path, text="1;2\n3;4\n", encoding="utf-8")
    info = DataStore.inspect(str(path), {"header": False})
    assert info["rows"] == 2 and [c["key"] for c in info["columns"]] == ["V1", "V2"]


@pytest.mark.parametrize("name,content,message", [
    ("vide.csv", b"", "vide"),
    ("blanc.csv", b"\n\n  \n", "aucune ligne"),
    ("ancien.xls", b"x", ".xls"),
    ("spss.sav", b"x", "SPSS"),
    ("image.png", b"x", "non pris en charge"),
    ("faux.xlsx", b"pas un classeur", "illisible"),
])
def test_unreadable_files(tmp_path, name, content, message):
    path = tmp_path / name
    path.write_bytes(content)
    with pytest.raises(SourceError, match=message):
        DataStore.inspect(str(path), None)


def test_excel_sheets_types_and_bool(tmp_path):
    info = DataStore.inspect(str(write_xlsx(tmp_path)), None)
    assert info["sheets"] == ["Réponses", "Notes"]
    assert info["options"]["sheet"] == "Réponses"
    assert {c["key"]: c["type"] for c in info["columns"]} == {
        "Groupe": "texte", "Score": "numerique", "Réussite": "booleen"}
    other = DataStore.inspect(str(write_xlsx(tmp_path, "b.xlsx")), {"sheet": "Notes"})
    assert other["rows"] == 1
    with pytest.raises(SourceError, match="n'existe pas"):
        DataStore.inspect(str(write_xlsx(tmp_path, "c.xlsx")), {"sheet": "Absente"})


def test_values_are_never_silently_converted(tmp_path):
    table = parse("code\n007\n010\n".encode(), "csv", ReadOptions())
    assert list(table.frame["code"]) == ["007", "010"]


# --------------------------------------------------------------- import et dictionnaire
def test_import_keeps_exact_copy_and_survives_reopen(tmp_path, project):
    src = write_csv(tmp_path)
    original_bytes = src.read_bytes()
    ds_id = project.data.import_file(str(src), None, None)
    ds = project.data.get(ds_id)
    assert ds["name"] == "enquete"
    assert ds["original"]["rows"] == 11 and ds["original"]["columns"] == 9
    project.save()
    project.close()
    with zipfile.ZipFile(project.path) as zf:
        members = [n for n in zf.namelist() if n.startswith("sources/")]
        assert len(members) == 1 and zf.read(members[0]) == original_bytes
    assert src.read_bytes() == original_bytes  # le fichier de l'utilisateur n'est pas touché

    reopened = Project.open(str(project.path))
    ds2 = reopened.data.get(ds_id)
    assert ds2["original"]["fingerprint"] == ds["original"]["fingerprint"]
    reopened.close()


def test_quality_report_on_survey(tmp_path, project):
    ds = project.data.get(project.data.import_file(str(write_csv(tmp_path)), None, None))
    q = ds["quality"]
    assert q["duplicates"] == 1
    age = next(v for v in q["variables"] if v["key"] == "Âge")
    assert age["invalid"] == 1 and age["invalid_examples"] == ["NSP"]
    note = next(v for v in q["variables"] if v["key"] == "Note")
    assert note["missing"] == 1
    assert var(ds, "Email")["potential_identifier"] and var(ds, "Nom")["potential_identifier"]
    assert var(ds, "Email")["role"] == "identifiant"
    assert not var(ds, "Sexe")["potential_identifier"]
    messages = " ".join(i["message"] for i in q["issues"])
    assert "doublons" in messages and "NSP" in messages


def test_declaring_missing_codes_and_changing_type(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    project.data.update_variable(ds_id, "Âge", {"missing_codes": ["NSP", "99"]})
    q = project.data.get(ds_id)["quality"]
    age = next(v for v in q["variables"] if v["key"] == "Âge")
    assert age["invalid"] == 0 and age["declared_missing"] == 2 and age["missing"] == 2
    project.data.update_variable(ds_id, "Satisfaction", {"level": "ordinal", "label": "Satisfaction (1-5)"})
    ds = project.data.get(ds_id)
    assert var(ds, "Satisfaction")["level"] == "ordinal"
    project.data.update_variable(ds_id, "Âge", {"type": "texte"})
    assert var(project.data.get(ds_id), "Âge")["level"] == "nominal"


def test_dictionary_validation(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    with pytest.raises(ValidationError, match="déjà"):
        project.data.update_variable(ds_id, "Note", {"name": "sexe"})
    with pytest.raises(ValidationError, match="compatible"):
        project.data.update_variable(ds_id, "Sexe", {"level": "continu"})
    with pytest.raises(ValidationError):
        project.data.update_variable(ds_id, "Sexe", {"type": "inconnu"})
    with pytest.raises(ValidationError):
        project.data.update_variable(ds_id, "Sexe", {"key": "x"})
    with pytest.raises(ValidationError):
        project.data.update_variable(ds_id, "absente", {"label": "x"})


def test_preview_masks_identifiers_and_paginates(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    page = project.data.preview(ds_id, None, 0, 3, False)
    assert page["total"] == 11 and len(page["rows"]) == 3
    email = [c["key"] for c in page["columns"]].index("Email")
    assert page["rows"][0][email] == "•••" and page["columns"][email]["masked"]
    revealed = project.data.preview(ds_id, None, 0, 1, True)
    assert revealed["rows"][0][email] == "a.alami@exemple.ma"
    note = [c["key"] for c in page["columns"]].index("Note")
    assert page["rows"][0][note] == 12.5 and page["rows"][1][note] == 9.75
    tut = [c["key"] for c in page["columns"]].index("Tutorat")
    assert page["rows"][0][tut] == "oui"
    date = [c["key"] for c in page["columns"]].index("Date entretien")
    assert page["rows"][0][date] == "2025-03-15"
    last = project.data.preview(ds_id, None, 10, 100, False)
    assert len(last["rows"]) == 1 and last["row_numbers"] == [11]


# --------------------------------------------------------------- versions et transformations
def test_versions_and_reversible_steps(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    original_fp = project.data.get(ds_id)["original"]["fingerprint"]
    v = project.data.create_version(ds_id, "Analyse principale", None)
    project.data.add_step(v, {"op": "remove_duplicates"})
    project.data.add_step(v, {"op": "filter_rows", "variable": "Sexe", "operator": "eq", "value": "F"})
    project.data.add_step(v, {"op": "compute", "function": "zscore", "variable": "Note", "new_name": "Note_z"})
    ds = project.data.get(ds_id)
    version = ds["versions"][0]
    assert [s["rows_after"] for s in version["steps"]] == [10, 5, 5]
    assert version["rows"] == 5 and version["columns"] == 10
    df, variables, _ = project.data.materialize(ds_id, v)
    assert abs(df["Note_z"].mean()) < 1e-12 and abs(df["Note_z"].std(ddof=1) - 1) < 1e-12
    # L'original n'a pas bougé.
    assert ds["original"]["fingerprint"] == original_fp and ds["original"]["rows"] == 11
    # Retirer le filtre : la version est recalculée.
    project.data.remove_step(v, 1)
    assert project.data.get(ds_id)["versions"][0]["rows"] == 10


def test_remove_step_refused_when_a_later_step_depends_on_it(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    v = project.data.create_version(ds_id, "V", None)
    project.data.add_step(v, {"op": "compute", "function": "log", "variable": "Note", "new_name": "ln_note"})
    project.data.add_step(v, {"op": "filter_rows", "variable": "ln_note", "operator": "gt", "value": "2"})
    with pytest.raises(ValidationError, match="dépend"):
        project.data.remove_step(v, 0)


def test_recode_and_drop_missing(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    v = project.data.create_version(ds_id, "V", None)
    project.data.add_step(v, {"op": "recode", "variable": "Satisfaction", "new_name": "Satisfait",
                              "mapping": {"1": "Non", "2": "Non", "3": "Neutre", "4": "Oui", "5": "Oui"}})
    project.data.add_step(v, {"op": "drop_missing", "variables": ["Note"]})
    df, variables, _ = project.data.materialize(ds_id, v)
    assert len(df) == 10
    assert df["Satisfait"].value_counts().to_dict() == {"Oui": 5, "Non": 4, "Neutre": 1}
    new = next(x for x in variables if x.key == "Satisfait")
    assert new.computed and new.type == "texte"


def test_log_of_non_positive_values_warns(tmp_path, project):
    path = write_csv(tmp_path, text="x\n1\n0\n-2\n10\n", encoding="utf-8")
    ds_id = project.data.import_file(str(path), None, None)
    v = project.data.create_version(ds_id, "V", None)
    project.data.add_step(v, {"op": "compute", "function": "log10", "variable": "x", "new_name": "lx"})
    step = project.data.get(ds_id)["versions"][0]["steps"][0]
    assert "2 valeur(s)" in step["warnings"][0]
    df, _, _ = project.data.materialize(ds_id, v)
    assert df["lx"].tolist()[0] == 0.0 and df["lx"].isna().sum() == 2


@pytest.mark.parametrize("step,message", [
    ({"op": "inconnue"}, "inconnue"),
    ({"op": "filter_rows", "variable": "Sexe", "operator": "gt", "value": "F"}, "numériques"),
    ({"op": "filter_rows", "variable": "Note", "operator": "eq", "value": "abc"}, "pas un nombre"),
    ({"op": "compute", "function": "log", "variable": "Sexe", "new_name": "z"}, "numérique"),
    ({"op": "compute", "function": "log", "variable": "Note", "new_name": "Sexe"}, "déjà"),
    ({"op": "drop_missing", "variables": []}, "au moins une"),
    ({"op": "recode", "variable": "Sexe", "new_name": "s2", "mapping": {}}, "correspondance"),
    ({"op": "filter_rows", "variable": "absente", "operator": "missing"}, "inconnue"),
])
def test_invalid_steps_are_rejected(tmp_path, project, step, message):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    v = project.data.create_version(ds_id, "V", None)
    with pytest.raises(ValidationError, match=message):
        project.data.add_step(v, step)
    assert project.data.get(ds_id)["versions"][0]["steps"] == []


def test_zscore_of_constant_variable_is_refused(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path, text="x\n3\n3\n3\n", encoding="utf-8")), None, None)
    v = project.data.create_version(ds_id, "V", None)
    with pytest.raises(ValidationError, match="constante"):
        project.data.add_step(v, {"op": "compute", "function": "zscore", "variable": "x", "new_name": "z"})
    q = project.data.get(ds_id)["quality"]
    assert q["variables"][0]["constant"]


def test_dictionary_change_breaking_a_step_is_reported(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    v = project.data.create_version(ds_id, "V", None)
    project.data.add_step(v, {"op": "compute", "function": "log", "variable": "Note", "new_name": "ln"})
    project.data.update_variable(ds_id, "Note", {"type": "texte"})
    version = project.data.get(ds_id)["versions"][0]
    assert version["error"] and "numérique" in version["error"]


def test_duplicate_version_and_fingerprint_is_deterministic(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    a = project.data.create_version(ds_id, "A", None)
    project.data.add_step(a, {"op": "remove_duplicates"})
    b = project.data.create_version(ds_id, "Copie de A", a)
    versions = project.data.get(ds_id)["versions"]
    assert versions[0]["fingerprint"] == versions[1]["fingerprint"]
    project.data.rename_version(b, "B")
    project.data.delete_version(a)
    assert [x["name"] for x in project.data.get(ds_id)["versions"]] == ["B"]


def test_delete_dataset_removes_source(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    project.data.delete_dataset(ds_id)
    assert project.data.list() == [] and project.data.source_files() == []


def test_altered_source_is_detected(tmp_path, project):
    ds_id = project.data.import_file(str(write_csv(tmp_path)), None, None)
    project.save()
    project.close()
    path = project.path
    with zipfile.ZipFile(path) as zf:
        items = {n: zf.read(n) for n in zf.namelist()}
    src = next(n for n in items if n.startswith("sources/"))
    items[src] = items[src].replace(b"Alami", b"Alamo")
    with zipfile.ZipFile(path, "w") as zf:
        for n, d in items.items():
            zf.writestr(n, d)
    p = Project.open(str(path))
    with pytest.raises(Exception, match="altéré"):
        p.data.get(ds_id)
    p.close()


def test_v1_project_is_migrated(tmp_path, study):
    """Un projet créé en Phase 2 (format 1) s'ouvre et reçoit les tables de données."""
    import json, sqlite3
    path = tmp_path / "ancien.statpfe"
    Project.create(str(path), study).close()
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        zf.extract("project.sqlite", tmp_path / "x")
    db = tmp_path / "x" / "project.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript("DROP TABLE datasets; DROP TABLE variables; DROP TABLE versions;"
                       "UPDATE meta SET value = '1' WHERE key = 'format_version';")
    conn.commit(); conn.close()
    manifest["format_version"] = 1
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.write(db, "project.sqlite")
    p = Project.open(str(path))
    assert p.dirty and p.describe()["format_version"] == 4
    assert p.journal()[1].action == "migration"
    ds_id = p.data.import_file(str(write_csv(tmp_path)), None, None)
    assert p.data.get(ds_id)["original"]["rows"] == 11
    p.close(discard_changes=True)


def test_fingerprint_changes_with_content():
    a = pd.DataFrame({"x": [1.0, 2.0]})
    b = pd.DataFrame({"x": [1.0, 2.5]})
    assert fingerprint(a) == fingerprint(a.copy()) != fingerprint(b)
