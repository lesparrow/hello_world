"""Validation des calculs de puissance contre R (paquet pwr et power.t.test).

`tests/reference/r_power.csv` est produit par `tests/reference/r_power.R`. La CI
le régénère avec R et le paquet pwr puis relance ces tests (STATPFE_R_POWER).
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from statpfe.stats.power import compute

REF = Path(__file__).parent / "reference"
RESULTS = Path(os.environ.get("STATPFE_R_POWER", REF / "r_power.csv"))
POWER_TOL = 1e-9   # loi de Student non centrale : scipy (Boost) et R (AS 243) concordent à ~1e-12 près
EFFECT_TOL = 1e-8


def load() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    with RESULTS.open(newline="") as fh:
        for row in csv.DictReader(fh):
            out.setdefault(row["case"], {})[row["key"]] = float(row["value"])
    return out


REFERENCE = load()
TWO, ONE = "two-sided", "one-sided"


def ss(design, effect, alpha, power, sides=TWO, **kw):
    return {"design": design, "mode": "sample_size", "effects": [effect], "alpha": alpha, "power": power,
            "alternative": sides, **kw}


def pw(design, effect, alpha, sides=TWO, **kw):
    return {"design": design, "mode": "power", "effects": [effect], "alpha": alpha, "alternative": sides, **kw}


def eff(design, alpha, power, sides=TWO, **kw):
    return {"design": design, "mode": "effect", "alpha": alpha, "power": power, "alternative": sides, **kw}


CASES = {
    "t2_ss_d05": ss("t_two", {"d": 0.5}, 0.05, 0.80),
    "t2_ss_d02_one_90": ss("t_two", {"d": 0.2}, 0.05, 0.90, ONE),
    "t2_ss_d08_a01": ss("t_two", {"diff": 4.0, "sd": 5.0}, 0.01, 0.95),
    "t2_ss_ratio2": ss("t_two", {"d": 0.5}, 0.05, 0.80, ratio=2),
    "t2_ss_ratio05_one": ss("t_two", {"d": 0.4}, 0.05, 0.85, ONE, ratio=0.5),
    "t2_pw_unequal": pw("t_two", {"d": 0.6}, 0.05, n1=30, n2=45),
    "t2_pw_small_one": pw("t_two", {"d": 0.3}, 0.10, ONE, n1=12, n2=9),
    "t2_eff_40": eff("t_two", 0.05, 0.80, n1=40, n2=40),
    "t2_eff_25_60_one": eff("t_two", 0.05, 0.90, ONE, n1=25, n2=60),
    "paired_ss_d03": ss("t_paired", {"d": 0.3}, 0.05, 0.80),
    "paired_ss_d06_one": ss("t_paired", {"d": -0.6}, 0.05, 0.90, ONE),
    "paired_pw_n25": pw("t_paired", {"d": 0.5}, 0.05, n=25),
    "paired_eff_n18": eff("t_paired", 0.05, 0.80, n=18),
    "one_ss_d04_a01": ss("t_one", {"d": 0.4}, 0.01, 0.80),
    "one_pw_n10_one": pw("t_one", {"d": 0.7}, 0.05, ONE, n=10),
    "one_eff_n60": eff("t_one", 0.05, 0.95, n=60),
    "prop_ss_40_60": ss("prop_two", {"p1": 0.4, "p2": 0.6}, 0.05, 0.80),
    "prop_ss_10_20_one": ss("prop_two", {"p1": 0.10, "p2": 0.20}, 0.05, 0.90, ONE),
    "prop_ss_ratio3": ss("prop_two", {"p1": 0.30, "p2": 0.50}, 0.05, 0.80, ratio=3),
    "prop_pw_unequal": pw("prop_two", {"p1": 0.30, "p2": 0.50}, 0.05, n1=60, n2=80),
    "prop_eff_100": eff("prop_two", 0.05, 0.80, n1=50, n2=50),
    "chi2_ss_w03_df2": ss("chi2", {"w": 0.3}, 0.05, 0.80, rows=2, cols=3),
    "chi2_ss_w01_df1": ss("chi2", {"w": 0.1}, 0.05, 0.90, df=1),
    "chi2_pw_w02_df4": pw("chi2", {"w": 0.2}, 0.05, n=200, rows=3, cols=3),
    "chi2_eff_n150_df1": eff("chi2", 0.05, 0.80, n=150, df=1),
    "r_ss_03": ss("correlation", {"r": 0.3}, 0.05, 0.80),
    "r_ss_02_one": ss("correlation", {"r": 0.2}, 0.05, 0.90, ONE),
    "r_ss_05_a01": ss("correlation", {"r": -0.5}, 0.01, 0.80),
    "r_pw_n50": pw("correlation", {"r": 0.4}, 0.05, n=50),
    "r_pw_n30_one": pw("correlation", {"r": 0.25}, 0.05, ONE, n=30),
    "r_eff_n80": eff("correlation", 0.05, 0.80, n=80),
}


def test_every_reference_case_is_checked():
    assert set(REFERENCE) == set(CASES)


@pytest.mark.parametrize("case", sorted(CASES))
def test_matches_r(case):
    expected = REFERENCE[case]
    res = compute(CASES[case])
    row = res["rows"][0]
    for key, ref in expected.items():
        if key in ("n1", "n2"):
            assert row[key] == int(ref), f"{case}.{key} : {row[key]} au lieu de {int(ref)} (R)"
        elif key in ("power", "power_base"):
            assert row["power"] == pytest.approx(ref, rel=POWER_TOL), f"{case}.{key}"
        elif key == "h":
            assert row["effect"] == pytest.approx(ref, rel=1e-12)
        elif key == "effect":
            assert row["effect"] == pytest.approx(ref, rel=EFFECT_TOL), f"{case}.effect"
        else:
            raise AssertionError(f"clé inattendue {key}")
