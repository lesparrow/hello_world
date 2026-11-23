"""Validation des méthodes statistiques contre R.

`tests/reference/r_results.csv` est produit par `tests/reference/r_reference.R`
(R de base, sans paquet) sur les jeux de `tests/reference/data/`. La CI régénère
ce fichier avec R puis relance ces tests (variable STATPFE_R_RESULTS).

Les données passent par la même chaîne que dans l'application : lecture du
CSV en textes bruts, détection des types, conversion par le dictionnaire.
"""

from __future__ import annotations

import csv
import math
import os
from pathlib import Path

import pytest

from statpfe.data import sources
from statpfe.data.sources import ReadOptions
from statpfe.data.types import build_typed_frame, detect_variable
from statpfe.stats.catalog import run

REF = Path(__file__).parent / "reference"
RESULTS = Path(os.environ.get("STATPFE_R_RESULTS", REF / "r_results.csv"))

# Tolérance relative par clé : les calculs directs doivent coïncider presque au bit près.
# Exceptions documentées :
# - Shapiro-Wilk : approximation de Royston (mêmes formules, implémentations différentes) ;
# - rapport de cotes conditionnel de Fisher et son IC : R les obtient par `uniroot` avec sa tolérance par
#   défaut (environ 1,2e-4 sur l'échelle de recherche) ; STATPFE résout la même équation plus précisément
#   (voir test_fisher_ci_is_exact : à la borne calculée, la probabilité de queue vaut exactement α/2).
TOLERANCE = {"shapiro_w": 1e-6, "shapiro_p": 1e-5, "odds_ratio": 2e-4}
FISHER_CI_TOL = 1e-3
DEFAULT_TOL = 1e-9


def load_reference() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    with RESULTS.open(newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["case"], {})[row["key"]] = float(row["value"])
    return out


REFERENCE = load_reference()


def dataset(name: str):
    table = sources.parse((REF / "data" / name).read_bytes(), "csv", ReadOptions())
    variables = [detect_variable(c, table.frame[c]) for c in table.frame.columns]
    df, _ = build_typed_frame(table.frame, variables)
    return df, variables


def A(alt):  # noqa: N802 - raccourci de lecture
    return {"two.sided": "two-sided"}.get(alt, alt)


CASES = {
    "desc_groups_y": ("descriptives", "groups.csv", {"variables": ["y"]}, "y|"),
    "desc_corr_x_99": ("descriptives", "corr.csv", {"variables": ["x"], "conf_level": 0.99}, "x|"),
    "desc_ties_score": ("descriptives", "groups_ties.csv", {"variables": ["score"]}, "score|"),
    "welch_groups": ("welch", "groups.csv", {"outcome": "y", "group": "g", "levels": ["A", "B"]}, None),
    "welch_groups_less_90": ("welch", "groups.csv", {"outcome": "y", "group": "g", "levels": ["A", "B"],
                                                     "alternative": "less", "conf_level": 0.90}, None),
    "student_groups": ("student", "groups.csv", {"outcome": "y", "group": "g", "levels": ["A", "B"]}, None),
    "student_groups_greater_99": ("student", "groups.csv", {"outcome": "y", "group": "g", "levels": ["A", "B"],
                                                            "alternative": "greater", "conf_level": 0.99}, None),
    "welch_small": ("welch", "small.csv", {"outcome": "y", "group": "g"}, None),
    "student_small_reversed": ("student", "small.csv", {"outcome": "y", "group": "g", "levels": ["T", "C"]}, None),
    "welch_ties": ("welch", "groups_ties.csv", {"outcome": "score", "group": "g"}, None),
    "mw_groups": ("mann_whitney", "groups.csv", {"outcome": "y", "group": "g"}, None),
    "mw_groups_greater": ("mann_whitney", "groups.csv", {"outcome": "y", "group": "g", "alternative": "greater"}, None),
    "mw_small": ("mann_whitney", "small.csv", {"outcome": "y", "group": "g"}, None),
    "mw_small_less": ("mann_whitney", "small.csv", {"outcome": "y", "group": "g", "alternative": "less"}, None),
    "mw_ties": ("mann_whitney", "groups_ties.csv", {"outcome": "score", "group": "g"}, None),
    "mw_ties_less": ("mann_whitney", "groups_ties.csv", {"outcome": "score", "group": "g", "alternative": "less"}, None),
    "paired_t": ("paired_t", "paired.csv", {"first": "apres", "second": "avant"}, None),
    "paired_t_less_99": ("paired_t", "paired.csv", {"first": "apres", "second": "avant", "alternative": "less",
                                                    "conf_level": 0.99}, None),
    "paired_t_ties": ("paired_t", "paired_ties.csv", {"first": "t2", "second": "t1"}, None),
    "wilcoxon": ("wilcoxon", "paired.csv", {"first": "apres", "second": "avant"}, None),
    "wilcoxon_greater": ("wilcoxon", "paired.csv", {"first": "apres", "second": "avant", "alternative": "greater"},
                         None),
    "wilcoxon_ties": ("wilcoxon", "paired_ties.csv", {"first": "t2", "second": "t1"}, None),
    "wilcoxon_ties_less": ("wilcoxon", "paired_ties.csv", {"first": "t2", "second": "t1", "alternative": "less"},
                           None),
    "pearson": ("pearson", "corr.csv", {"x": "x", "y": "y"}, None),
    "pearson_greater_90": ("pearson", "corr.csv", {"x": "x", "y": "y", "alternative": "greater",
                                                   "conf_level": 0.90}, None),
    "pearson_small": ("pearson", "corr_small.csv", {"x": "x", "y": "y"}, None),
    "pearson_ties": ("pearson", "corr_ties.csv", {"x": "x", "y": "y"}, None),
    "spearman": ("spearman", "corr.csv", {"x": "x", "y": "y"}, None),
    "spearman_less": ("spearman", "corr.csv", {"x": "x", "y": "y", "alternative": "less"}, None),
    "spearman_greater": ("spearman", "corr.csv", {"x": "x", "y": "y", "alternative": "greater"}, None),
    "spearman_small": ("spearman", "corr_small.csv", {"x": "x", "y": "y"}, None),
    "spearman_small_greater": ("spearman", "corr_small.csv", {"x": "x", "y": "y", "alternative": "greater"}, None),
    "spearman_ties": ("spearman", "corr_ties.csv", {"x": "x", "y": "y"}, None),
    "chi2_2x2_yates": ("chi2", "cat.csv", {"row": "sexe", "col": "fumeur"}, None),
    "chi2_2x2_plain": ("chi2", "cat.csv", {"row": "sexe", "col": "fumeur", "correction": False}, None),
    "chi2_2x3": ("chi2", "cat.csv", {"row": "sexe", "col": "satisfaction"}, None),
    "chi2_3x3_small": ("chi2", "cat_small_rxc.csv", {"row": "r", "col": "c"}, None),
    "fisher_2x2": ("fisher", "cat_small.csv", {"row": "traitement", "col": "guerison"}, None),
    "fisher_2x2_less": ("fisher", "cat_small.csv", {"row": "traitement", "col": "guerison", "alternative": "less"},
                        None),
    "fisher_2x2_greater_90": ("fisher", "cat_small.csv", {"row": "traitement", "col": "guerison",
                                                          "alternative": "greater", "conf_level": 0.90}, None),
    "fisher_2x2_sexe": ("fisher", "cat.csv", {"row": "sexe", "col": "fumeur"}, None),
    "fisher_rxc_small": ("fisher", "cat_small_rxc.csv", {"row": "r", "col": "c"}, None),
    "fisher_2x3": ("fisher", "cat.csv", {"row": "sexe", "col": "satisfaction"}, None),
    "fisher_3x3_medium": ("fisher", "cat_medium.csv", {"row": "r", "col": "c"}, None),
    "chi2_3x3_medium": ("chi2", "cat_medium.csv", {"row": "r", "col": "c"}, None),
}


def engine_values(case: str) -> dict:
    method, file, params, sub = CASES[case]
    df, variables = dataset(file)
    result = run(method, df, variables, params)
    values = dict(result["values"])
    if sub is not None:
        values = values[sub]
    for name in ("expected", "stdres"):
        if name in values:
            for i, row in enumerate(values.pop(name)):
                for j, v in enumerate(row):
                    values[f"{name}_{i}_{j}"] = v
    return values


def test_every_reference_case_is_checked():
    assert set(REFERENCE) == set(CASES)


@pytest.mark.parametrize("case", sorted(CASES))
def test_matches_r(case):
    expected = REFERENCE[case]
    got = engine_values(case)
    method = CASES[case][0]
    for key, ref in expected.items():
        assert key in got, f"{case} : clé « {key} » absente du résultat"
        value = got[key]
        if math.isinf(ref):
            assert value == ("+∞" if ref > 0 else "−∞"), f"{case}.{key} : {value!r} au lieu de {ref}"
            continue
        tol = FISHER_CI_TOL if method == "fisher" and key.startswith("ci_") else TOLERANCE.get(key, DEFAULT_TOL)
        assert value == pytest.approx(ref, rel=tol, abs=1e-12), f"{case}.{key} : {value!r} au lieu de {ref!r} (R)"


def test_fisher_ci_is_exact():
    """La borne inférieure de l'IC du rapport de cotes vérifie exactement P(X ≥ x | OR = borne) = α/2."""
    from scipy.stats import nchypergeom_fisher

    df, variables = dataset("cat_small.csv")
    values = run("fisher", df, variables, {"row": "traitement", "col": "guerison"})["values"]
    # Tableau [[2, 7], [6, 2]] : x = 2, marges 9 (ligne) et 8 (colonne), n = 17
    lower_tail = nchypergeom_fisher.sf(1, 17, 9, 8, values["ci_low"])
    upper_tail = nchypergeom_fisher.cdf(2, 17, 9, 8, values["ci_high"])
    assert lower_tail == pytest.approx(0.025, abs=1e-9)
    assert upper_tail == pytest.approx(0.025, abs=1e-9)
