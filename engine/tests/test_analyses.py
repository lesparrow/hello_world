"""Analyses : cas limites, diagnostics, enregistrement, reproduction et traçabilité."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from data_helpers import write_csv
from statpfe.core.project import Project
from statpfe.data.types import Category, Variable
from statpfe.errors import ValidationError
from statpfe.rpc.server import Engine
from statpfe.stats.catalog import METHODS, catalog, run
from statpfe.stats.common import AnalysisError, fr, fr_p
from statpfe.stats.distributions import psignrank, pwilcox
from statpfe.stats.tests import fisher_exact_rxc, hedges_correction


# ---------------------------------------------------------------------- outils
def frame(**cols):
    df = pd.DataFrame(cols)
    variables = []
    for k, s in df.items():
        if pd.api.types.is_numeric_dtype(s):
            variables.append(Variable(k, k, "numerique", "continu"))
        else:
            df[k] = s.astype(object).where(s.notna(), None)
            variables.append(Variable(k, k, "texte", "nominal"))
    return df, variables


def levels(result, level):
    return [d for d in result["diagnostics"] if d["level"] == level]


# ---------------------------------------------------------------------- catalogue
def test_catalog_describes_every_method():
    cat = catalog()
    assert {m["key"] for m in cat["methods"]} == set(METHODS)
    for m in cat["methods"]:
        for field in ("objective", "variables", "conditions", "results", "r_equivalent"):
            assert m[field], (m["key"], field)
        assert m["family"] in cat["families"]
    json.dumps(cat)


def test_unknown_method_and_bad_params():
    df, v = frame(y=[1.0, 2.0, 3.0], z=[2.0, 1.0, 3.0])
    with pytest.raises(ValidationError):
        run("anova", df, v, {})
    with pytest.raises(ValidationError):
        run("descriptives", df, v, "y")
    with pytest.raises(ValidationError, match="Choisissez"):
        run("descriptives", df, v, {"variables": []})
    with pytest.raises(ValidationError, match="confiance"):
        run("descriptives", df, v, {"variables": ["y"], "conf_level": 0.5})
    with pytest.raises(ValidationError, match="alternative"):
        run("pearson", df, v, {"x": "y", "y": "z", "alternative": "both"})


# ---------------------------------------------------------------------- variables refusées
def test_identifier_and_excluded_variables_are_refused():
    df, v = frame(y=[1.0, 2.0, 3.0, 4.0], g=["a", "b", "a", "b"], nom=["A", "B", "C", "D"])
    v[2].role = "identifiant"
    with pytest.raises(AnalysisError, match="identifiant"):
        run("frequencies", df, v, {"variable": "nom"})
    v[2].role = "non_defini"
    v[2].potential_identifier = True
    with pytest.raises(AnalysisError, match="identifiant potentiel"):
        run("frequencies", df, v, {"variable": "nom"})
    v[0].role = "exclue"
    with pytest.raises(AnalysisError, match="exclue"):
        run("welch", df, v, {"outcome": "y", "group": "g"})


def test_type_checks():
    df, v = frame(y=[1.0, 2.0, 3.0, 4.0], g=["a", "b", "a", "b"])
    with pytest.raises(AnalysisError, match="numérique"):
        run("welch", df, v, {"outcome": "g", "group": "y"})
    with pytest.raises(AnalysisError, match="différentes"):
        run("pearson", df, v, {"x": "y", "y": "y"})
    with pytest.raises(AnalysisError, match="différentes"):
        run("welch", df, v, {"outcome": "y", "group": "y"})


# ---------------------------------------------------------------------- deux groupes
def test_three_groups_require_a_choice():
    df, v = frame(y=[1.0, 2, 3, 4, 5, 6], g=["a", "b", "c", "a", "b", "c"])
    with pytest.raises(AnalysisError, match="Choisissez les deux groupes"):
        run("welch", df, v, {"outcome": "y", "group": "g"})
    r = run("welch", df, v, {"outcome": "y", "group": "g", "levels": ["a", "c"]})
    assert r["values"]["n1"] == 2 and r["values"]["n2"] == 2
    assert any("autres modalités" in d["title"] for d in r["diagnostics"])
    with pytest.raises(AnalysisError):
        run("welch", df, v, {"outcome": "y", "group": "g", "levels": ["a", "z"]})


def test_group_too_small_and_constant():
    df, v = frame(y=[1.0, 2.0, 3.0], g=["a", "b", "b"])
    with pytest.raises(AnalysisError, match="moins de deux valeurs"):
        run("student", df, v, {"outcome": "y", "group": "g"})
    df, v = frame(y=[2.0, 2.0, 5.0, 5.0], g=["a", "a", "b", "b"])
    with pytest.raises(AnalysisError, match="constants"):
        run("welch", df, v, {"outcome": "y", "group": "g"})


def test_small_groups_and_outliers_are_flagged():
    df, v = frame(y=[1.0, 2.0, 3.0, 2.5, 2.2, 2.4, 2.6, 2.3, 2.5, 40.0], g=["a"] * 3 + ["b"] * 7)
    r = run("welch", df, v, {"outcome": "y", "group": "g"})
    assert any("ne compte que 3" in d["title"] for d in levels(r, "important"))
    assert any("extrême" in d["title"] for d in levels(r, "methodologique"))
    assert any("Shapiro" in d["title"] for d in levels(r, "information"))
    assert "levene_p" in r["values"]


def test_ordinal_outcome_warns_for_t_test():
    df, v = frame(y=[1.0, 2, 3, 4, 5, 2, 3, 4], g=["a"] * 4 + ["b"] * 4)
    v[0].level = "ordinal"
    r = run("welch", df, v, {"outcome": "y", "group": "g"})
    assert any("ordinale" in d["title"] for d in levels(r, "methodologique"))


def test_missing_values_are_reported():
    df, v = frame(y=[1.0, None, 3.0, 4.0, 5.0, 6.0, None], g=["a", "a", "a", "b", "b", None, "b"])
    r = run("welch", df, v, {"outcome": "y", "group": "g"})
    assert r["n_used"] == 4
    assert r["missing"]["excluded"] == 3 and "exclue" in r["missing"]["text"]


def test_group_order_and_labels_follow_dictionary():
    df, v = frame(y=[5.0, 6.0, 7.0, 1.0, 2.0, 3.0], g=["1", "1", "1", "2", "2", "2"])
    v[1].categories = [Category("2", "Témoin"), Category("1", "Traité")]
    r = run("student", df, v, {"outcome": "y", "group": "g"})
    assert r["values"]["mean1"] == 2.0  # « Témoin » vient en premier : différence Témoin − Traité
    assert "Témoin" in r["interpretation"][0]


def test_mann_whitney_exact_vs_normal():
    df, v = frame(y=[1.0, 2, 3, 4, 5, 6, 7, 8], g=["a"] * 4 + ["b"] * 4)
    r = run("mann_whitney", df, v, {"outcome": "y", "group": "g"})
    assert r["values"]["exact"] and r["values"]["w"] == 0 and r["values"]["rank_biserial"] == -1
    assert r["values"]["p"] == pytest.approx(2 / 70)
    df, v = frame(y=[1.0, 1, 2, 2, 3, 3, 4, 4], g=["a", "b"] * 4)
    r = run("mann_whitney", df, v, {"outcome": "y", "group": "g"})
    assert not r["values"]["exact"]


def test_mann_whitney_all_equal():
    df, v = frame(y=[3.0] * 6, g=["a"] * 3 + ["b"] * 3)
    with pytest.raises(AnalysisError, match="identiques"):
        run("mann_whitney", df, v, {"outcome": "y", "group": "g"})


# ---------------------------------------------------------------------- apparié
def test_paired_edge_cases():
    df, v = frame(a=[1.0, 2.0, 3.0], b=[2.0, 3.0, 4.0])
    with pytest.raises(AnalysisError, match="identiques"):
        run("paired_t", df, v, {"first": "a", "second": "b"})
    df, v = frame(a=[1.0, 2.0, 3.0], b=[1.0, 2.0, 3.0])
    with pytest.raises(AnalysisError, match="nulles"):
        run("wilcoxon", df, v, {"first": "a", "second": "b"})
    df, v = frame(a=[1.0, None], b=[1.0, 2.0])
    with pytest.raises(AnalysisError, match="deux paires"):
        run("paired_t", df, v, {"first": "a", "second": "b"})


def test_wilcoxon_zeros_are_dropped_and_reported():
    df, v = frame(a=[5.0, 6, 7, 8, 9, 10], b=[5.0, 4, 6, 5, 8, 7])
    r = run("wilcoxon", df, v, {"first": "a", "second": "b"})
    assert r["values"]["zeros"] == 1 and r["values"]["n_nonzero"] == 5
    assert any("sans différence" in d["title"] for d in r["diagnostics"])


# ---------------------------------------------------------------------- corrélations
def test_correlation_edge_cases():
    df, v = frame(x=[1.0, 2.0], y=[2.0, 1.0])
    with pytest.raises(AnalysisError, match="trois"):
        run("pearson", df, v, {"x": "x", "y": "y"})
    df, v = frame(x=[1.0, 1.0, 1.0, 1.0], y=[2.0, 1.0, 3.0, 4.0])
    with pytest.raises(AnalysisError, match="constante"):
        run("spearman", df, v, {"x": "x", "y": "y"})


def test_perfect_correlation_is_serializable():
    df, v = frame(x=[1.0, 2, 3, 4, 5], y=[2.0, 4, 6, 8, 10])
    r = run("pearson", df, v, {"x": "x", "y": "y"})
    assert r["values"]["r"] == pytest.approx(1) and r["values"]["p"] < 1e-6
    json.dumps(r, allow_nan=False)
    r = run("spearman", df, v, {"x": "x", "y": "y"})
    assert r["values"]["rho"] == pytest.approx(1)
    json.dumps(r, allow_nan=False)


def test_scatter_points_are_capped():
    rng = np.random.default_rng(0)
    df, v = frame(x=rng.normal(size=6000), y=rng.normal(size=6000))
    r = run("pearson", df, v, {"x": "x", "y": "y"})
    scatter = r["charts"][0]["data"]
    assert len(scatter["points"]) == 5000 and scatter["truncated"] and scatter["n"] == 6000


# ---------------------------------------------------------------------- qualitatives
def test_chi2_low_expected_counts_recommend_fisher():
    df, v = frame(a=["x", "x", "x", "y", "y", "x"], b=["u", "v", "u", "v", "v", "u"])
    r = run("chi2", df, v, {"row": "a", "col": "b"})
    assert any("Fisher" in d["detail"] for d in levels(r, "important"))


def test_contingency_needs_two_levels():
    df, v = frame(a=["x", "x", "x"], b=["u", "v", "u"])
    with pytest.raises(AnalysisError, match="une seule modalité"):
        run("chi2", df, v, {"row": "a", "col": "b"})


def test_fisher_rxc_rules():
    df, v = frame(a=list("xxyyzz"), b=list("uvuvuv"))
    with pytest.raises(AnalysisError, match="unilatérale"):
        run("fisher", df, v, {"row": "a", "col": "b", "alternative": "less"})
    big = pd.DataFrame({"a": ["x", "y"] * 200, "b": ["u", "v", "w", "t"] * 100})
    big_vars = [Variable("a", "a", "texte", "nominal"), Variable("b", "b", "texte", "nominal")]
    with pytest.raises(AnalysisError, match="trop grand"):
        run("fisher", big, big_vars, {"row": "a", "col": "b"})


def test_fisher_rxc_on_known_table():
    # Valeur de R : fisher.test(matrix(c(3,1,1,3,2,2), 2))$p.value
    assert fisher_exact_rxc(np.array([[3, 1, 2], [1, 3, 2]])) == pytest.approx(0.7662337662337656, rel=1e-12)


def test_frequencies():
    df, v = frame(s=["b", "a", "b", None, "c", "b"])
    v[0].categories = [Category("c", "Cadre"), Category("b"), Category("a")]
    v[0].level = "ordinal"
    r = run("frequencies", df, v, {"variable": "s"})
    rows = r["tables"][0]["rows"]
    assert [row[0] for row in rows] == ["c", "b", "a", "Manquant", "Total"]
    assert rows[0][1] == "Cadre" and rows[1][2] == 3 and rows[1][4] == pytest.approx(0.6)
    assert rows[2][5] == pytest.approx(1.0)
    assert r["n_used"] == 5 and r["missing"]["excluded"] == 1
    df, v = frame(s=[str(i) for i in range(60)])
    with pytest.raises(AnalysisError, match="50"):
        run("frequencies", df, v, {"variable": "s"})


def test_crosstab_percentages():
    df, v = frame(a=["x", "x", "y", "y", "y"], b=["u", "v", "u", "u", None])
    r = run("crosstab", df, v, {"row": "a", "col": "b", "percentages": "all"})
    assert r["values"]["counts"] == [[1, 1], [2, 0]]
    assert [t["title"] for t in r["tables"]][1:] == ["Pourcentages en ligne", "Pourcentages en colonne"]
    assert r["missing"]["excluded"] == 1


# ---------------------------------------------------------------------- descriptives
def test_descriptives_with_group_and_missing():
    df, v = frame(y=[1.0, 2.0, None, 4.0, 10.0, 12.0], g=["a", "a", "a", "b", "b", None])
    r = run("descriptives", df, v, {"variables": ["y"], "group": "g"})
    assert r["values"]["y|a"]["n"] == 2 and r["values"]["y|b"]["n"] == 2
    assert any("sans valeur pour" in d["title"] for d in r["diagnostics"])
    assert r["charts"][0]["type"] == "boxplot" and len(r["charts"][0]["data"]["series"]) == 2
    r = run("descriptives", df, v, {"variables": ["y"]})
    assert isinstance(r["values"]["y|"]["n"], int) and "(n = 5)" in r["interpretation"][0]


def test_descriptives_degenerate_cases_are_serializable():
    df, v = frame(c=[3.0, 3.0, 3.0], one=[1.0, None, None], none=[None, None, None])
    v[2] = Variable("none", "none", "numerique", "continu")
    df["none"] = pd.Series([np.nan] * 3, dtype="float64")
    r = run("descriptives", df, v, {"variables": ["c", "one", "none"]})
    json.dumps(r, allow_nan=False)
    titles = " ".join(d["title"] for d in r["diagnostics"])
    assert "constante" in titles and "une seule valeur" in titles and "aucune valeur" in titles


def test_histogram_and_box():
    from statpfe.stats.descriptive import box_stats, histogram

    x = np.array([1.0, 2, 2, 3, 3, 3, 4, 4, 5, 30])
    h = histogram(x)
    assert sum(h["counts"]) == 10 and len(h["edges"]) == len(h["counts"]) + 1
    b = box_stats(x)
    assert b["outliers"] == [30.0] and b["whisker_high"] == 5.0


# ---------------------------------------------------------------------- lois et formules
def test_exact_distributions_sum_to_one():
    assert pwilcox(12, 4, 3) == pytest.approx(1.0)
    assert psignrank(55, 10) == pytest.approx(1.0)
    assert pwilcox(-1, 4, 3) == 0 and psignrank(-1, 10) == 0


def test_hedges_correction_matches_approximation():
    for df in (10, 30, 100):
        assert hedges_correction(df) == pytest.approx(1 - 3 / (4 * df - 1), rel=1e-3)


def test_french_formatting():
    assert fr(1234.567) == "1 234,57" and fr(-0.5) == "−0,50" and fr(None) == "non calculable"
    assert fr_p(0.0004) == "p < 0,001" and fr_p(0.0312) == "p = 0,031"


# ---------------------------------------------------------------------- projet : enregistrement et reproduction
@pytest.fixture
def project(tmp_path, study):
    p = Project.create(str(tmp_path / "a.statpfe"), study)
    ds = p.data.import_file(str(write_csv(tmp_path)), None, "Enquête")
    yield p, ds, tmp_path
    if not p._closed:
        p.close(discard_changes=True)


def test_run_store_and_reproduce(project):
    p, ds, tmp_path = project
    aid = p.analyses.run(ds, None, "welch", {"outcome": "Note", "group": "Sexe"})
    a = p.analyses.get(aid)
    assert a["status"] == "a_jour" and a["version_name"] == "Données d'origine"
    assert a["environment"]["scipy"] and a["result"]["method_label"] == "Test t de Welch"
    assert len(a["data_fingerprint"]) == 64 and a["data_fingerprint"] == a["current_fingerprint"]
    rep = p.analyses.reproduce(aid)
    assert rep["identical_data"] and rep["identical_results"] and rep["same_environment"]
    assert any(j.action == "analyse" for j in p.journal())
    assert p.describe()["analyses_count"] == 1

    # Le dictionnaire change (un code manquant) : l'analyse est signalée et la reproduction montre l'écart
    p.data.update_variable(ds, "Note", {"missing_codes": ["8"]})
    assert p.analyses.get(aid)["status"] == "donnees_modifiees"
    rep = p.analyses.reproduce(aid)
    assert not rep["identical_data"] and not rep["identical_results"]
    assert any(d["path"] == "n2" for d in rep["differences"])


def test_analysis_on_version_and_deleted_version(project):
    p, ds, _ = project
    vid = p.data.create_version(ds, "Sans doublons", None)
    p.data.add_step(vid, {"op": "remove_duplicates"})
    aid = p.analyses.run(ds, vid, "frequencies", {"variable": "Sexe"})
    a = p.analyses.get(aid)
    assert a["version_name"] == "Sans doublons" and a["result"]["n_used"] == 10
    p.data.delete_version(vid)
    listed = p.analyses.list()
    assert listed[0]["status"] == "version_supprimee"
    rep = p.analyses.reproduce(aid)
    assert rep["status"] == "version_supprimee" and not rep["identical_results"]
    # Le résultat enregistré reste consultable
    assert p.analyses.get(aid)["result"]["n_used"] == 10


def test_levels_for_group_choice(project):
    p, ds, _ = project
    assert [(x["value"], x["count"]) for x in p.analyses.levels(ds, None, "Sexe")] == [("F", 6), ("M", 5)]
    assert [x["value"] for x in p.analyses.levels(ds, None, "Tutorat")] == ["non", "oui"]
    with pytest.raises(ValidationError):
        p.analyses.levels(ds, None, "Nom")
    with pytest.raises(ValidationError):
        p.analyses.levels(ds, None, "absente")
    # Les valeurs proposées sont acceptées telles quelles par les tests
    aid = p.analyses.run(ds, None, "welch", {"outcome": "Note", "group": "Tutorat", "levels": ["oui", "non"]})
    assert "oui" in p.analyses.get(aid)["result"]["interpretation"][0]


def test_identifier_columns_cannot_be_analysed(project):
    p, ds, _ = project
    with pytest.raises(AnalysisError):
        p.analyses.run(ds, None, "frequencies", {"variable": "Nom"})


def test_update_delete_and_persistence(project):
    p, ds, tmp_path = project
    aid = p.analyses.run(ds, None, "chi2", {"row": "Sexe", "col": "Tutorat"}, "Sexe et tutorat")
    p.analyses.update(aid, {"note": "Analyse prévue dans le protocole."})
    with pytest.raises(ValidationError):
        p.analyses.update(aid, {"result": {}})
    with pytest.raises(ValidationError):
        p.analyses.update(aid, {"title": "  "})
    second = p.analyses.run(ds, None, "descriptives", {"variables": ["Note", "Âge"]})
    p.analyses.delete(second)
    with pytest.raises(ValidationError):
        p.analyses.get(second)
    p.save()
    p.close()
    q = Project.open(str(tmp_path / "a.statpfe"))
    try:
        a = q.analyses.get(aid)
        assert a["title"] == "Sexe et tutorat" and a["note"] == "Analyse prévue dans le protocole."
        assert a["status"] == "a_jour" and q.analyses.reproduce(aid)["identical_results"]
        assert [x["id"] for x in q.analyses.list()] == [aid]
    finally:
        q.close(discard_changes=True)


def test_broken_version_is_refused(project):
    p, ds, _ = project
    vid = p.data.create_version(ds, "Filtre", None)
    p.data.add_step(vid, {"op": "filter_rows", "variable": "Note", "operator": "gt", "value": "10"})
    aid = p.analyses.run(ds, vid, "descriptives", {"variables": ["Note"]})
    p.data.update_variable(ds, "Note", {"type": "texte"})  # l'étape « Note > 10 » ne peut plus s'appliquer
    with pytest.raises(ValidationError, match="corrigée"):
        p.analyses.run(ds, vid, "descriptives", {"variables": ["Note"]})
    assert p.analyses.get(aid)["status"] == "version_a_corriger"


def test_analysis_over_rpc(tmp_path, study):
    e = Engine()

    def call(method, params=None):
        return e.handle(json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}))

    assert "methods" in call("analysis.catalog")["result"]
    assert call("analysis.list")["error"]["code"] == -32000  # aucun projet
    call("project.create", {"path": str(tmp_path / "r.statpfe"), "study": study})
    ds = call("data.import", {"path": str(write_csv(tmp_path)), "name": "E"})["result"]["dataset_id"]
    r = call("analysis.run", {"dataset_id": ds, "method": "pearson", "params": {"x": "Note", "y": "Satisfaction"}})
    a = r["result"]["analysis"]
    assert a["result"]["method"] == "pearson" and r["result"]["project"]["analyses_count"] == 1
    assert call("analysis.list")["result"][0]["status"] == "a_jour"
    rep = call("analysis.reproduce", {"analysis_id": a["id"]})["result"]["report"]
    assert rep["identical_results"]
    bad = call("analysis.run", {"dataset_id": ds, "method": "welch", "params": {"outcome": "Sexe", "group": "Note"}})
    assert bad["error"]["data"]["kind"] == "analyse_impossible"
    assert call("analysis.delete", {"analysis_id": a["id"]})["result"]["analyses_count"] == 0
    e.shutdown()


def test_every_method_runs_on_the_survey(project):
    p, ds, _ = project
    params = {
        "descriptives": {"variables": ["Note", "Âge"], "group": "Sexe"},
        "frequencies": {"variable": "Satisfaction"},
        "crosstab": {"row": "Sexe", "col": "Tutorat"},
        "welch": {"outcome": "Note", "group": "Tutorat"},
        "student": {"outcome": "Note", "group": "Sexe"},
        "mann_whitney": {"outcome": "Satisfaction", "group": "Sexe"},
        "paired_t": {"first": "Note", "second": "Satisfaction"},
        "wilcoxon": {"first": "Note", "second": "Satisfaction"},
        "pearson": {"x": "Note", "y": "Satisfaction"},
        "spearman": {"x": "Note", "y": "Satisfaction"},
        "chi2": {"row": "Sexe", "col": "Tutorat"},
        "fisher": {"row": "Sexe", "col": "Tutorat"},
    }
    assert set(params) == set(METHODS)
    for method, prm in params.items():
        aid = p.analyses.run(ds, None, method, prm)
        result = p.analyses.get(aid)["result"]
        assert result["interpretation"], method
        for s in result["summary"]:
            assert s["value"] is None or isinstance(s["value"], (int, float, str)), (method, s)
            if isinstance(s["value"], float):
                assert math.isfinite(s["value"])
