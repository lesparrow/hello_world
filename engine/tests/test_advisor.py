"""Assistant méthodologique : règles, informations manquantes, enregistrement du choix."""

from __future__ import annotations

import json
import sqlite3
import zipfile

import numpy as np
import pandas as pd
import pytest

from data_helpers import write_csv
from statpfe.core.project import Project
from statpfe.data.types import Category, Variable
from statpfe.errors import ValidationError
from statpfe.stats.advisor import PRINCIPLE, RULES_VERSION, advise
from statpfe.stats.catalog import METHODS


def data(**cols):
    df = pd.DataFrame(cols)
    variables = []
    for k, s in df.items():
        if pd.api.types.is_numeric_dtype(s):
            variables.append(Variable(k, k, "numerique", "continu"))
        else:
            df[k] = s.astype(object).where(s.notna(), None)
            variables.append(Variable(k, k, "texte", "nominal"))
    return df, variables


rng = np.random.default_rng(7)


def rec(advice):
    return advice["recommendation"]["method"] if advice["recommendation"] else None


def alt_methods(advice):
    return [a["method"] for a in advice["alternatives"]]


# ---------------------------------------------------------------------- comparer deux groupes
def test_two_large_groups_recommend_welch():
    df, v = data(y=rng.normal(10, 2, 60), g=["a"] * 30 + ["b"] * 30)
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"},
                       "independent": True, "purpose": "confirmatoire"})
    assert rec(a) == "welch"
    assert {"mann_whitney", "student"} <= set(alt_methods(a))
    assert a["recommendation"]["params"] == {"outcome": "y", "group": "g", "levels": ["a", "b"]}
    assert a["missing_information"] == []
    assert a["rules_version"] == RULES_VERSION and a["principle"] == PRINCIPLE


def test_small_skewed_groups_recommend_mann_whitney():
    y = np.concatenate([[1, 1.2, 1.1, 1.3, 1.0, 9.0], [2, 2.1, 2.3, 2.2, 2.4, 15.0]])
    df, v = data(y=y, g=["a"] * 6 + ["b"] * 6)
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}})
    assert rec(a) == "mann_whitney" and "welch" in alt_methods(a)
    assert any("indépendants" in m for m in a["missing_information"])
    assert any("confirmatoire" in m for m in a["missing_information"])


def test_small_but_regular_groups_still_welch():
    df, v = data(y=[10.0, 11, 12, 13, 14, 10.5, 11.5, 12.5, 13.5, 14.5], g=["a"] * 5 + ["b"] * 5)
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}, "independent": True})
    assert rec(a) == "welch"


def test_ordinal_outcome_recommends_mann_whitney():
    df, v = data(y=rng.integers(1, 6, 80).astype(float), g=["a", "b"] * 40)
    v[0].level = "ordinal"
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}, "independent": True})
    assert rec(a) == "mann_whitney"


def test_likert_declared_quantitative_is_questioned():
    df, v = data(y=rng.integers(1, 6, 80).astype(float), g=["a", "b"] * 40)
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}, "independent": True})
    assert any("ordinale" in m and "5 valeurs" in m for m in a["missing_information"])


def test_three_groups_are_honest_about_missing_anova():
    df, v = data(y=rng.normal(size=60), g=["a", "b", "c"] * 20)
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}, "independent": True})
    assert a["recommendation"] is None and "pas encore disponible" in a["blocking"]
    assert [x["available"] for x in a["alternatives"]] == [False, False]
    # En choisissant deux groupes, une recommandation redevient possible
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"},
                       "levels": ["a", "c"], "independent": True})
    assert rec(a) == "welch" and a["recommendation"]["params"]["levels"] == ["a", "c"]
    assert any("autre(s) groupe(s)" in m for m in a["missing_information"])


def test_qualitative_outcome_between_groups_is_an_association():
    df, v = data(y=["oui", "non"] * 50, g=["a"] * 50 + ["b"] * 50)
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}, "independent": True})
    assert rec(a) == "chi2" and "fisher" in alt_methods(a)


def test_single_group_is_blocking():
    df, v = data(y=[1.0, 2.0, 3.0], g=["a", "a", "a"])
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}})
    assert a["recommendation"] is None and "un seul groupe" in a["blocking"]


# ---------------------------------------------------------------------- appariées
def test_paired_large_recommends_paired_t():
    x = rng.normal(50, 5, 30)
    df, v = data(avant=x, apres=x + rng.normal(2, 1, 30))
    a = advise(df, v, {"objective": "compare_paired", "variables": {"first": "apres", "second": "avant"}})
    assert rec(a) == "paired_t" and "wilcoxon" in alt_methods(a)


def test_paired_small_irregular_recommends_wilcoxon():
    df, v = data(a=[1.0, 2, 3, 4, 5, 6, 7, 8], b=[1.5, 2.2, 3.1, 4.4, 5.2, 6.1, 7.3, 30.0])
    a = advise(df, v, {"objective": "compare_paired", "variables": {"first": "a", "second": "b"}})
    assert rec(a) == "wilcoxon"


def test_paired_text_measures_are_blocking():
    df, v = data(a=["x", "y"], b=["y", "x"])
    a = advise(df, v, {"objective": "compare_paired", "variables": {"first": "a", "second": "b"}})
    assert a["recommendation"] is None and "McNemar" in a["blocking"]


def test_paired_units_differ():
    x = rng.normal(50, 5, 30)
    df, v = data(a=x, b=x + 1)
    v[0].unit, v[1].unit = "kg", "g"
    a = advise(df, v, {"objective": "compare_paired", "variables": {"first": "a", "second": "b"}})
    assert any("même unité" in m for m in a["missing_information"])


# ---------------------------------------------------------------------- liens
def test_relate_quantitative_regular_is_pearson():
    # Données régulières déterministes : ni asymétrie marquée ni valeur extrême.
    x = np.linspace(-2, 2, 50)
    df, v = data(x=x, y=x + 0.5 * np.sin(7 * x))
    a = advise(df, v, {"objective": "relate", "variables": {"x": "x", "y": "y"}})
    assert rec(a) == "pearson" and "spearman" in alt_methods(a)


def test_relate_with_outliers_is_spearman():
    x = np.append(rng.normal(size=40), 12.0)
    df, v = data(x=x, y=np.append(rng.normal(size=40), 0.0))
    a = advise(df, v, {"objective": "relate", "variables": {"x": "x", "y": "y"}})
    assert rec(a) == "spearman" and "pearson" in alt_methods(a)


def test_relate_ordinal_is_spearman():
    df, v = data(x=rng.integers(1, 6, 40).astype(float), y=rng.normal(size=40))
    v[0].level = "ordinal"
    assert rec(advise(df, v, {"objective": "relate", "variables": {"x": "x", "y": "y"}})) == "spearman"


def test_relate_two_qualitative_small_counts_is_fisher():
    df, v = data(a=["x"] * 6 + ["y"] * 6, b=["u"] * 5 + ["v"] * 4 + ["u"] * 3)
    a = advise(df, v, {"objective": "relate", "variables": {"x": "a", "y": "b"}})
    assert rec(a) == "fisher" and "chi2" in alt_methods(a)


def test_relate_quantitative_and_qualitative_becomes_group_comparison():
    df, v = data(y=rng.normal(size=60), g=["a", "b"] * 30)
    a = advise(df, v, {"objective": "relate", "variables": {"x": "g", "y": "y"}})
    assert a["objective"] == "compare_groups" and rec(a) == "welch"


# ---------------------------------------------------------------------- décrire
def test_describe_rules():
    df, v = data(y=rng.normal(size=20), z=rng.normal(size=20), g=["a", "b"] * 10, h=["u"] * 10 + ["v"] * 10)
    assert rec(advise(df, v, {"objective": "describe", "variables": {"variables": ["y", "z"]}})) == "descriptives"
    a = advise(df, v, {"objective": "describe", "variables": {"variables": ["y", "g"]}})
    assert rec(a) == "descriptives" and a["recommendation"]["params"]["group"] == "g"
    assert rec(advise(df, v, {"objective": "describe", "variables": {"variables": ["g"]}})) == "frequencies"
    assert rec(advise(df, v, {"objective": "describe", "variables": {"variables": ["g", "h"]}})) == "crosstab"


# ---------------------------------------------------------------------- invariants
def test_recommendations_are_always_available_methods_and_never_cite_normality_tests():
    scenarios = [
        ("compare_groups", {"outcome": "y", "group": "g"}), ("relate", {"x": "y", "y": "z"}),
        ("compare_paired", {"first": "y", "second": "z"}), ("relate", {"x": "g", "y": "h"}),
        ("describe", {"variables": ["y", "g"]}),
    ]
    for seed in range(15):
        r = np.random.default_rng(seed)
        n = int(r.integers(6, 80))
        df, v = data(y=r.lognormal(size=n), z=r.normal(size=n), g=r.choice(["a", "b"], n), h=r.choice(["u", "v", "w"], n))
        for objective, variables in scenarios:
            a = advise(df, v, {"objective": objective, "variables": variables})
            json.dumps(a, allow_nan=False)
            if a["recommendation"]:
                assert a["recommendation"]["method"] in METHODS
                text = " ".join(a["recommendation"]["reasons"]).lower()
                assert "shapiro" not in text and "test de normalité" not in text
            for alt in a["alternatives"]:
                assert alt["method"] is None or alt["method"] in METHODS


def test_identifiers_and_bad_requests_are_refused():
    df, v = data(y=[1.0, 2.0], nom=["A", "B"])
    v[1].role = "identifiant"
    with pytest.raises(ValidationError):
        advise(df, v, {"objective": "describe", "variables": {"variables": ["nom"]}})
    with pytest.raises(ValidationError):
        advise(df, v, {"objective": "guess"})
    with pytest.raises(ValidationError):
        advise(df, v, {"objective": "relate", "variables": {"x": "y"}})
    with pytest.raises(ValidationError):
        advise(df, v, "relate")
    with pytest.raises(ValidationError):
        advise(df, v, {"objective": "describe", "variables": {"variables": ["y"]}, "purpose": "autre"})


def test_category_labels_appear_in_observations():
    df, v = data(y=rng.normal(size=40), g=["1", "2"] * 20)
    v[1].categories = [Category("1", "Témoin"), Category("2", "Traité")]
    a = advise(df, v, {"objective": "compare_groups", "variables": {"outcome": "y", "group": "g"}, "independent": True})
    assert any("Témoin" in o for o in a["observations"])


# ---------------------------------------------------------------------- enregistrement du choix
@pytest.fixture
def project(tmp_path, study):
    p = Project.create(str(tmp_path / "a.statpfe"), study)
    ds = p.data.import_file(str(write_csv(tmp_path)), None, "Enquête")
    yield p, ds, tmp_path
    if not p._closed:
        p.close(discard_changes=True)


REQUEST = {"objective": "compare_groups", "variables": {"outcome": "Note", "group": "Tutorat"}, "independent": True}


def test_following_the_recommendation(project):
    p, ds, _ = project
    advice = p.analyses.advise(ds, None, REQUEST)
    rec_ = advice["recommendation"]
    aid = p.analyses.run(ds, None, rec_["method"], rec_["params"], None,
                         {"mode": "assistant", "request": REQUEST, "purpose": "confirmatoire", "hypothesis": 0})
    choice = p.analyses.get(aid)["choice"]
    assert choice["followed"] and choice["recommended"] == rec_["method"] and choice["rules_version"] == RULES_VERSION
    assert choice["hypothesis_text"].startswith("H1") and choice["purpose"] == "confirmatoire"


def test_deviating_requires_a_reason(project):
    p, ds, _ = project
    rec_ = p.analyses.advise(ds, None, REQUEST)["recommendation"]
    other = "student" if rec_["method"] != "student" else "welch"
    with pytest.raises(ValidationError, match="raison"):
        p.analyses.run(ds, None, other, rec_["params"], None, {"mode": "assistant", "request": REQUEST})
    aid = p.analyses.run(ds, None, other, rec_["params"], None,
                         {"mode": "assistant", "request": REQUEST, "reason": "Protocole imposé par le directeur."})
    choice = p.analyses.get(aid)["choice"]
    assert not choice["followed"] and choice["reason"] == "Protocole imposé par le directeur."
    assert any(j.action == "choix_methode" for j in p.journal())


def test_direct_choice_and_invalid_choices(project):
    p, ds, _ = project
    aid = p.analyses.run(ds, None, "frequencies", {"variable": "Sexe"})
    assert p.analyses.get(aid)["choice"]["mode"] == "direct"
    for bad in ({"mode": "x"}, {"mode": "direct", "hypothesis": 5}, {"mode": "assistant"},
                {"mode": "direct", "reason": "x" * 3000}, "assistant"):
        with pytest.raises(ValidationError):
            p.analyses.run(ds, None, "frequencies", {"variable": "Sexe"}, None, bad)


def test_v3_project_is_migrated(tmp_path, study):
    path = tmp_path / "v3.statpfe"
    p = Project.create(str(path), study)
    ds = p.data.import_file(str(write_csv(tmp_path)), None, None)
    p.analyses.run(ds, None, "frequencies", {"variable": "Sexe"})
    p.save()
    p.close()
    with zipfile.ZipFile(path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        members = {n: zf.read(n) for n in zf.namelist()}
    db = tmp_path / "project.sqlite"
    db.write_bytes(members["project.sqlite"])
    conn = sqlite3.connect(db)
    conn.executescript("ALTER TABLE analyses DROP COLUMN choice; UPDATE meta SET value = '3' WHERE key = 'format_version';")
    conn.commit()
    conn.close()
    manifest["format_version"] = 3
    members["manifest.json"] = json.dumps(manifest).encode()
    members["project.sqlite"] = db.read_bytes()
    with zipfile.ZipFile(path, "w") as zf:
        for n, b in members.items():
            zf.writestr(n, b)
    q = Project.open(str(path))
    try:
        assert q.dirty and q.describe()["format_version"] == 5
        old = q.analyses.list()[0]["id"]
        assert q.analyses.get(old)["choice"] == {}
        aid = q.analyses.run(ds, None, "frequencies", {"variable": "Sexe"})
        assert q.analyses.get(aid)["choice"]["mode"] == "direct"
    finally:
        q.close(discard_changes=True)
