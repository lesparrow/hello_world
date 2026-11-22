"""Rapports : contenu, contrôles avant export, fichiers Word et PDF relus et comparés aux résultats."""

from __future__ import annotations

import json
import sqlite3
from datetime import date

import docx
import pypdf
import pytest

from statpfe.core.project import Project
from statpfe.errors import ValidationError
from statpfe.report import fmt
from statpfe.report.build import build, french_date
from statpfe.report.options import SECTIONS, TEMPLATES, clean_options, templates
from statpfe.rpc.server import Engine

NAMES = ["Alami", "Bennani", "Chraibi", "Daoudi", "Fassi", "Ghali", "Hajji", "Jabri"]


def survey_csv(tmp_path):
    lines = ["id;Nom;Email;Sexe;Note;Tutorat;Satisfaction"]
    for i in range(40):
        name = f"{NAMES[i % 8]}{i}"
        tut = "oui" if i % 2 else "non"
        note = 9 + (i * 7 % 11) * 0.5 + (2 if tut == "oui" else 0)
        lines.append(f"{i + 1};{name};{name.lower()}@exemple.ma;{'F' if i % 3 else 'M'};"
                     f"{str(note).replace('.', ',')};{tut};{1 + i * 3 % 5}")
    path = tmp_path / "enquete.csv"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def project(tmp_path):
    p = Project.create(str(tmp_path / "etude.statpfe"), {
        "title": "Tutorat et réussite", "problem_statement": "Le tutorat améliore-t-il la réussite ?",
        "objectives": "Mesurer l'effet du tutorat.", "population": "Étudiants de L1",
        "sampling_method": "Volontaires", "planned_sample_size": 50,
        "hypotheses": ["Les tutorés ont de meilleures notes.", "La satisfaction est liée à la note."]})
    ds = p.data.import_file(str(survey_csv(tmp_path)), {}, "Enquête")
    request = {"objective": "compare_groups", "variables": {"outcome": "Note", "group": "Tutorat"},
               "independent": True}
    ids = {
        "welch": p.analyses.run(ds, None, "welch", {"outcome": "Note", "group": "Tutorat", "levels": ["non", "oui"]},
                                choice={"mode": "assistant", "request": request, "purpose": "confirmatoire",
                                        "hypothesis": 0}),
        "desc": p.analyses.run(ds, None, "descriptives", {"variables": ["Note"], "group": "Tutorat"},
                               choice={"mode": "direct", "purpose": "exploratoire"}),
        "chi2": p.analyses.run(ds, None, "chi2", {"row": "Sexe", "col": "Tutorat"}),
    }
    p.ds = ds
    p.ids = ids
    yield p
    p.close(discard_changes=True)


def options(p, **over):
    o = p.reports.options()
    o["cover"].update(authors="Nadia B.", institution="Université Y", year="2025-2026", city="Rabat")
    o.update(over)
    return o


# ---------------------------------------------------------------------- mise en forme
@pytest.mark.parametrize("value,kind,expected", [
    (0.0004, "p", "< 0,001"), (0.0123, "p", "0,012"), (0.05, "p", "0,050"), (57.98, "df", "57,98"),
    (12, "df", "12"), (-1.2346, "value", "−1,235"), (None, "value", "non calculable"), ("+∞", "ci", "+∞"),
    (1234.5, "value", "1 234,500"), (-0.0001, "value", "0,000"),
])
def test_stat_format_matches_interface(value, kind, expected):
    assert fmt.stat(value, kind) == expected


@pytest.mark.parametrize("value,kind,expected", [
    (None, "num", "—"), (True, None, "oui"), (12, "int", "12"), (0.525, "pct", "52,5 %"),
    (3.14159, "num", "3,142"), (0.00012, "num", "1,200e−4"), (2.5e7, "num", "2,500e7"), ("F", "text", "F"),
])
def test_cell_format_matches_interface(value, kind, expected):
    assert fmt.cell(value, kind) == expected


def test_french_date():
    assert french_date(date(2026, 11, 1)) == "1er novembre 2026"
    assert french_date(date(2026, 3, 22)) == "22 mars 2026"


# ---------------------------------------------------------------------- options
def test_templates_and_option_validation():
    t = templates()
    assert {x["key"] for x in t["templates"]} == set(TEMPLATES)
    assert {x["key"] for x in t["sections"]} == set(SECTIONS)
    o = clean_options({"template": "article"})
    assert not o["sections"]["cover"] and o["sections"]["inferential"]
    for bad in ([], {"template": "roman"}, {"cover": {"pirate": "x"}}, {"cover": {"authors": "x" * 400}},
                {"sections": {"cover": "oui"}}, {"analyses": [1, 1]}, {"analyses": ["1"]}, {"figures": "oui"}):
        with pytest.raises(ValidationError):
            clean_options(bad)


def test_options_are_saved_in_the_project(project, tmp_path):
    project.save()
    project.reports.save_options(project.reports.options())
    assert not project.dirty  # options par défaut inchangées : le projet n'est pas modifié
    o = options(project, template="these")
    project.reports.save_options(o)
    assert project.dirty
    project.save()
    path = project.path
    project.close()
    reopened = Project.open(str(path))
    try:
        got = reopened.reports.options()
        assert got["template"] == "these" and got["cover"]["authors"] == "Nadia B."
        assert sorted(got["analyses"]) == sorted(o["analyses"])
    finally:
        reopened.close(discard_changes=True)


# ---------------------------------------------------------------------- contenu
def test_content_numbering_and_traceability(project):
    o = options(project)
    o["sections"]["annex_journal"] = True
    doc = build(project, clean_options(o), today=date(2026, 11, 22))
    text = doc.text()
    outline = doc.outline()
    # Tableaux et figures numérotés sans trou, chacun avec sa source quand il vient d'une analyse
    tables = [o["text"] for o in outline if o["kind"] == "table"]
    figures = [o["text"] for o in outline if o["kind"] == "figure"]
    assert [int(t.split(".")[0].split()[1]) for t in tables] == list(range(1, len(tables) + 1))
    assert [int(t.split(".")[0].split()[1]) for t in figures] == list(range(1, len(figures) + 1))
    assert len(figures) >= 3
    # Descriptives d'abord (analyse 1), puis inférentielles
    headings = [o["text"] for o in outline if o["kind"] == "heading"]
    assert any(h.endswith("Analyse 1 : Statistiques descriptives") for h in headings)
    assert headings.index(next(h for h in headings if "Statistiques descriptives" == h.split(". ", 1)[-1])) < \
        headings.index(next(h for h in headings if h.endswith("Analyses inférentielles")))
    # Étude, hypothèses, choix, traçabilité, avertissement
    for expected in ("Le tutorat améliore-t-il la réussite ?", "H1. Les tutorés", "Mise à l'épreuve par",
                     "Aucune analyse de ce rapport n'est liée", "Méthode recommandée et retenue : Test t de Welch",
                     "Empreinte des données (SHA-256)", "aucune validation scientifique", "Nadia B.",
                     "À rédiger par l'auteur", "Journal du projet", "analyse exploratoire", "22 novembre 2026"):
        assert expected in text, expected
    welch = project.analyses.get(project.ids["welch"])
    assert welch["data_fingerprint"] in text
    t_stat = next(s for s in welch["result"]["summary"] if s["key"] == "t")
    assert fmt.stat(t_stat["value"], t_stat["kind"], t_stat["digits"]) in text


def test_identifier_values_never_appear(project):
    o = options(project)
    o["sections"]["annex_journal"] = True
    text = build(project, clean_options(o)).text()
    assert "Nom" in text and "Email" in text  # le dictionnaire les cite par leur nom
    for i in range(40):
        name = f"{NAMES[i % 8]}{i}"
        assert name not in text and "@exemple.ma" not in text


def test_sections_can_be_disabled(project):
    o = options(project)
    o["sections"] = {k: k == "inferential" for k in SECTIONS}
    doc = build(project, clean_options(o))
    headings = [x["text"] for x in doc.outline() if x["kind"] == "heading" and x["level"] == 1]
    assert headings == ["1. Analyses inférentielles"]
    assert "Statistiques descriptives" not in doc.text().split("Analyses inférentielles")[1]


# ---------------------------------------------------------------------- contrôles
def test_checks_pass_on_consistent_project(project):
    res = project.reports.check(options(project))
    c = res["checks"]
    assert c["blocking"] == 0
    assert any("identiques aux résultats enregistrés" in x for x in c["passed"])
    assert any("Aucun texte rédigé avec l'aide d'une IA" in x for x in c["passed"])
    titles = [i["title"] for i in c["items"]]
    assert "Hypothèse(s) sans analyse liée" in titles  # H2
    assert any("analyse exploratoire" in t for t in titles)
    assert res["outline"]


def test_modified_data_blocks_export(project, tmp_path):
    project.data.update_variable(project.ds, "Note", {"missing_codes": ["9,0"]})
    c = project.reports.check(options(project))["checks"]
    assert c["blocking"] >= 1
    assert any(i["level"] == "bloquant" and i["analysis_id"] == project.ids["welch"] for i in c["items"])
    with pytest.raises(ValidationError, match="bloquant"):
        project.reports.export(str(tmp_path / "r.docx"), "docx", options(project))
    assert not (tmp_path / "r.docx").exists()


def test_tampered_result_is_detected(project):
    conn: sqlite3.Connection = project._conn
    row = conn.execute("SELECT result FROM analyses WHERE id = ?", (project.ids["chi2"],)).fetchone()
    result = json.loads(row[0])
    result["tables"][0]["rows"][0][1] += 1  # un effectif modifié à la main
    conn.execute("UPDATE analyses SET result = ? WHERE id = ?", (json.dumps(result), project.ids["chi2"]))
    c = project.reports.check(options(project))["checks"]
    item = next(i for i in c["items"] if i["analysis_id"] == project.ids["chi2"] and i["level"] == "bloquant")
    assert "recalcul" in item["title"]


def test_missing_limits_and_empty_selection(project):
    o = options(project, analyses=[])
    c = project.reports.check(o)["checks"]
    assert c["blocking"] == 1 and c["items"][0]["title"] == "Aucune analyse sélectionnée"
    # Avertissement important d'une analyse alors que la section Limites est désactivée
    project.analyses.run(project.ds, None, "welch", {"outcome": "Satisfaction", "group": "Sexe"})
    o = options(project)
    o["sections"]["limits"] = False
    c = project.reports.check(o)["checks"]
    if any(i["level"] == "important" for i in c["items"]):
        assert any(i["title"] == "Section « Limites » désactivée" for i in c["items"])


# ---------------------------------------------------------------------- fichiers
def test_export_docx_is_readable_and_matches_results(project, tmp_path):
    path = tmp_path / "rapport.docx"
    out = project.reports.export(str(path), "docx", options(project))
    assert out["file_name"] == "rapport.docx" and out["figures"] >= 3 and out["tables"] >= 5
    d = docx.Document(str(path))
    body = "\n".join(p.text for p in d.paragraphs)
    cells = "\n".join(c.text for t in d.tables for r in t.rows for c in r.cells)
    assert d.core_properties.title == "Tutorat et réussite" and d.core_properties.author == "Nadia B."
    assert "Tutorat et réussite" in body and "Tableau" in body and "Figure" in body
    assert "aucune validation scientifique" in body
    assert "non validé scientifiquement" in d.sections[0].footer.paragraphs[0].text
    # Toutes les statistiques de synthèse du test de Welch figurent telles que mises en forme
    welch = project.analyses.get(project.ids["welch"])
    for s in welch["result"]["summary"]:
        assert fmt.stat(s["value"], s["kind"], s["digits"]) in cells, s["label"]
    assert len(d.inline_shapes) == out["figures"]  # images identiques partagées : on compte les insertions
    xml = d.element.xml
    assert "SEQ Tableau" in xml and "SEQ Figure" in xml and "TOC" in xml
    assert any(j.action == "rapport" for j in project.journal())


def test_export_pdf_is_readable_and_matches_results(project, tmp_path):
    path = tmp_path / "rapport.pdf"
    out = project.reports.export(str(path), "pdf", options(project, template="memoire"))
    reader = pypdf.PdfReader(str(path))
    assert len(reader.pages) >= 5
    assert reader.metadata.title == "Tutorat et réussite" and reader.metadata.author == "Nadia B."
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "MÉMOIRE DE MASTER" in text and "Sommaire" in text
    welch = project.analyses.get(project.ids["welch"])
    for s in welch["result"]["summary"]:
        assert fmt.stat(s["value"], s["kind"], s["digits"]).replace(" ", " ") in text.replace(" ", " ")
    fonts = set()
    for page in reader.pages:
        for f in (page["/Resources"].get("/Font") or {}).values():
            fonts.add(str(f.get_object()["/BaseFont"]))
    assert any("DejaVuSans" in f for f in fonts)
    assert out["size"] == path.stat().st_size


@pytest.mark.parametrize("raw,fmt_", [("rapport.docx", "docx"), ("/tmp/r.pdf", "docx"), ("/nope/dir/r.pdf", "pdf"),
                                       (None, "pdf"), ("/tmp/r.odt", "odt")])
def test_export_path_validation(project, raw, fmt_):
    with pytest.raises(ValidationError):
        project.reports.export(raw, fmt_, options(project))


def test_rpc_report_methods(project, tmp_path):
    engine = Engine()
    engine.project = project
    t = engine.methods["report.templates"]({})
    assert t["formats"] == [{"key": "docx", "label": "Word (.docx)"}, {"key": "pdf", "label": "PDF"}]
    o = engine.methods["report.options"]({})
    res = engine.methods["report.check"]({"options": o})
    assert res["checks"]["blocking"] == 0
    exp = engine.methods["report.export"]({"path": str(tmp_path / "x.pdf"), "format": "pdf", "options": o})
    assert exp["export"]["file_name"] == "x.pdf"
    json.dumps(res)
    engine.project = None
