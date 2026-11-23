"""Phase 10 : rapports en couleurs, export LaTeX, graphiques en images, tableaux Excel."""

from __future__ import annotations

import shutil
import subprocess
import zipfile

import docx
import openpyxl
import pytest

from statpfe.errors import ValidationError
from statpfe.report import charts, exports
from statpfe.report.options import clean_options
from statpfe.report.render_latex import tex
from statpfe.rpc.server import Engine
from test_report import options, project  # noqa: F401


def test_theme_option_is_validated(project):
    assert clean_options(options(project))["theme"] == "bleu"  # thème par défaut : couleurs
    assert clean_options(options(project, theme="sobre"))["theme"] == "sobre"
    for bad in ("rose", 3, None):
        with pytest.raises(ValidationError):
            clean_options(options(project, theme=bad))


def test_colour_and_sober_word_reports(project, tmp_path):
    for theme, header in (("bleu", "1F4E79"), ("sobre", "E7E7E7")):
        path = tmp_path / f"{theme}.docx"
        project.reports.export(str(path), "docx", options(project, theme=theme))
        xml = docx.Document(str(path)).tables[0]._tbl.xml
        assert f'w:fill="{header}"' in xml
    heading = docx.Document(str(tmp_path / "bleu.docx")).styles["Heading 1"].font.color.rgb
    assert str(heading) == "1F4E79"


def test_charts_follow_theme_and_format():
    chart = {"type": "bar", "title": "Répartition", "data": {"bars": [
        {"label": "a", "count": 3, "percent": 0.5}, {"label": "b", "count": 3, "percent": 0.5}], "n": 6}}
    png = charts.render(chart, "bleu")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    svg = charts.render(chart, "vert", "svg").decode()
    assert svg.lstrip().startswith("<?xml") and "#3a8e5c" in svg.lower()
    assert "#3a8e5c" not in charts.render(chart, "sobre", "svg").decode().lower()
    with pytest.raises(ValidationError):
        charts.render(chart, "bleu", "gif")


def test_latex_special_characters():
    assert tex("50 % & x_1 {a} #2 $") == r"50 \% \& x\_1 \{a\} \#2 \$"
    assert tex("χ² ≥ 3,84 ; n₁ − n₂") == (r"\ensuremath{\chi}\textsuperscript{2} \ensuremath{\geq} 3,84 ; "
                                          r"n\ensuremath{_{1}} \ensuremath{-} n\ensuremath{_{2}}")
    assert tex("« Étude »") == r"\og{} Étude \fg{}"
    assert tex("مرحبا") == "?????"  # écriture non prise en charge par pdflatex : signalée, pas d'échec


def test_latex_export_is_a_complete_overleaf_archive(project, tmp_path):
    path = tmp_path / "rapport.zip"
    out = project.reports.export(str(path), "latex", options(project))
    assert out["file_name"] == "rapport.zip" and out["figures"] > 0
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        main = z.read("rapport.tex").decode()
    assert "rapport.tex" in names and "LISEZMOI.txt" in names
    assert sum(n.startswith("figures/") and n.endswith(".png") for n in names) == out["figures"]
    assert main.startswith("%") and r"\begin{document}" in main and main.rstrip().endswith(r"\end{document}")
    assert "Tutorat et réussite" in main and r"\begin{longtable}" in main
    with pytest.raises(ValidationError):
        project.reports.export(str(tmp_path / "rapport.tex"), "latex", options(project))


@pytest.mark.skipif(shutil.which("pdflatex") is None, reason="pdflatex absent (installé dans le CI)")
@pytest.mark.parametrize("theme", ["bleu", "sobre"])
def test_latex_export_compiles_with_pdflatex(project, tmp_path, theme):
    path = tmp_path / "rapport.zip"
    project.reports.export(str(path), "latex", options(project, theme=theme))
    work = tmp_path / "tex"
    with zipfile.ZipFile(path) as z:
        z.extractall(work)
    for _ in range(2):  # deux passes : sommaire
        run = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "rapport.tex"], cwd=work,
                             capture_output=True, text=True, timeout=180)
        assert run.returncode == 0, run.stdout[-3000:]
    assert (work / "rapport.pdf").read_bytes()[:5] == b"%PDF-"


def test_tables_to_excel_keep_real_numbers(project, tmp_path):
    path = tmp_path / "tableaux.xlsx"
    out = exports.export_tables(project, str(path))
    assert out["sheets"] == 3 and out["tables"] >= 3
    wb = openpyxl.load_workbook(path)
    assert wb.sheetnames[0] == "Sommaire" and len(wb.sheetnames) == 4
    welch = next(ws for ws in wb.worksheets if ws.title.startswith(f"A{project.ids['welch']} "))
    stats = {r[0]: r[1] for r in welch.iter_rows(values_only=True) if r[0] and r[1] is not None}
    saved = project.analyses.get(project.ids["welch"])["result"]["values"]
    assert stats["t"] == pytest.approx(saved["t"]) and isinstance(stats["t"], float)
    assert stats["Valeur p"] == pytest.approx(saved["p"])
    # Choix des analyses, et erreurs lisibles.
    assert exports.export_tables(project, str(path), analyses=[project.ids["chi2"]], power=[])["sheets"] == 1
    for bad in ([999], "1", [True]):
        with pytest.raises(ValidationError):
            exports.export_tables(project, str(path), analyses=bad)
    with pytest.raises(ValidationError):
        exports.export_tables(project, str(tmp_path / "t.csv"))


def test_chart_images_one_or_all(project, tmp_path):
    one = tmp_path / "boite.svg"
    exports.export_chart(project, str(one), "analysis", project.ids["welch"], 0, "bordeaux")
    assert one.read_text(encoding="utf-8").lstrip().startswith("<?xml")
    with pytest.raises(ValidationError):
        exports.export_chart(project, str(one), "analysis", project.ids["welch"], 99)
    with pytest.raises(ValidationError):
        exports.export_chart(project, str(tmp_path / "x.jpg"), "analysis", project.ids["welch"], 0)
    out = exports.export_charts(project, str(tmp_path), "png", "bleu")
    assert out["count"] == len(out["files"]) > 2
    assert all((tmp_path / f).read_bytes()[:4] == b"\x89PNG" for f in out["files"])
    assert all(f.startswith("analyse-") and f.endswith(".png") for f in out["files"])
    with pytest.raises(ValidationError):
        exports.export_charts(project, str(tmp_path / "absent"), "png")


def test_export_rpc_methods(project, tmp_path):
    e = Engine()
    e.project = project
    res = e.methods["export.tables"]({"path": str(tmp_path / "t.xlsx")})
    assert res["export"]["sheets"] == 3
    res = e.methods["export.charts"]({"directory": str(tmp_path), "format": "svg"})
    assert res["export"]["count"] > 0
    res = e.methods["export.chart"]({"path": str(tmp_path / "c.png"), "source": "analysis",
                                     "id": project.ids["desc"], "index": 0})
    assert res["export"]["file_name"] == "c.png"
    assert any(j["action"] == "export" for j in project.describe()["journal"])
