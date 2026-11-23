"""Catalogue des méthodes disponibles et exécution d'une analyse.

Seules les méthodes présentes ici sont proposées dans l'interface ; chacune
est implémentée dans ce moteur et validée contre R (tests/reference).
"""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from statpfe.data.types import Variable
from statpfe.errors import ValidationError
from statpfe.stats import descriptive, tests
from statpfe.stats.common import Context, Result

GROUP_COMMON = ["alternative", "conf_level"]


def _m(key: str, label: str, family: str, run: Callable[[Context], Result], *, objective: str, variables: list[dict],
       conditions: list[str], params: list[str], results: list[str], warnings: list[str],
       r_equivalent: str) -> dict[str, Any]:
    return {"key": key, "label": label, "family": family, "run": run, "objective": objective, "variables": variables,
            "conditions": conditions, "params": params, "results": results, "warnings": warnings,
            "r_equivalent": r_equivalent}


def _v(name: str, label: str, kind: str, multiple: bool = False, optional: bool = False) -> dict[str, Any]:
    """kind : quantitative (numérique) | qualitative (toute variable à modalités) | any."""
    return {"name": name, "label": label, "kind": kind, "multiple": multiple, "optional": optional}


FAMILIES = {
    "describe": "Décrire",
    "compare2": "Comparer deux groupes indépendants",
    "paired": "Comparer deux mesures appariées",
    "correlate": "Relier deux variables quantitatives",
    "associate": "Relier deux variables qualitatives",
}

METHODS: dict[str, dict[str, Any]] = {m["key"]: m for m in [
    _m("descriptives", "Statistiques descriptives", "describe", descriptive.descriptives,
       objective="Résumer la tendance centrale, la dispersion et la forme de variables quantitatives, "
                 "éventuellement par groupe.",
       variables=[_v("variables", "Variables quantitatives", "quantitative", multiple=True),
                  _v("group", "Regrouper par (facultatif)", "qualitative", optional=True)],
       conditions=["Variables de type numérique."],
       params=["conf_level"],
       results=["n, manquants, moyenne, écart-type, erreur type, IC de la moyenne, médiane, quartiles, min, max, "
                "asymétrie, aplatissement", "Histogramme et boîte à moustaches"],
       warnings=["Valeurs extrêmes", "Variable constante", "Forte asymétrie", "Valeurs manquantes"],
       r_equivalent="mean, sd, quantile (type 7), t.test()$conf.int"),
    _m("frequencies", "Fréquences et pourcentages", "describe", descriptive.frequencies,
       objective="Compter les effectifs et pourcentages de chaque modalité d'une variable.",
       variables=[_v("variable", "Variable", "qualitative")],
       conditions=["Au plus 50 modalités différentes."],
       params=[],
       results=["Effectifs, % du total, % valides, % cumulés", "Diagramme en barres"],
       warnings=["Variable quantitative", "Une seule modalité"],
       r_equivalent="table, prop.table"),
    _m("crosstab", "Tableau croisé", "describe", descriptive.crosstab,
       objective="Décrire la répartition conjointe de deux variables qualitatives.",
       variables=[_v("row", "En ligne", "qualitative"), _v("col", "En colonne", "qualitative")],
       conditions=["Au plus 50 modalités par variable."],
       params=["percentages"],
       results=["Effectifs, pourcentages en ligne et en colonne", "Barres empilées"],
       warnings=[],
       r_equivalent="table, prop.table(margin = 1 ou 2)"),
    _m("welch", "Test t de Welch", "compare2", lambda c: tests.two_sample_t(c, equal_var=False),
       objective="Comparer les moyennes d'une variable quantitative entre deux groupes indépendants, sans supposer "
                 "des variances égales.",
       variables=[_v("outcome", "Variable à comparer", "quantitative"), _v("group", "Groupes", "qualitative")],
       conditions=["Observations indépendantes", "Distribution approximativement normale dans chaque groupe, ou "
                   "groupes assez grands", "Pas de valeurs extrêmes influentes"],
       params=["levels", "alternative", "conf_level"],
       results=["t, degrés de liberté de Welch, p, différence de moyennes et IC", "d de Cohen, g de Hedges"],
       warnings=["Petits groupes", "Valeurs extrêmes", "Variable ordinale"],
       r_equivalent="t.test(y ~ g)"),
    _m("student", "Test t de Student", "compare2", lambda c: tests.two_sample_t(c, equal_var=True),
       objective="Comparer les moyennes de deux groupes indépendants en supposant des variances égales.",
       variables=[_v("outcome", "Variable à comparer", "quantitative"), _v("group", "Groupes", "qualitative")],
       conditions=["Observations indépendantes", "Normalité approximative dans chaque groupe",
                   "Variances égales dans les deux groupes"],
       params=["levels", "alternative", "conf_level"],
       results=["t, degrés de liberté, p, différence de moyennes et IC", "d de Cohen, g de Hedges"],
       warnings=["Variances inégales (préférer Welch)", "Petits groupes", "Valeurs extrêmes"],
       r_equivalent="t.test(y ~ g, var.equal = TRUE)"),
    _m("mann_whitney", "Test de Mann-Whitney", "compare2", tests.mann_whitney,
       objective="Comparer deux groupes indépendants sur une variable quantitative ou ordinale, à partir des rangs.",
       variables=[_v("outcome", "Variable à comparer", "quantitative"), _v("group", "Groupes", "qualitative")],
       conditions=["Observations indépendantes", "Variable au moins ordinale"],
       params=["levels", "alternative", "conf_level"],
       results=["W, p (exacte ou approximation normale), médianes", "Corrélation bisériale de rangs"],
       warnings=["Nombreux ex aequo", "Petits groupes"],
       r_equivalent="wilcox.test(y ~ g)"),
    _m("paired_t", "Test t apparié", "paired", tests.paired_t,
       objective="Comparer deux mesures prises sur les mêmes individus (avant/après, deux conditions).",
       variables=[_v("first", "Première mesure", "quantitative"), _v("second", "Seconde mesure", "quantitative")],
       conditions=["Paires indépendantes entre elles", "Différences approximativement normales"],
       params=["alternative", "conf_level"],
       results=["t, degrés de liberté, p, différence moyenne et IC", "dz de Cohen"],
       warnings=["Peu de paires", "Différences extrêmes"],
       r_equivalent="t.test(x, y, paired = TRUE)"),
    _m("wilcoxon", "Test de Wilcoxon apparié", "paired", tests.wilcoxon_paired,
       objective="Comparer deux mesures appariées à partir des rangs des différences.",
       variables=[_v("first", "Première mesure", "quantitative"), _v("second", "Seconde mesure", "quantitative")],
       conditions=["Paires indépendantes entre elles", "Différences au moins ordinales"],
       params=["alternative", "conf_level"],
       results=["V, p (exacte ou approximation normale)", "Corrélation bisériale de rangs appariée"],
       warnings=["Différences nulles écartées", "Ex aequo"],
       r_equivalent="wilcox.test(x, y, paired = TRUE)"),
    _m("pearson", "Corrélation de Pearson", "correlate", tests.pearson,
       objective="Mesurer l'intensité de la relation linéaire entre deux variables quantitatives.",
       variables=[_v("x", "Première variable", "quantitative"), _v("y", "Seconde variable", "quantitative")],
       conditions=["Observations indépendantes", "Relation linéaire", "Pas de valeurs extrêmes influentes"],
       params=["alternative", "conf_level"],
       results=["r, t, degrés de liberté, p, IC de r (transformation de Fisher), r²", "Nuage de points"],
       warnings=["Valeurs extrêmes", "Relation non linéaire", "Peu d'observations"],
       r_equivalent="cor.test(x, y)"),
    _m("spearman", "Corrélation de Spearman", "correlate", tests.spearman,
       objective="Mesurer une relation monotone entre deux variables quantitatives ou ordinales.",
       variables=[_v("x", "Première variable", "quantitative"), _v("y", "Seconde variable", "quantitative")],
       conditions=["Observations indépendantes", "Variables au moins ordinales"],
       params=["alternative", "conf_level"],
       results=["rho, S, p", "Nuage de points"],
       warnings=["Ex aequo (approximation)", "Peu d'observations"],
       r_equivalent="cor.test(x, y, method = \"spearman\")"),
    _m("chi2", "Test du khi-deux d'indépendance", "associate", tests.chi_square,
       objective="Tester l'association entre deux variables qualitatives.",
       variables=[_v("row", "En ligne", "qualitative"), _v("col", "En colonne", "qualitative")],
       conditions=["Observations indépendantes", "Effectifs théoriques ≥ 5 dans au moins 80 % des cases et tous ≥ 1"],
       params=["correction", "conf_level"],
       results=["χ², degrés de liberté, p, V de Cramér", "Effectifs théoriques, résidus standardisés ajustés"],
       warnings=["Effectifs théoriques faibles (préférer Fisher)"],
       r_equivalent="chisq.test(table(x, y))"),
    _m("fisher", "Test exact de Fisher", "associate", tests.fisher,
       objective="Tester l'association entre deux variables qualitatives, y compris avec de petits effectifs.",
       variables=[_v("row", "En ligne", "qualitative"), _v("col", "En colonne", "qualitative")],
       conditions=["Observations indépendantes", "Tableau d'au plus 20 cases et 300 observations"],
       params=["alternative", "conf_level"],
       results=["p exacte", "Rapport de cotes et IC (tableau 2 × 2)"],
       warnings=[],
       r_equivalent="fisher.test(table(x, y))"),
]}

PARAM_LABELS = {
    "conf_level": "Niveau de confiance (90, 95 ou 99 %) ; le seuil de signification vaut 1 − niveau",
    "alternative": "Hypothèse alternative : bilatérale ou unilatérale",
    "levels": "Les deux groupes à comparer et leur ordre",
    "percentages": "Pourcentages en ligne, en colonne, les deux ou aucun",
    "correction": "Correction de continuité de Yates pour un tableau 2 × 2",
}


def catalog() -> dict[str, Any]:
    return {
        "families": FAMILIES,
        "methods": [{k: v for k, v in m.items() if k != "run"} for m in METHODS.values()],
        "param_labels": PARAM_LABELS,
    }


def run(method: Any, df: pd.DataFrame, variables: list[Variable], params: Any) -> dict[str, Any]:
    if not isinstance(method, str) or method not in METHODS:
        raise ValidationError("Méthode d'analyse inconnue.")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValidationError("Paramètres d'analyse invalides.")
    ctx = Context(df=df, variables=variables, params=dict(params))
    result = METHODS[method]["run"](ctx).to_dict()
    result["method"] = method
    result["method_label"] = METHODS[method]["label"]
    return result
