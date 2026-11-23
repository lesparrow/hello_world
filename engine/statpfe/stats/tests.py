"""Tests statistiques fondamentaux.

Chaque fonction reproduit le comportement par défaut de la fonction R
correspondante (t.test, wilcox.test, cor.test, chisq.test, fisher.test) ;
les valeurs sont comparées à R par les tests de validation du moteur.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps
from scipy.special import gammaln
from scipy.stats.contingency import odds_ratio

from statpfe.data.types import Variable
from statpfe.stats.common import (
    ALTERNATIVES, AnalysisError, Context, Result, as_labels, fr, fr_p, level_label, missing_note, num,
    ordered_levels,
)
from statpfe.stats.descriptive import (
    add_crosstab_tables, box_stats, crosstab_counts, histogram, shapiro, skewness, summarize,
)
from statpfe.stats.distributions import psignrank, pspearman, pwilcox

SMALL_GROUP = 5
FISHER_MAX_N = 300
FISHER_MAX_CELLS = 20


# ======================================================================= utilitaires
def _p_two_sided_norm(z: float, alternative: str) -> float:
    if alternative == "less":
        return float(sps.norm.cdf(z))
    if alternative == "greater":
        return float(sps.norm.sf(z))
    return float(2 * min(sps.norm.cdf(z), sps.norm.sf(z)))


def _p_t(stat: float, df: float, alternative: str) -> float:
    if alternative == "less":
        return float(sps.t.cdf(stat, df))
    if alternative == "greater":
        return float(sps.t.sf(stat, df))
    return float(2 * min(sps.t.cdf(stat, df), sps.t.sf(stat, df)))


def _t_ci(estimate: float, se: float, df: float, conf: float, alternative: str) -> tuple[float, float]:
    if alternative == "less":
        return -math.inf, estimate + float(sps.t.ppf(conf, df)) * se
    if alternative == "greater":
        return estimate - float(sps.t.ppf(conf, df)) * se, math.inf
    q = float(sps.t.ppf(1 - (1 - conf) / 2, df))
    return estimate - q * se, estimate + q * se


def hedges_correction(df: float) -> float:
    """Facteur exact J(df) = Γ(df/2) / (√(df/2) Γ((df−1)/2))."""
    return float(math.exp(gammaln(df / 2) - math.log(math.sqrt(df / 2)) - gammaln((df - 1) / 2)))


def magnitude_d(d: float | None) -> str:
    if d is None:
        return "non calculable"
    a = abs(d)
    return "négligeable" if a < 0.2 else "petite" if a < 0.5 else "moyenne" if a < 0.8 else "grande"


def magnitude_r(r: float | None) -> str:
    if r is None:
        return "non calculable"
    a = abs(r)
    return "négligeable" if a < 0.1 else "faible" if a < 0.3 else "moyenne" if a < 0.5 else "forte"


def _ci_text(lo: float, hi: float, conf: float, digits: int = 2) -> str:
    lo_s = "−∞" if lo == -math.inf else fr(lo, digits)
    hi_s = "+∞" if hi == math.inf else fr(hi, digits)
    return f"IC {fr(conf * 100, 0)} % [{lo_s} ; {hi_s}]"


def _significance(p: float, alpha: float) -> bool:
    return p < alpha


CAUTION_GROUPS = ("Une différence statistiquement significative n'indique ni son importance pratique ni une "
                  "relation de cause à effet ; un résultat non significatif ne prouve pas l'absence de différence.")
CAUTION_ASSOC = ("Une association statistique n'implique pas de relation de cause à effet ; un résultat non "
                 "significatif ne prouve pas l'absence d'association.")
NORMALITY_NOTE = ("Ce test n'est donné qu'à titre indicatif : avec de grands échantillons il détecte des écarts "
                  "sans importance, avec de petits il manque de puissance. Examinez aussi l'histogramme et la "
                  "boîte à moustaches ; ne choisissez pas la méthode sur ce seul résultat.")


# ======================================================================= deux groupes indépendants
def _two_groups(ctx: Context) -> tuple[Variable, Variable, str, str, np.ndarray, np.ndarray, dict[str, Any]]:
    outcome = ctx.var("outcome", label="variable à comparer", types=("numerique",))
    group = ctx.var("group", label="variable de groupe")
    if outcome.key == group.key:
        raise AnalysisError("La variable à comparer et la variable de groupe doivent être différentes.")
    labels = as_labels(ctx.df[group.key])
    y = pd.to_numeric(ctx.df[outcome.key], errors="coerce")
    present = ordered_levels(group, sorted(set(labels.dropna())))
    chosen = ctx.params.get("levels")
    if chosen is None:
        if len(present) != 2:
            raise AnalysisError(
                f"« {group.name} » a {len(present)} modalité(s) dans les données. Choisissez les deux groupes à "
                "comparer" + (" (ou utilisez une ANOVA, prévue dans une phase ultérieure)." if len(present) > 2
                              else "."))
        chosen = present
    if (not isinstance(chosen, list) or len(chosen) != 2 or len(set(chosen)) != 2
            or not all(isinstance(c, str) and c in present for c in chosen)):
        raise AnalysisError("Choisissez deux groupes différents présents dans les données.")
    a, b = chosen
    in_groups = labels.isin([a, b])
    complete = in_groups & y.notna()
    x1 = y[complete & (labels == a)].to_numpy(dtype="float64")
    x2 = y[complete & (labels == b)].to_numpy(dtype="float64")
    total = len(ctx.df)
    info = {
        "total": total, "other_groups": int((labels.notna() & ~in_groups).sum()),
        "missing": int((in_groups & y.isna()).sum() + labels.isna().sum()),
        "used": int(complete.sum()), "levels_present": len(present),
    }
    for lv, x in ((a, x1), (b, x2)):
        if len(x) < 2:
            raise AnalysisError(f"Le groupe « {level_label(group, lv)} » a moins de deux valeurs : la comparaison "
                                "est impossible.")
    return outcome, group, a, b, x1, x2, info


def _group_tables(res: Result, outcome: Variable, group: Variable, a: str, b: str, x1: np.ndarray,
                  x2: np.ndarray, conf: float) -> None:
    rows = []
    for lv, x in ((a, x1), (b, x2)):
        s = summarize(x, conf)
        rows.append([level_label(group, lv), s["n"], s["mean"], s["sd"], s["median"], s["q1"], s["q3"],
                     s["min"], s["max"]])
    res.table(f"« {outcome.name} » par groupe", ["Groupe", "n", "Moyenne", "Écart-type", "Médiane", "Q1", "Q3",
                                                 "Min", "Max"], rows,
              kinds=["text", "int"] + ["num"] * 7)
    res.chart("boxplot", f"« {outcome.name} » selon « {group.name} »", {
        "series": [{"label": level_label(group, lv), "variable": outcome.name, **box_stats(x)}
                   for lv, x in ((a, x1), (b, x2))], "unit": outcome.unit})
    for lv, x in ((a, x1), (b, x2)):
        res.chart("histogram", f"« {outcome.name} », groupe « {level_label(group, lv)} »",
                  {"variable": outcome.name, "unit": outcome.unit, **histogram(x)})


def _group_diagnostics(res: Result, outcome: Variable, group: Variable, a: str, b: str, x1: np.ndarray,
                       x2: np.ndarray, info: dict[str, Any], parametric: bool) -> None:
    la, lb = level_label(group, a), level_label(group, b)
    if info["other_groups"]:
        res.diag("information", f"{info['other_groups']} ligne(s) appartenant à d'autres modalités de "
                                f"« {group.name} » ne sont pas incluses.")
    for lv, x in ((la, x1), (lb, x2)):
        if len(x) < SMALL_GROUP:
            res.diag("important", f"Le groupe « {lv} » ne compte que {len(x)} observation(s).",
                     "Avec si peu de données, le test manque de puissance et ses conditions ne peuvent pas être "
                     "vérifiées de façon fiable.")
        if np.ptp(x) == 0:
            res.diag("important", f"« {outcome.name} » est constante dans le groupe « {lv} ».")
        box = box_stats(x)
        if box["outlier_count"]:
            res.diag("methodologique", f"Groupe « {lv} » : {box['outlier_count']} valeur(s) extrême(s) "
                                       "(au-delà de 1,5 × EIQ).",
                     "Les moyennes et le test t y sont sensibles ; vérifiez ces valeurs." if parametric else
                     "Les tests de rangs y sont peu sensibles, mais vérifiez qu'il ne s'agit pas d'erreurs.")
    big, small = max(len(x1), len(x2)), min(len(x1), len(x2))
    if small and big / small >= 2:
        res.diag("information", f"Groupes déséquilibrés ({len(x1)} et {len(x2)} observations).")
    if parametric:
        if outcome.level == "ordinal":
            res.diag("methodologique", f"« {outcome.name} » est déclarée ordinale.",
                     "Une moyenne suppose des écarts égaux entre les niveaux ; le test de Mann-Whitney est souvent "
                     "plus adapté aux échelles ordinales.")
        for lv, x in ((la, x1), (lb, x2)):
            sw = shapiro(x)
            if sw:
                res.diag("information", f"Normalité (Shapiro-Wilk), groupe « {lv} » : W = {fr(sw[0], 3)}, "
                                        f"{fr_p(sw[1])}.", NORMALITY_NOTE)
                res.values[f"shapiro_w|{lv}"], res.values[f"shapiro_p|{lv}"] = sw
        with np.errstate(all="ignore"):
            lev = sps.levene(x1, x2, center="median")
        if math.isfinite(float(lev.statistic)) and math.isfinite(float(lev.pvalue)):
            res.values["levene_f"], res.values["levene_p"] = float(lev.statistic), float(lev.pvalue)
            sds = sorted((float(np.std(x1, ddof=1)), float(np.std(x2, ddof=1))))
            ratio = sds[1] / sds[0] if sds[0] > 0 else None
            res.diag("information", f"Homogénéité des variances (Levene, centré sur la médiane) : "
                                    f"F = {fr(float(lev.statistic))}, {fr_p(float(lev.pvalue))} ; rapport des "
                                    f"écarts-types = {fr(ratio)}.",
                     "Le test de Welch ne suppose pas l'égalité des variances ; il est recommandé par défaut.")
    if info["missing"]:
        res.diag("information", f"{info['missing']} ligne(s) exclue(s) pour valeur manquante (variable comparée "
                                "ou groupe).")


def two_sample_t(ctx: Context, equal_var: bool) -> Result:
    outcome, group, a, b, x1, x2, info = _two_groups(ctx)
    alt, conf, alpha = ctx.alternative(), ctx.conf_level(), ctx.alpha()
    method = "student" if equal_var else "welch"
    title = "Test t de Student (variances égales)" if equal_var else "Test t de Welch"
    res = Result(method, title)
    res.variables = [outcome.name, group.name]
    n1, n2 = len(x1), len(x2)
    m1, m2 = float(np.mean(x1)), float(np.mean(x2))
    v1, v2 = float(np.var(x1, ddof=1)), float(np.var(x2, ddof=1))
    diff = m1 - m2
    if equal_var:
        df = n1 + n2 - 2
        sp2 = ((n1 - 1) * v1 + (n2 - 1) * v2) / df
        se = math.sqrt(sp2 * (1 / n1 + 1 / n2))
        sd_effect = math.sqrt(sp2)
    else:
        se = math.sqrt(v1 / n1 + v2 / n2)
        df = (v1 / n1 + v2 / n2) ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) if se > 0 else math.nan
        sd_effect = math.sqrt((v1 + v2) / 2)
    if se == 0:
        raise AnalysisError("Les deux groupes sont constants : le test t n'est pas calculable.")
    t = diff / se
    p = _p_t(t, df, alt)
    lo, hi = _t_ci(diff, se, df, conf, alt)
    d = diff / sd_effect if sd_effect > 0 else None
    g = d * hedges_correction(n1 + n2 - 2) if d is not None else None
    la, lb = level_label(group, a), level_label(group, b)
    res.stat("t", "t", t)
    res.stat("df", "Degrés de liberté", df, "df", 2 if not equal_var else 0)
    res.stat("p", "Valeur p", p, "p")
    res.stat("mean_diff", f"Différence de moyennes ({la} − {lb})", diff, "estimate")
    res.stat("ci_low", "IC bas", lo, "ci")
    res.stat("ci_high", "IC haut", hi, "ci")
    res.stat("cohen_d", "d de Cohen" + ("" if equal_var else " (écart-type moyen)"), d, "effect")
    res.stat("hedges_g", "g de Hedges", g, "effect")
    res.values.update(n1=n1, n2=n2, mean1=m1, mean2=m2, se=se, conf_level=conf, alternative=alt)
    _group_tables(res, outcome, group, a, b, x1, x2, conf)
    _group_diagnostics(res, outcome, group, a, b, x1, x2, info, parametric=True)
    res.n_used = info["used"]
    res.missing = missing_note(info["total"] - info["other_groups"], info["used"], [outcome.name, group.name])
    sig = _significance(p, alpha)
    df_txt = fr(df, 0) if equal_var else fr(df, 2)
    hyp = {"two-sided": "", "less": f" (hypothèse : moyenne de « {la} » inférieure)",
           "greater": f" (hypothèse : moyenne de « {la} » supérieure)"}[alt]
    res.interpretation = [
        f"Moyenne de « {outcome.name} » : {fr(m1)} dans le groupe « {la} » (n = {n1}) et {fr(m2)} dans le groupe "
        f"« {lb} » (n = {n2}), soit une différence de {fr(diff)} ({_ci_text(lo, hi, conf)}).",
        f"Au seuil de {fr(alpha * 100, 0)} %, cette différence {'est' if sig else 'n’est pas'} statistiquement "
        f"significative{hyp} : t({df_txt}) = {fr(t)}, {fr_p(p)}.",
        f"Taille d'effet : d = {fr(d)} ({magnitude_d(d)} selon les repères indicatifs de Cohen).",
        CAUTION_GROUPS,
    ]
    if equal_var:
        res.diag("methodologique", "Le test de Student suppose des variances égales dans les deux groupes.",
                 "Le test de Welch donne des résultats presque identiques quand les variances sont égales et reste "
                 "fiable quand elles diffèrent ; il est généralement préféré.")
    return res


def _rank_with_ties(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ranks = sps.rankdata(values)
    _, counts = np.unique(ranks, return_counts=True)
    return ranks, counts


def mann_whitney(ctx: Context) -> Result:
    outcome, group, a, b, x1, x2, info = _two_groups(ctx)
    alt, conf, alpha = ctx.alternative(), ctx.conf_level(), ctx.alpha()
    res = Result("mann_whitney", "Test de Mann-Whitney (Wilcoxon, échantillons indépendants)")
    res.variables = [outcome.name, group.name]
    n1, n2 = len(x1), len(x2)
    ranks, tie_counts = _rank_with_ties(np.concatenate([x1, x2]))
    w = float(ranks[:n1].sum() - n1 * (n1 + 1) / 2)
    ties = bool((tie_counts > 1).any())
    exact = n1 < 50 and n2 < 50 and not ties
    if exact:
        if alt == "two-sided":
            pp = pwilcox(w - 1, n1, n2, False) if w > n1 * n2 / 2 else pwilcox(w, n1, n2)
            p = min(2 * pp, 1.0)
        elif alt == "greater":
            p = pwilcox(w - 1, n1, n2, False)
        else:
            p = pwilcox(w, n1, n2)
        z = None
    else:
        z0 = w - n1 * n2 / 2
        sigma = math.sqrt((n1 * n2 / 12) * ((n1 + n2 + 1) - (tie_counts ** 3 - tie_counts).sum()
                                             / ((n1 + n2) * (n1 + n2 - 1))))
        if sigma == 0:
            raise AnalysisError("Toutes les valeurs sont identiques : le test n'est pas calculable.")
        corr = {"two-sided": math.copysign(0.5, z0) if z0 != 0 else 0.0, "greater": 0.5, "less": -0.5}[alt]
        z = (z0 - corr) / sigma
        p = _p_two_sided_norm(z, alt)
    r_rb = 2 * w / (n1 * n2) - 1
    ps = w / (n1 * n2)
    la, lb = level_label(group, a), level_label(group, b)
    res.stat("w", "W (U de Mann-Whitney)", w, "value", 1)
    if z is not None:
        res.stat("z", "z (approximation normale)", z)
    res.stat("p", "Valeur p", p, "p")
    res.stat("rank_biserial", "Corrélation bisériale de rangs", r_rb, "effect")
    res.stat("prob_superiority", f"Probabilité qu'une valeur de « {la} » dépasse une valeur de « {lb} »", ps,
             "effect")
    res.stat("median1", f"Médiane « {la} »", float(np.median(x1)), "estimate")
    res.stat("median2", f"Médiane « {lb} »", float(np.median(x2)), "estimate")
    res.values.update(n1=n1, n2=n2, exact=exact, alternative=alt)
    _group_tables(res, outcome, group, a, b, x1, x2, conf)
    _group_diagnostics(res, outcome, group, a, b, x1, x2, info, parametric=False)
    res.diag("information", "Valeur p exacte." if exact else
             "Valeur p par approximation normale avec correction de continuité"
             + (" et correction pour les ex aequo." if ties else "."),
             "" if exact else "Comme R : la loi exacte n'est utilisée que sans ex aequo et pour des groupes de "
                              "moins de 50 observations.")
    res.n_used = info["used"]
    res.missing = missing_note(info["total"] - info["other_groups"], info["used"], [outcome.name, group.name])
    sig = _significance(p, alpha)
    res.interpretation = [
        f"Médiane de « {outcome.name} » : {fr(float(np.median(x1)))} dans le groupe « {la} » (n = {n1}) et "
        f"{fr(float(np.median(x2)))} dans le groupe « {lb} » (n = {n2}).",
        f"Au seuil de {fr(alpha * 100, 0)} %, la différence de distribution entre les deux groupes "
        f"{'est' if sig else 'n’est pas'} statistiquement significative : W = {fr(w, 1)}, {fr_p(p)}.",
        f"Corrélation bisériale de rangs : {fr(r_rb)} ({magnitude_r(r_rb)}). Ce test compare les rangs : il "
        "porte sur la tendance d'un groupe à prendre des valeurs plus élevées, pas strictement sur les médianes.",
        CAUTION_GROUPS,
    ]
    return res


# ======================================================================= mesures appariées
def _paired(ctx: Context) -> tuple[Variable, Variable, np.ndarray, np.ndarray, int]:
    first = ctx.var("first", label="première mesure", types=("numerique",))
    second = ctx.var("second", label="seconde mesure", types=("numerique",))
    if first.key == second.key:
        raise AnalysisError("Choisissez deux mesures différentes.")
    a = pd.to_numeric(ctx.df[first.key], errors="coerce")
    b = pd.to_numeric(ctx.df[second.key], errors="coerce")
    ok = a.notna() & b.notna()
    if ok.sum() < 2:
        raise AnalysisError("Moins de deux paires complètes : le test est impossible.")
    return first, second, a[ok].to_numpy("float64"), b[ok].to_numpy("float64"), len(ctx.df)


def _paired_common(res: Result, first: Variable, second: Variable, x: np.ndarray, y: np.ndarray,
                   total: int, conf: float, parametric: bool) -> np.ndarray:
    d = x - y
    rows = []
    for name, v in ((first.name, x), (second.name, y), (f"Différence ({first.name} − {second.name})", d)):
        s = summarize(v, conf)
        rows.append([name, s["n"], s["mean"], s["sd"], s["median"], s["q1"], s["q3"], s["min"], s["max"]])
    res.table("Mesures appariées", ["Mesure", "n", "Moyenne", "Écart-type", "Médiane", "Q1", "Q3", "Min", "Max"],
              rows, kinds=["text", "int"] + ["num"] * 7)
    res.chart("histogram", "Distribution des différences", {"variable": "Différence", "unit": first.unit,
                                                             **histogram(d)})
    res.chart("boxplot", "Les deux mesures", {"series": [
        {"label": first.name, "variable": first.name, **box_stats(x)},
        {"label": second.name, "variable": second.name, **box_stats(y)}], "unit": first.unit})
    n = len(d)
    res.n_used = n
    res.missing = missing_note(total, n, [first.name, second.name])
    if n < SMALL_GROUP:
        res.diag("important", f"Seulement {n} paire(s) complète(s).", "Le test manque de puissance.")
    box = box_stats(d)
    if box["outlier_count"]:
        res.diag("methodologique", f"{box['outlier_count']} différence(s) extrême(s) (au-delà de 1,5 × EIQ).")
    if parametric:
        sw = shapiro(d)
        if sw:
            res.diag("information", f"Normalité des différences (Shapiro-Wilk) : W = {fr(sw[0], 3)}, {fr_p(sw[1])}.",
                     NORMALITY_NOTE)
            res.values["shapiro_w"], res.values["shapiro_p"] = sw
        if first.level == "ordinal" or second.level == "ordinal":
            res.diag("methodologique", "Au moins une mesure est déclarée ordinale.",
                     "Le test de Wilcoxon pour échantillons appariés est souvent plus adapté.")
    if first.unit and second.unit and first.unit != second.unit:
        res.diag("important", f"Les deux mesures n'ont pas la même unité ({first.unit} et {second.unit}).")
    if total - n:
        res.diag("information", f"{total - n} ligne(s) sans les deux mesures sont exclues.")
    return d


def paired_t(ctx: Context) -> Result:
    first, second, x, y, total = _paired(ctx)
    alt, conf, alpha = ctx.alternative(), ctx.conf_level(), ctx.alpha()
    res = Result("paired_t", "Test t apparié")
    res.variables = [first.name, second.name]
    d = _paired_common(res, first, second, x, y, total, conf, parametric=True)
    n = len(d)
    mean_d = float(np.mean(d))
    sd_d = float(np.std(d, ddof=1))
    if sd_d == 0:
        raise AnalysisError("Toutes les différences sont identiques : le test t apparié n'est pas calculable.")
    se = sd_d / math.sqrt(n)
    df = n - 1
    t = mean_d / se
    p = _p_t(t, df, alt)
    lo, hi = _t_ci(mean_d, se, df, conf, alt)
    dz = mean_d / sd_d
    res.stat("t", "t", t)
    res.stat("df", "Degrés de liberté", df, "df", 0)
    res.stat("p", "Valeur p", p, "p")
    res.stat("mean_diff", f"Différence moyenne ({first.name} − {second.name})", mean_d, "estimate")
    res.stat("ci_low", "IC bas", lo, "ci")
    res.stat("ci_high", "IC haut", hi, "ci")
    res.stat("cohen_dz", "d de Cohen (dz, différences)", dz, "effect")
    res.values.update(n=n, sd_diff=sd_d, conf_level=conf, alternative=alt)
    sig = _significance(p, alpha)
    res.interpretation = [
        f"Sur {n} paire(s), la différence moyenne « {first.name} » − « {second.name} » est de {fr(mean_d)} "
        f"({_ci_text(lo, hi, conf)}).",
        f"Au seuil de {fr(alpha * 100, 0)} %, elle {'est' if sig else 'n’est pas'} statistiquement significative : "
        f"t({df}) = {fr(t)}, {fr_p(p)}.",
        f"Taille d'effet : dz = {fr(dz)} ({magnitude_d(dz)} selon les repères indicatifs de Cohen, à interpréter "
        "avec prudence pour des mesures appariées).",
        CAUTION_GROUPS,
    ]
    return res


def wilcoxon_paired(ctx: Context) -> Result:
    first, second, x, y, total = _paired(ctx)
    alt, conf, alpha = ctx.alternative(), ctx.conf_level(), ctx.alpha()
    res = Result("wilcoxon", "Test de Wilcoxon pour échantillons appariés")
    res.variables = [first.name, second.name]
    d_all = _paired_common(res, first, second, x, y, total, conf, parametric=False)
    zeros = int((d_all == 0).sum())
    d = d_all[d_all != 0]
    n = len(d)
    if n == 0:
        raise AnalysisError("Toutes les différences sont nulles : le test n'est pas calculable.")
    ranks, tie_counts = _rank_with_ties(np.abs(d))
    v = float(ranks[d > 0].sum())
    v_minus = float(ranks[d < 0].sum())
    ties = bool((tie_counts > 1).any())
    exact = n < 50 and not ties and zeros == 0
    if exact:
        if alt == "two-sided":
            pp = psignrank(v - 1, n, False) if v > n * (n + 1) / 4 else psignrank(v, n)
            p = min(2 * pp, 1.0)
        elif alt == "greater":
            p = psignrank(v - 1, n, False)
        else:
            p = psignrank(v, n)
        z = None
    else:
        z0 = v - n * (n + 1) / 4
        sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24 - (tie_counts ** 3 - tie_counts).sum() / 48)
        corr = {"two-sided": math.copysign(0.5, z0) if z0 != 0 else 0.0, "greater": 0.5, "less": -0.5}[alt]
        z = (z0 - corr) / sigma
        p = _p_two_sided_norm(z, alt)
    r_rb = (v - v_minus) / (v + v_minus)
    res.stat("v", "V (somme des rangs positifs)", v, "value", 1)
    if z is not None:
        res.stat("z", "z (approximation normale)", z)
    res.stat("p", "Valeur p", p, "p")
    res.stat("rank_biserial", "Corrélation bisériale de rangs appariée", r_rb, "effect")
    res.stat("median_diff", f"Médiane des différences ({first.name} − {second.name})", float(np.median(d_all)),
             "estimate")
    res.values.update(n_nonzero=n, zeros=zeros, exact=exact, alternative=alt)
    if zeros:
        res.diag("information", f"{zeros} paire(s) sans différence (différence nulle) sont écartées du calcul, "
                                "comme dans R.")
    res.diag("information", "Valeur p exacte." if exact else
             "Valeur p par approximation normale avec correction de continuité"
             + (" et correction pour les ex aequo." if ties else "."))
    sig = _significance(p, alpha)
    res.interpretation = [
        f"Sur {len(d_all)} paire(s) ({n} avec une différence non nulle), la médiane des différences "
        f"« {first.name} » − « {second.name} » est de {fr(float(np.median(d_all)))}.",
        f"Au seuil de {fr(alpha * 100, 0)} %, l'écart entre les deux mesures {'est' if sig else 'n’est pas'} "
        f"statistiquement significatif : V = {fr(v, 1)}, {fr_p(p)}.",
        f"Corrélation bisériale de rangs appariée : {fr(r_rb)} ({magnitude_r(r_rb)}).",
        CAUTION_GROUPS,
    ]
    return res


# ======================================================================= corrélations
def _pair_xy(ctx: Context) -> tuple[Variable, Variable, np.ndarray, np.ndarray, int]:
    xv = ctx.var("x", label="première variable", types=("numerique",))
    yv = ctx.var("y", label="seconde variable", types=("numerique",))
    if xv.key == yv.key:
        raise AnalysisError("Choisissez deux variables différentes.")
    a = pd.to_numeric(ctx.df[xv.key], errors="coerce")
    b = pd.to_numeric(ctx.df[yv.key], errors="coerce")
    ok = a.notna() & b.notna()
    x, y = a[ok].to_numpy("float64"), b[ok].to_numpy("float64")
    if len(x) < 3:
        raise AnalysisError("Moins de trois observations complètes : la corrélation n'est pas calculable.")
    for v, arr in ((xv, x), (yv, y)):
        if np.ptp(arr) == 0:
            raise AnalysisError(f"« {v.name} » est constante : la corrélation n'est pas calculable.")
    return xv, yv, x, y, len(ctx.df)


MAX_SCATTER = 5000


def _corr_common(res: Result, xv: Variable, yv: Variable, x: np.ndarray, y: np.ndarray, total: int) -> None:
    n = len(x)
    res.n_used = n
    res.missing = missing_note(total, n, [xv.name, yv.name])
    pts = list(zip(x.tolist(), y.tolist()))
    res.chart("scatter", f"« {yv.name} » en fonction de « {xv.name} »", {
        "x_label": xv.name, "y_label": yv.name, "points": pts[:MAX_SCATTER], "n": n,
        "truncated": n > MAX_SCATTER})
    if n < 10:
        res.diag("important", f"Seulement {n} observations complètes.",
                 "Une corrélation estimée sur si peu de données est très imprécise.")
    if total - n:
        res.diag("information", f"{total - n} ligne(s) exclue(s) pour valeur manquante.")


def pearson(ctx: Context) -> Result:
    xv, yv, x, y, total = _pair_xy(ctx)
    alt, conf, alpha = ctx.alternative(), ctx.conf_level(), ctx.alpha()
    res = Result("pearson", "Corrélation de Pearson")
    res.variables = [xv.name, yv.name]
    n = len(x)
    r = float(np.corrcoef(x, y)[0, 1])
    r = max(min(r, 1.0), -1.0)
    df = n - 2
    t = math.sqrt(df) * r / math.sqrt(1 - r * r) if abs(r) < 1 else math.copysign(math.inf, r)
    p = _p_t(t, df, alt)
    lo = hi = None
    if n > 3 and abs(r) < 1:
        z, sigma = math.atanh(r), 1 / math.sqrt(n - 3)
        if alt == "less":
            lo, hi = -1.0, math.tanh(z + sigma * float(sps.norm.ppf(conf)))
        elif alt == "greater":
            lo, hi = math.tanh(z - sigma * float(sps.norm.ppf(conf))), 1.0
        else:
            q = float(sps.norm.ppf((1 + conf) / 2))
            lo, hi = math.tanh(z - q * sigma), math.tanh(z + q * sigma)
    res.stat("r", "r de Pearson", r, "effect")
    res.stat("t", "t", t)
    res.stat("df", "Degrés de liberté", df, "df", 0)
    res.stat("p", "Valeur p", p, "p")
    res.stat("ci_low", "IC bas", lo, "ci")
    res.stat("ci_high", "IC haut", hi, "ci")
    res.stat("r2", "r² (part de variance commune)", r * r, "effect")
    res.values.update(n=n, conf_level=conf, alternative=alt)
    _corr_common(res, xv, yv, x, y, total)
    for v, arr in ((xv, x), (yv, y)):
        box = box_stats(arr)
        if box["outlier_count"]:
            res.diag("methodologique", f"« {v.name} » : {box['outlier_count']} valeur(s) extrême(s).",
                     "Le coefficient de Pearson y est très sensible ; comparez avec la corrélation de Spearman.")
        g1 = skewness(arr)
        if g1 is not None and abs(g1) >= 1:
            res.diag("information", f"« {v.name} » est nettement asymétrique (G1 = {fr(g1)}).")
        if v.level == "ordinal":
            res.diag("methodologique", f"« {v.name} » est déclarée ordinale.",
                     "La corrélation de Spearman est en général plus adaptée.")
    res.diag("methodologique", "Le coefficient de Pearson ne mesure que la relation linéaire.",
             "Examinez le nuage de points : une relation courbe ou des sous-groupes peuvent passer inaperçus.")
    sig = _significance(p, alpha)
    direction = "positive" if r > 0 else "négative"
    ci = f" ({_ci_text(lo, hi, conf)})" if lo is not None else ""
    res.interpretation = [
        f"Entre « {xv.name} » et « {yv.name} » (n = {n}), la corrélation linéaire est {direction} : r = {fr(r)}{ci}.",
        f"Au seuil de {fr(alpha * 100, 0)} %, elle {'est' if sig else 'n’est pas'} statistiquement significative : "
        f"t({df}) = {fr(t)}, {fr_p(p)}. Intensité {magnitude_r(r)} selon les repères indicatifs de Cohen.",
        CAUTION_ASSOC,
    ]
    return res


def spearman(ctx: Context) -> Result:
    xv, yv, x, y, total = _pair_xy(ctx)
    alt, conf, alpha = ctx.alternative(), ctx.conf_level(), ctx.alpha()
    res = Result("spearman", "Corrélation de Spearman")
    res.variables = [xv.name, yv.name]
    n = len(x)
    rx, ry = sps.rankdata(x), sps.rankdata(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    q = (n ** 3 - n) * (1 - rho) / 6
    ties = min(len(np.unique(x)), len(np.unique(y))) < n
    exact = not ties
    if alt == "two-sided":
        pp = pspearman(q, n, False, exact) if q > (n ** 3 - n) / 6 else pspearman(q, n, True, exact)
        p = min(2 * pp, 1.0)
    elif alt == "greater":
        p = pspearman(q, n, True, exact)
    else:
        p = pspearman(q, n, False, exact)
    res.stat("rho", "rho de Spearman", rho, "effect")
    res.stat("s", "S", q, "value", 1)
    res.stat("p", "Valeur p", p, "p")
    res.values.update(n=n, exact=exact, alternative=alt)
    _corr_common(res, xv, yv, x, y, total)
    if exact:
        res.diag("information", "Valeur p exacte (n ≤ 9) ou approximation d'Edgeworth (algorithme AS 89), comme R."
                 if n > 9 else "Valeur p exacte.")
    else:
        res.diag("information", "Données avec ex aequo : valeur p par l'approximation de la loi t, comme R.")
    sig = _significance(p, alpha)
    direction = "positive" if rho > 0 else "négative"
    res.interpretation = [
        f"Entre « {xv.name} » et « {yv.name} » (n = {n}), la corrélation des rangs est {direction} : rho = {fr(rho)}.",
        f"Au seuil de {fr(alpha * 100, 0)} %, elle {'est' if sig else 'n’est pas'} statistiquement significative "
        f"({fr_p(p)}). Intensité {magnitude_r(rho)} selon les repères indicatifs de Cohen. La corrélation de "
        "Spearman mesure une relation monotone (pas forcément linéaire).",
        CAUTION_ASSOC,
    ]
    if n > 9 and exact:
        res.diag("information", "Aucun intervalle de confiance n'est fourni pour rho.",
                 "R n'en calcule pas non plus par défaut ; les méthodes approchées existantes ne sont pas encore "
                 "validées dans STATPFE.")
    return res


# ======================================================================= tableaux de contingence
def _contingency(ctx: Context) -> tuple[Variable, Variable, pd.DataFrame, list[str], list[str], int, int]:
    row = ctx.var("row", label="variable en ligne")
    col = ctx.var("col", label="variable en colonne")
    if row.key == col.key:
        raise AnalysisError("Choisissez deux variables différentes.")
    table, rlev, clev, total, used = crosstab_counts(ctx, row, col)
    for v, lev in ((row, rlev), (col, clev)):
        if len(lev) < 2:
            raise AnalysisError(f"« {v.name} » ne prend qu'une seule modalité dans les données analysées : le test "
                                "n'est pas calculable.")
    return row, col, table, rlev, clev, total, used


def chi_square(ctx: Context) -> Result:
    row, col, table, rlev, clev, total, used = _contingency(ctx)
    correct = ctx.flag("correction", True)
    alpha = ctx.alpha()
    res = Result("chi2", "Test du khi-deux d'indépendance")
    res.variables = [row.name, col.name]
    obs = table.to_numpy(dtype="float64")
    n = obs.sum()
    expected = np.outer(obs.sum(axis=1), obs.sum(axis=0)) / n
    dof = (obs.shape[0] - 1) * (obs.shape[1] - 1)
    yates = correct and dof == 1
    if yates:
        delta = np.minimum(0.5, np.abs(obs - expected))
        stat = float((((np.abs(obs - expected) - delta) ** 2) / expected).sum())
    else:
        stat = float(((obs - expected) ** 2 / expected).sum())
    stat_plain = float(((obs - expected) ** 2 / expected).sum())
    p = float(sps.chi2.sf(stat, dof))
    k = min(obs.shape) - 1
    v = math.sqrt(stat_plain / (n * k)) if n and k else None
    rs, cs = obs.sum(axis=1, keepdims=True) / n, obs.sum(axis=0, keepdims=True) / n
    stdres = (obs - expected) / np.sqrt(expected * (1 - rs) * (1 - cs))
    res.stat("chi2", "Khi-deux" + (" (correction de Yates)" if yates else ""), stat)
    res.stat("df", "Degrés de liberté", dof, "df", 0)
    res.stat("p", "Valeur p", p, "p")
    res.stat("cramer_v", "V de Cramér", v, "effect")
    res.values.update(n=int(n), yates=yates, expected=expected.tolist(), stdres=stdres.tolist())
    add_crosstab_tables(res, row, col, table, rlev, clev, "row")
    rlab = [level_label(row, x) for x in rlev]
    clab = [level_label(col, x) for x in clev]
    res.table("Effectifs théoriques (sous l'hypothèse d'indépendance)", [row.name] + clab,
              [[rlab[i]] + list(expected[i]) for i in range(len(rlev))], kinds=["text"] + ["num"] * len(clev))
    res.table("Résidus standardisés ajustés", [row.name] + clab,
              [[rlab[i]] + list(stdres[i]) for i in range(len(rlev))],
              "Une valeur au-delà de ±2 signale une case qui contribue nettement à l'écart à l'indépendance "
              "(repère indicatif, sans correction pour comparaisons multiples).",
              kinds=["text"] + ["num"] * len(clev))
    low = int((expected < 5).sum())
    cells = expected.size
    if (expected < 1).any() or low / cells > 0.2:
        res.diag("important", f"{low} case(s) sur {cells} ont un effectif théorique inférieur à 5"
                 + (" (et au moins une inférieure à 1)" if (expected < 1).any() else "") + ".",
                 "L'approximation du khi-deux n'est alors pas fiable : utilisez le test exact de Fisher ou "
                 "regroupez des modalités.")
    elif low:
        res.diag("information", f"{low} case(s) sur {cells} ont un effectif théorique inférieur à 5 (moins de "
                                "20 % des cases, aucune inférieure à 1).")
    if yates:
        res.diag("information", "Correction de continuité de Yates appliquée (tableau 2 × 2), comme R par défaut.")
    res.n_used = used
    res.missing = missing_note(total, used, [row.name, col.name])
    sig = _significance(p, alpha)
    res.interpretation = [
        f"Au seuil de {fr(alpha * 100, 0)} %, l'association entre « {row.name} » et « {col.name} » "
        f"{'est' if sig else 'n’est pas'} statistiquement significative : χ²({dof}) = {fr(stat)}, {fr_p(p)}, "
        f"n = {int(n)}.",
        f"V de Cramér = {fr(v)} : intensité {_magnitude_v(v, k)} selon les repères indicatifs de Cohen.",
        CAUTION_ASSOC,
    ]
    return res


def _magnitude_v(v: float | None, k: int) -> str:
    if v is None:
        return "non calculable"
    s = math.sqrt(k)
    return "négligeable" if v < 0.1 / s else "faible" if v < 0.3 / s else "moyenne" if v < 0.5 / s else "forte"


def fisher(ctx: Context) -> Result:
    row, col, table, rlev, clev, total, used = _contingency(ctx)
    alt = ctx.alternative()
    conf = ctx.conf_level()
    alpha = ctx.alpha()
    obs = table.to_numpy(dtype="int64")
    is_2x2 = obs.shape == (2, 2)
    if not is_2x2:
        if alt != "two-sided":
            raise AnalysisError("Une hypothèse unilatérale n'est possible que pour un tableau 2 × 2.")
        if obs.sum() > FISHER_MAX_N or obs.size > FISHER_MAX_CELLS:
            raise AnalysisError(f"Tableau trop grand pour le test exact de Fisher dans STATPFE (au plus "
                                f"{FISHER_MAX_N} observations et {FISHER_MAX_CELLS} cases). Utilisez le khi-deux ou "
                                "regroupez des modalités.")
    res = Result("fisher", "Test exact de Fisher")
    res.variables = [row.name, col.name]
    if is_2x2:
        p = float(sps.fisher_exact(obs, alternative=alt).pvalue)
        orr = odds_ratio(obs, kind="conditional")
        ci = orr.confidence_interval(confidence_level=conf, alternative=alt)
        or_est, or_lo, or_hi = float(orr.statistic), float(ci.low), float(ci.high)
        res.stat("p", "Valeur p", p, "p")
        res.stat("odds_ratio", "Rapport de cotes (estimation conditionnelle)", float(orr.statistic), "effect")
        res.stat("ci_low", "IC bas", float(ci.low), "ci")
        res.stat("ci_high", "IC haut", float(ci.high), "ci")
    else:
        p = fisher_exact_rxc(obs)
        res.stat("p", "Valeur p", p, "p")
    res.values.update(n=int(obs.sum()), alternative=alt)
    add_crosstab_tables(res, row, col, table, rlev, clev, "row")
    res.n_used = used
    res.missing = missing_note(total, used, [row.name, col.name])
    sig = _significance(p, alpha)
    lines = [f"Au seuil de {fr(alpha * 100, 0)} %, l'association entre « {row.name} » et « {col.name} » "
             f"{'est' if sig else 'n’est pas'} statistiquement significative ({fr_p(p)}, n = {int(obs.sum())})."]
    if is_2x2:
        r0, r1 = (level_label(row, x) for x in rlev)
        c0 = level_label(col, clev[0])
        lines.append(
            f"Rapport de cotes = {fr(or_est)} ({_ci_text(or_lo, or_hi, conf)}) : "
            f"cote de « {c0} » dans « {r0} » rapportée à celle dans « {r1} ». Une valeur de 1 correspond à "
            "l'absence d'association.")
        res.diag("information", "Comme R, le rapport de cotes est l'estimation du maximum de vraisemblance "
                                "conditionnelle (elle diffère légèrement du calcul (a × d) / (b × c)).")
    lines.append(CAUTION_ASSOC)
    res.interpretation = lines
    return res


MAX_TABLES = 2_000_000


def fisher_exact_rxc(obs: np.ndarray) -> float:
    """Valeur p exacte de Fisher pour un tableau r × c, par énumération de tous les tableaux de mêmes marges.

    Comme `fisher.test` de R : somme des probabilités des tableaux au plus aussi probables que le tableau
    observé (avec une tolérance relative de 1e-7 pour les égalités numériques).
    """
    rows = [int(v) for v in obs.sum(axis=1)]
    cols = [int(v) for v in obs.sum(axis=0)]
    n = sum(rows)
    lf = np.array([0.0] + list(np.cumsum(np.log(np.arange(1, n + 1)))))
    const = float(sum(lf[r] for r in rows) + sum(lf[c] for c in cols) - lf[n])
    observed = const - float(sum(lf[int(v)] for v in obs.ravel()))
    threshold = observed + math.log1p(1e-7)
    total = 0.0
    count = 0

    def fill_column(j: int, remaining: list[int], acc: float) -> None:
        nonlocal total, count
        if j == len(cols) - 1:
            count += 1
            if count > MAX_TABLES:
                raise AnalysisError("Tableau trop complexe pour le calcul exact de Fisher : utilisez le khi-deux ou "
                                    "regroupez des modalités.")
            logp = acc - float(sum(lf[r] for r in remaining))
            if logp <= threshold:
                total += math.exp(logp)
            return
        target = cols[j]
        rest_cap = [sum(remaining[i + 1:]) for i in range(len(remaining))]

        def place(i: int, left: int, cell_acc: float, used: list[int]) -> None:
            if i == len(remaining) - 1:
                if left <= remaining[i]:
                    new_rem = [remaining[k] - (used[k] if k < i else left) for k in range(len(remaining))]
                    fill_column(j + 1, new_rem, cell_acc - float(lf[left]))
                return
            lo = max(0, left - rest_cap[i])
            hi = min(remaining[i], left)
            for v in range(lo, hi + 1):
                used.append(v)
                place(i + 1, left - v, cell_acc - float(lf[v]), used)
                used.pop()

        place(0, target, acc, [])

    fill_column(0, rows, const)
    return min(total, 1.0)


def alternative_label(alt: str) -> str:
    return ALTERNATIVES[alt]
