"""Statistiques descriptives, fréquences et tableaux croisés.

Conventions (identiques à R par défaut) :
- écart-type et variance avec le dénominateur n − 1 ;
- quantiles de type 7 (`quantile()` de R, `numpy.quantile` par défaut) ;
- asymétrie et aplatissement « ajustés » (G1 et G2, ceux de SPSS et Excel) ;
- intervalle de confiance de la moyenne fondé sur la loi de Student.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from statpfe.data.types import Variable
from statpfe.stats.common import (
    MAX_GROUP_LEVELS, AnalysisError, Context, Result, as_labels, fr, level_label, missing_note, num,
    ordered_levels,
)

MAX_OUTLIERS_SHOWN = 200
SHAPIRO_MIN, SHAPIRO_MAX = 3, 5000


# ------------------------------------------------------------------ calculs élémentaires
def summarize(x: np.ndarray, conf_level: float = 0.95) -> dict[str, Any]:
    n = len(x)
    out: dict[str, Any] = {"n": n}
    if n == 0:
        return out
    mean = float(np.mean(x))
    sd = float(np.std(x, ddof=1)) if n > 1 else None
    q1, med, q3 = (float(v) for v in np.quantile(x, [0.25, 0.5, 0.75]))
    out.update(mean=mean, sd=sd, variance=sd ** 2 if sd is not None else None,
               se=sd / math.sqrt(n) if sd is not None else None, median=med, q1=q1, q3=q3, iqr=q3 - q1,
               min=float(np.min(x)), max=float(np.max(x)))
    out["range"] = out["max"] - out["min"]
    if sd is not None and sd > 0:
        tcrit = float(sps.t.ppf(1 - (1 - conf_level) / 2, n - 1))
        out["ci_low"], out["ci_high"] = mean - tcrit * out["se"], mean + tcrit * out["se"]
        out["cv"] = sd / abs(mean) if mean != 0 else None
    else:
        out["ci_low"] = out["ci_high"] = None
    out["skewness"] = skewness(x)
    out["kurtosis"] = kurtosis(x)
    return out


def skewness(x: np.ndarray) -> float | None:
    """Asymétrie ajustée G1 (n ≥ 3)."""
    n = len(x)
    if n < 3 or np.std(x) == 0:
        return None
    return float(sps.skew(x, bias=False))


def kurtosis(x: np.ndarray) -> float | None:
    """Aplatissement ajusté G2 (excès, 0 pour une loi normale ; n ≥ 4)."""
    n = len(x)
    if n < 4 or np.std(x) == 0:
        return None
    return float(sps.kurtosis(x, fisher=True, bias=False))


def shapiro(x: np.ndarray) -> tuple[float, float] | None:
    if not SHAPIRO_MIN <= len(x) <= SHAPIRO_MAX or np.ptp(x) == 0:
        return None
    res = sps.shapiro(x)
    return float(res.statistic), float(res.pvalue)


def box_stats(x: np.ndarray) -> dict[str, Any]:
    """Boîte à moustaches de Tukey : moustaches jusqu'à la dernière valeur à 1,5 × EIQ."""
    q1, med, q3 = (float(v) for v in np.quantile(x, [0.25, 0.5, 0.75]))
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = x[(x >= lo_fence) & (x <= hi_fence)]
    outliers = np.sort(x[(x < lo_fence) | (x > hi_fence)])
    return {
        "q1": q1, "median": med, "q3": q3, "mean": float(np.mean(x)),
        "whisker_low": float(inside.min()) if len(inside) else q1,
        "whisker_high": float(inside.max()) if len(inside) else q3,
        "outliers": [float(v) for v in outliers[:MAX_OUTLIERS_SHOWN]],
        "outlier_count": int(len(outliers)), "n": int(len(x)),
    }


def histogram(x: np.ndarray) -> dict[str, Any]:
    """Classes de Sturges (comme `hist()` de R, sans l'arrondi « pretty »)."""
    if np.ptp(x) == 0:
        edges = np.array([x[0] - 0.5, x[0] + 0.5])
    else:
        edges = np.histogram_bin_edges(x, bins="sturges")
    counts, edges = np.histogram(x, bins=edges)
    return {"edges": [float(e) for e in edges], "counts": [int(c) for c in counts], "n": int(len(x))}


def numeric_values(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype="float64")


# ------------------------------------------------------------------ analyses
STAT_COLUMNS = [
    ("n", "n"), ("mean", "Moyenne"), ("sd", "Écart-type"), ("se", "Erreur type"), ("ci_low", "IC bas"),
    ("ci_high", "IC haut"), ("median", "Médiane"), ("q1", "Q1"), ("q3", "Q3"), ("min", "Min"), ("max", "Max"),
    ("skewness", "Asymétrie"), ("kurtosis", "Aplatissement"),
]


def descriptives(ctx: Context) -> Result:
    variables = ctx.var_list("variables", label="variables quantitatives", types=("numerique",))
    group = ctx.optional_var("group", label="variable de regroupement")
    conf = ctx.conf_level()
    res = Result("descriptives", "Statistiques descriptives")
    res.variables = [v.name for v in variables] + ([group.name] if group else [])
    total = len(ctx.df)
    df = ctx.df
    groups: list[tuple[str, str, pd.DataFrame]] = [("", "Ensemble", df)]
    if group is not None:
        labels = as_labels(df[group.key])
        present = sorted(set(labels.dropna()))
        if len(present) > MAX_GROUP_LEVELS:
            raise AnalysisError(f"« {group.name} » a plus de {MAX_GROUP_LEVELS} modalités : choisissez une "
                                "variable qualitative pour regrouper.")
        levels = ordered_levels(group, present)
        n_missing_group = int(labels.isna().sum())
        if n_missing_group:
            res.diag("information", f"{n_missing_group} ligne(s) sans valeur pour « {group.name} » sont exclues "
                                    "des statistiques par groupe.")
        groups = [(lv, level_label(group, lv), df[labels == lv]) for lv in levels]

    rows, box_series = [], []
    ci_label = f"IC {fr(conf * 100, 0)} % de la moyenne"
    for var in variables:
        col_all = df[var.key]
        missing = int(col_all.isna().sum())
        for gkey, glabel, gdf in groups:
            x = numeric_values(gdf[var.key])
            s = summarize(x, conf)
            row = [var.name] + ([glabel] if group else []) + [s.get(k) for k, _ in STAT_COLUMNS]
            row.insert(2 if group else 1, int(gdf[var.key].isna().sum()))
            rows.append(row)
            name = f"{var.name} · {glabel}" if group else var.name
            values = {k: num(v) if isinstance(v, (int, float)) else v for k, v in s.items()}
            sw = shapiro(x)
            if sw:
                values["shapiro_w"], values["shapiro_p"] = sw
            res.values[f"{var.key}|{gkey}"] = values
            if len(x):
                box_series.append({"label": glabel if group else var.name, "variable": var.name, **box_stats(x)})
            _numeric_diagnostics(res, name, x)
        if group is None:
            x = numeric_values(col_all)
            if len(x):
                res.chart("histogram", f"Histogramme de « {var.name} »",
                          {"variable": var.name, "unit": var.unit, **histogram(x)})
        if missing and group is None:
            res.diag("information" if missing / max(total, 1) < 0.2 else "important",
                     f"« {var.name} » : {missing} valeur(s) manquante(s) sur {total}.",
                     "Chaque statistique est calculée sur les valeurs disponibles de la variable.")
    columns = ["Variable"] + (["Groupe"] if group else []) + ["Manquants"] + [label for _, label in STAT_COLUMNS]
    columns[columns.index("IC bas")] = f"{ci_label} (bas)"
    columns[columns.index("IC haut")] = f"{ci_label} (haut)"
    res.table("Statistiques descriptives", columns, rows,
              "Écart-type avec dénominateur n − 1 ; quartiles de type 7 ; asymétrie G1 et aplatissement G2 "
              "(excès, 0 pour une loi normale).",
              kinds=["text"] + (["text"] if group else []) + ["int", "int"] + ["num"] * (len(STAT_COLUMNS) - 1))
    if box_series:
        if group:
            for var in variables:
                series = [b for b in box_series if b["variable"] == var.name]
                res.chart("boxplot", f"« {var.name} » selon « {group.name} »", {"series": series, "unit": var.unit})
        else:
            for b in box_series:
                res.chart("boxplot", f"Boîte à moustaches de « {b['variable']} »", {"series": [b], "unit": ""})
    res.missing = {"strategy": "disponibles", "total": total, "used": None, "excluded": None,
                   "text": "Chaque variable est décrite à partir de ses valeurs disponibles (les valeurs manquantes "
                           "sont ignorées variable par variable)."}
    res.interpretation = _describe_text(variables, res, group)
    return res


def _numeric_diagnostics(res: Result, name: str, x: np.ndarray) -> None:
    n = len(x)
    if n == 0:
        res.diag("important", f"« {name} » : aucune valeur disponible.")
        return
    if n < 2:
        res.diag("important", f"« {name} » : une seule valeur, l'écart-type n'est pas calculable.")
        return
    if np.ptp(x) == 0:
        res.diag("important", f"« {name} » est constante (toutes les valeurs valent {fr(float(x[0]))}).",
                 "Une variable constante n'apporte aucune information pour les comparaisons ou corrélations.")
        return
    box = box_stats(x)
    if box["outlier_count"]:
        res.diag("methodologique",
                 f"« {name} » : {box['outlier_count']} valeur(s) au-delà de 1,5 fois l'écart interquartile.",
                 "Vérifiez qu'il ne s'agit pas d'erreurs de saisie. Une valeur extrême réelle ne doit pas être "
                 "supprimée sans justification.")
    g1 = skewness(x)
    if g1 is not None and abs(g1) >= 1:
        res.diag("information", f"« {name} » : distribution nettement asymétrique (G1 = {fr(g1)}).",
                 "La médiane et l'écart interquartile décrivent alors mieux la tendance centrale et la dispersion.")


def _describe_text(variables: list[Variable], res: Result, group: Variable | None) -> list[str]:
    lines = []
    for var in variables:
        s = res.values.get(f"{var.key}|")
        if group is None and s and s.get("n", 0) >= 2 and s.get("sd") is not None:
            unit = f" {var.unit}" if var.unit else ""
            lines.append(
                f"« {var.name} » (n = {s['n']}) : moyenne {fr(s['mean'])}{unit} (écart-type {fr(s['sd'])}), "
                f"médiane {fr(s['median'])}{unit} (Q1 = {fr(s['q1'])}, Q3 = {fr(s['q3'])}), "
                f"de {fr(s['min'])} à {fr(s['max'])}.")
    if group is not None:
        lines.append("Les statistiques par groupe décrivent l'échantillon ; elles ne permettent pas à elles seules "
                     "de conclure à une différence entre groupes (un test est nécessaire).")
    return lines


def frequencies(ctx: Context) -> Result:
    var = ctx.var("variable", label="variable")
    res = Result("frequencies", f"Fréquences de « {var.name} »")
    res.variables = [var.name]
    labels = as_labels(ctx.df[var.key])
    total = len(labels)
    valid = labels.dropna()
    present = sorted(set(valid))
    if len(present) > MAX_GROUP_LEVELS:
        raise AnalysisError(f"« {var.name} » a {len(present)} valeurs différentes : un tableau de fréquences "
                            f"n'est pas adapté au-delà de {MAX_GROUP_LEVELS}. Utilisez les statistiques "
                            "descriptives ou regroupez les valeurs (recodage).")
    levels = ordered_levels(var, present)
    counts = valid.value_counts()
    n_valid = len(valid)
    rows, cum = [], 0
    bars = []
    for lv in levels:
        c = int(counts.get(lv, 0))
        cum += c
        lab = level_label(var, lv)
        rows.append([lv, lab if lab != lv else "", c, c / total if total else None,
                     c / n_valid if n_valid else None, cum / n_valid if n_valid else None])
        bars.append({"label": lab, "count": c, "percent": c / n_valid if n_valid else 0})
        res.values[f"count|{lv}"] = c
    missing = total - n_valid
    if missing:
        rows.append(["Manquant", "", missing, missing / total, None, None])
    rows.append(["Total", "", total, 1.0 if total else None, 1.0 if n_valid else None, None])
    res.table(f"Distribution de « {var.name} »",
              ["Modalité", "Libellé", "Effectif", "% du total", "% valide", "% valide cumulé"], rows,
              "Le pourcentage valide est calculé sans les valeurs manquantes."
              + (" Le cumul n'a de sens que pour une variable ordinale." if var.level != "ordinal" else ""),
              kinds=["text", "text", "int", "pct", "pct", "pct"])
    res.chart("bar", f"Répartition de « {var.name} »", {"bars": bars, "n": n_valid})
    res.n_used = n_valid
    res.values.update(n_valid=n_valid, n_missing=missing)
    res.missing = missing_note(total, n_valid, [var.name])
    if var.level == "continu" and var.type == "numerique":
        res.diag("methodologique", f"« {var.name} » est déclarée quantitative.",
                 "Pour une variable quantitative, les statistiques descriptives et l'histogramme sont "
                 "généralement plus informatifs qu'un tableau de fréquences.")
    if len(levels) == 1:
        res.diag("important", f"« {var.name} » ne prend qu'une seule valeur dans les données analysées.")
    if n_valid and len(levels) > 1:
        top = max(bars, key=lambda b: b["count"])
        res.interpretation = [
            f"Sur {n_valid} réponse(s) valide(s), la modalité la plus fréquente est « {top['label']} » "
            f"({top['count']}, soit {fr(100 * top['percent'], 1)} %)."
            + (f" {missing} valeur(s) manquante(s) ne sont pas comptées dans les pourcentages valides." if missing
               else "")]
    return res


def crosstab_counts(ctx: Context, row: Variable, col: Variable) -> tuple[pd.DataFrame, list[str], list[str], int, int]:
    """Tableau de contingence (observations complètes sur les deux variables)."""
    r = as_labels(ctx.df[row.key])
    c = as_labels(ctx.df[col.key])
    total = len(r)
    mask = r.notna() & c.notna()
    r, c = r[mask], c[mask]
    rlev = ordered_levels(row, sorted(set(r)))
    clev = ordered_levels(col, sorted(set(c)))
    for v, lev in ((row, rlev), (col, clev)):
        if len(lev) > MAX_GROUP_LEVELS:
            raise AnalysisError(f"« {v.name} » a trop de modalités ({len(lev)}) pour un tableau croisé.")
    table = pd.crosstab(r, c).reindex(index=rlev, columns=clev, fill_value=0)
    return table, rlev, clev, total, int(mask.sum())


def add_crosstab_tables(res: Result, row: Variable, col: Variable, table: pd.DataFrame,
                        rlev: list[str], clev: list[str], percentages: str = "row") -> None:
    counts = table.to_numpy(dtype="int64")
    n = int(counts.sum())
    rlab = [level_label(row, v) for v in rlev]
    clab = [level_label(col, v) for v in clev]
    rows = [[rlab[i]] + [int(v) for v in counts[i]] + [int(counts[i].sum())] for i in range(len(rlev))]
    rows.append(["Total"] + [int(v) for v in counts.sum(axis=0)] + [n])
    res.table(f"Effectifs : « {row.name} » (lignes) × « {col.name} » (colonnes)",
              [row.name] + clab + ["Total"], rows, kinds=["text"] + ["int"] * (len(clev) + 1))
    if percentages in ("row", "all"):
        rs = counts.sum(axis=1, keepdims=True)
        pct = np.divide(counts, rs, out=np.zeros_like(counts, dtype=float), where=rs > 0)
        res.table("Pourcentages en ligne", [row.name] + clab + ["Total"],
                  [[rlab[i]] + list(pct[i]) + [1.0 if rs[i, 0] else None] for i in range(len(rlev))],
                  kinds=["text"] + ["pct"] * (len(clev) + 1))
    if percentages in ("col", "all"):
        cs = counts.sum(axis=0, keepdims=True)
        pct = np.divide(counts, cs, out=np.zeros_like(counts, dtype=float), where=cs > 0)
        res.table("Pourcentages en colonne", [row.name] + clab,
                  [[rlab[i]] + list(pct[i]) for i in range(len(rlev))], kinds=["text"] + ["pct"] * len(clev))
    rs = counts.sum(axis=1)
    res.chart("stacked", f"Répartition de « {col.name} » selon « {row.name} »", {
        "rows": rlab, "columns": clab,
        "percent": [[(counts[i, j] / rs[i]) if rs[i] else 0 for j in range(len(clev))] for i in range(len(rlev))],
        "counts": counts.tolist(),
    })


def crosstab(ctx: Context) -> Result:
    row = ctx.var("row", label="variable en ligne")
    col = ctx.var("col", label="variable en colonne")
    if row.key == col.key:
        raise AnalysisError("Choisissez deux variables différentes.")
    pct = ctx.params.get("percentages", "row")
    if pct not in ("row", "col", "all", "none"):
        raise AnalysisError("Option de pourcentages inconnue.")
    res = Result("crosstab", f"Tableau croisé « {row.name} » × « {col.name} »")
    res.variables = [row.name, col.name]
    table, rlev, clev, total, used = crosstab_counts(ctx, row, col)
    if used == 0:
        raise AnalysisError("Aucune ligne n'a de valeur pour les deux variables.")
    add_crosstab_tables(res, row, col, table, rlev, clev, pct)
    res.n_used = used
    res.missing = missing_note(total, used, [row.name, col.name])
    res.values["counts"] = table.to_numpy(dtype="int64").tolist()
    res.interpretation = ["Un tableau croisé décrit la répartition conjointe des deux variables. Pour tester "
                          "s'il existe une association, utilisez le test du khi-deux ou le test exact de Fisher."]
    return res
