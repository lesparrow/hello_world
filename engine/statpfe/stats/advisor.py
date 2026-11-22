"""Assistant méthodologique déterministe.

À partir de l'objectif de l'étudiant, du dictionnaire des variables et de
caractéristiques simples des données (effectifs, nombre de groupes, forme des
distributions, effectifs théoriques), l'assistant recommande une méthode
disponible dans STATPFE et explique pourquoi. Il ne calcule aucun résultat de
test et ne fonde jamais son choix sur un test de normalité.

Les règles sont volontairement simples, lisibles et versionnées (RULES_VERSION) :
le choix enregistré avec une analyse indique la version des règles utilisée.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from statpfe.data.types import Variable
from statpfe.errors import ValidationError
from statpfe.stats.catalog import METHODS
from statpfe.stats.common import EXCLUDED_ROLES, MAX_GROUP_LEVELS, as_labels, fr, level_label, ordered_levels
from statpfe.stats.descriptive import box_stats, skewness
from statpfe.stats.tests import FISHER_MAX_CELLS, FISHER_MAX_N

RULES_VERSION = "assistant-1"
SMALL_N = 15
OBJECTIVES = {
    "describe": "Décrire des variables",
    "compare_groups": "Comparer des groupes indépendants",
    "compare_paired": "Comparer deux mesures sur les mêmes individus",
    "relate": "Étudier le lien entre deux variables",
}
PURPOSES = {"confirmatoire": "Confirmatoire (hypothèse fixée à l'avance)",
            "exploratoire": "Exploratoire (recherche de pistes)"}
PRINCIPLE = ("La recommandation repose sur le type des variables, le plan d'étude, les effectifs et la forme des "
             "distributions ; elle ne dépend jamais d'un seul test de normalité. Vous restez libre de choisir une "
             "autre méthode en justifiant votre choix.")
NOT_AVAILABLE = {
    "anova_welch": "ANOVA de Welch (plus de deux groupes)",
    "kruskal": "Test de Kruskal-Wallis (plus de deux groupes)",
    "regression": "Régression linéaire",
    "logistic": "Régression logistique",
}


# ====================================================================== nature des variables
def nature(v: Variable) -> str:
    """quantitative | ordinale | qualitative | date"""
    if v.type == "date":
        return "date"
    if v.type == "numerique" and v.level == "continu":
        return "quantitative"
    if v.level == "ordinal":
        return "ordinale"
    return "qualitative"


NATURE_LABEL = {"quantitative": "quantitative", "ordinale": "qualitative ordinale",
                "qualitative": "qualitative nominale", "date": "date"}


class Advice:
    def __init__(self, objective: str):
        self.objective = objective
        self.recommendation: dict[str, Any] | None = None
        self.unavailable: list[dict[str, str]] = []
        self.alternatives: list[dict[str, Any]] = []
        self.missing: list[str] = []
        self.observations: list[str] = []
        self.blocking: str | None = None

    def recommend(self, method: str, params: dict[str, Any], reasons: list[str], limits: list[str] | None = None,
                  checks: list[str] | None = None) -> None:
        m = METHODS[method]
        self.recommendation = {
            "method": method, "label": m["label"], "params": params, "reasons": reasons,
            "conditions": m["conditions"], "checks": checks or [], "limits": limits or [],
        }

    def alternative(self, method: str, params: dict[str, Any], when: str) -> None:
        if self.recommendation and self.recommendation["method"] == method:
            return
        self.alternatives.append({"method": method, "label": METHODS[method]["label"], "params": params,
                                  "when": when, "available": True})

    def not_available(self, key: str, when: str) -> None:
        self.alternatives.append({"method": None, "label": NOT_AVAILABLE[key], "params": {}, "when": when,
                                  "available": False})

    def to_dict(self, request: dict[str, Any]) -> dict[str, Any]:
        return {
            "rules_version": RULES_VERSION, "objective": self.objective, "objective_label": OBJECTIVES[self.objective],
            "recommendation": self.recommendation, "blocking": self.blocking, "alternatives": self.alternatives,
            "missing_information": self.missing, "observations": self.observations, "principle": PRINCIPLE,
            "request": request,
        }


# ====================================================================== point d'entrée
def advise(df: pd.DataFrame, variables: list[Variable], request: Any,
           hypotheses: list[str] | None = None) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValidationError("Demande d'assistance invalide.")
    objective = request.get("objective")
    if objective not in OBJECTIVES:
        raise ValidationError("Choisissez un objectif.")
    by_key = {v.key: v for v in variables}
    advice = Advice(objective)
    chosen = request.get("variables") or {}
    if not isinstance(chosen, dict):
        raise ValidationError("Variables invalides.")

    def get(name: str, label: str, optional: bool = False) -> Variable | None:
        key = chosen.get(name)
        if key in (None, ""):
            if not optional:
                raise ValidationError(f"Choisissez la variable « {label} ».")
            return None
        if key not in by_key:
            raise ValidationError(f"Variable inconnue ({label}).")
        v = by_key[key]
        if v.role in EXCLUDED_ROLES or v.potential_identifier:
            raise ValidationError(f"« {v.name} » est un identifiant ou est exclue des analyses : elle ne peut pas "
                                  "être analysée.")
        return v

    if objective == "describe":
        keys = chosen.get("variables")
        if not isinstance(keys, list) or not keys or len(keys) > 30:
            raise ValidationError("Choisissez entre 1 et 30 variables à décrire.")
        vs = []
        for k in keys:
            chosen["_v"] = k
            vs.append(get("_v", "variable"))
        chosen.pop("_v", None)
        _describe(advice, df, vs)
    elif objective == "compare_groups":
        outcome = get("outcome", "variable à comparer")
        group = get("group", "variable de groupe")
        if outcome.key == group.key:
            raise ValidationError("La variable comparée et la variable de groupe doivent être différentes.")
        _compare_groups(advice, df, outcome, group, request.get("levels"))
        if request.get("independent") is not True:
            advice.missing.append("Confirmez que chaque individu n'appartient qu'à un seul groupe (groupes "
                                  "indépendants). Si les mêmes personnes sont mesurées deux fois, choisissez "
                                  "« Comparer deux mesures sur les mêmes individus ».")
    elif objective == "compare_paired":
        first = get("first", "première mesure")
        second = get("second", "seconde mesure")
        if first.key == second.key:
            raise ValidationError("Choisissez deux mesures différentes.")
        _compare_paired(advice, df, first, second)
    else:
        x = get("x", "première variable")
        y = get("y", "seconde variable")
        if x.key == y.key:
            raise ValidationError("Choisissez deux variables différentes.")
        _relate(advice, df, x, y)

    purpose = request.get("purpose")
    if purpose not in (None, *PURPOSES):
        raise ValidationError("Nature de l'analyse inconnue.")
    if purpose is None:
        advice.missing.append("Précisez si l'analyse est confirmatoire (hypothèse fixée avant de voir les données) "
                              "ou exploratoire.")
    elif advice.recommendation is not None:
        if purpose == "confirmatoire":
            advice.recommendation["limits"].append(
                "Analyse confirmatoire : la méthode, le caractère bilatéral ou unilatéral et le seuil doivent être "
                "fixés avant de consulter les résultats. Enregistrer ce choix maintenant en garde la trace.")
        else:
            advice.recommendation["limits"].append(
                "Analyse exploratoire : présentez le résultat comme une piste. Multiplier les tests augmente le "
                "risque de résultats significatifs dus au hasard.")
    hyp = request.get("hypothesis")
    if hyp is not None:
        if not isinstance(hyp, int) or isinstance(hyp, bool) or not hypotheses or not 0 <= hyp < len(hypotheses):
            raise ValidationError("Hypothèse inconnue.")
    elif purpose == "confirmatoire" and hypotheses:
        advice.missing.append("Indiquez quelle hypothèse de l'étude cette analyse met à l'épreuve.")
    return advice.to_dict(_echo(request))


def _echo(request: dict[str, Any]) -> dict[str, Any]:
    keep = {k: request.get(k) for k in ("objective", "variables", "levels", "independent", "purpose", "hypothesis")
            if k in request}
    return keep


# ====================================================================== règles
def _numeric(series: pd.Series) -> np.ndarray:
    return pd.to_numeric(series, errors="coerce").dropna().to_numpy(dtype="float64")


def _shape(x: np.ndarray) -> dict[str, Any]:
    g1 = skewness(x) if len(x) >= 3 else None
    out = box_stats(x)["outlier_count"] if len(x) else 0
    return {"n": len(x), "skew": g1, "outliers": out, "irregular": (g1 is not None and abs(g1) >= 1) or out > 0}


def _shape_text(name: str, s: dict[str, Any]) -> str:
    parts = [f"n = {s['n']}"]
    if s["skew"] is not None:
        parts.append(f"asymétrie G1 = {fr(s['skew'])}")
    parts.append(f"{s['outliers']} valeur(s) extrême(s)" if s["outliers"] else "aucune valeur extrême")
    return f"{name} : " + ", ".join(parts) + "."


def _likert_check(advice: Advice, v: Variable, series: pd.Series) -> None:
    if v.type == "numerique" and v.level == "continu":
        k = int(pd.to_numeric(series, errors="coerce").nunique())
        if 2 < k <= 7:
            advice.missing.append(f"« {v.name} » ne prend que {k} valeurs différentes : s'il s'agit d'une échelle "
                                  "(Likert, notes de 1 à 5…), déclarez-la ordinale dans le dictionnaire.")


def _describe(advice: Advice, df: pd.DataFrame, vs: list[Variable]) -> None:
    quant = [v for v in vs if nature(v) == "quantitative"]
    qual = [v for v in vs if nature(v) in ("qualitative", "ordinale")]
    if any(nature(v) == "date" for v in vs):
        advice.missing.append("Les variables de type date ne sont pas encore décrites par STATPFE.")
    for v in quant:
        _likert_check(advice, v, df[v.key])
    if quant and len(qual) == 1:
        advice.recommend("descriptives", {"variables": [v.key for v in quant], "group": qual[0].key},
                         [f"Variable(s) quantitative(s) décrite(s) selon les modalités de « {qual[0].name} »."],
                         ["Des statistiques par groupe décrivent l'échantillon ; elles ne prouvent pas une "
                          "différence entre groupes."],
                         ["Comparer moyennes et médianes : un écart important signale une asymétrie."])
        advice.alternative("frequencies", {"variable": qual[0].key}, f"Pour décrire « {qual[0].name} » seule.")
    elif quant:
        advice.recommend("descriptives", {"variables": [v.key for v in quant]},
                         ["Variable(s) quantitative(s) : moyenne, écart-type, médiane, quartiles et graphiques."],
                         [], ["Valeurs extrêmes et asymétrie dans l'histogramme et la boîte à moustaches."])
        for v in qual:
            advice.alternative("frequencies", {"variable": v.key}, f"Pour décrire « {v.name} » (qualitative).")
        if len(qual) > 1:
            advice.missing.append("Plusieurs variables qualitatives sont choisies avec des quantitatives : décrivez-les "
                                  "séparément ou choisissez-en une pour regrouper.")
    elif len(qual) == 2:
        a, b = qual
        advice.recommend("crosstab", {"row": a.key, "col": b.key},
                         ["Deux variables qualitatives : le tableau croisé décrit leur répartition conjointe."], [],
                         ["Modalités rares, cases vides."])
        advice.alternative("frequencies", {"variable": a.key}, f"Pour décrire « {a.name} » seule.")
        advice.alternative("frequencies", {"variable": b.key}, f"Pour décrire « {b.name} » seule.")
    elif qual:
        v = qual[0]
        advice.recommend("frequencies", {"variable": v.key},
                         [f"« {v.name} » est {NATURE_LABEL[nature(v)]} : effectifs et pourcentages par modalité."], [],
                         ["Modalités très rares, valeurs manquantes."])
        for other in qual[1:]:
            advice.alternative("frequencies", {"variable": other.key}, f"Pour décrire « {other.name} ».")
    else:
        advice.blocking = "Aucune variable descriptible n'a été choisie."


def _group_labels(df: pd.DataFrame, group: Variable) -> tuple[pd.Series, list[str]]:
    labels = as_labels(df[group.key])
    present = ordered_levels(group, sorted(set(labels.dropna())))
    return labels, present


def _compare_groups(advice: Advice, df: pd.DataFrame, outcome: Variable, group: Variable, levels: Any) -> None:
    if nature(group) == "date" or nature(outcome) == "date":
        advice.blocking = "Les variables de type date ne peuvent pas être utilisées ici."
        return
    labels, present = _group_labels(df, group)
    if len(present) > MAX_GROUP_LEVELS:
        advice.blocking = (f"« {group.name} » a plus de {MAX_GROUP_LEVELS} valeurs différentes : ce n'est pas une "
                           "variable de groupe. Vérifiez son type et son niveau dans le dictionnaire.")
        return
    if group.type == "numerique" and group.level == "continu" and len(present) > 2:
        advice.missing.append(f"« {group.name} » est déclarée quantitative : si elle définit des groupes, déclarez-la "
                              "qualitative dans le dictionnaire.")
    k = len(present)
    advice.observations.append(f"« {group.name} » : {k} groupe(s) dans les données ("
                               + ", ".join(f"{level_label(group, p)} : {int((labels == p).sum())}" for p in present)
                               + ").")
    if k < 2:
        advice.blocking = f"« {group.name} » ne contient qu'un seul groupe : aucune comparaison n'est possible."
        return
    out_nature = nature(outcome)

    # Variable comparée qualitative : comparaison de proportions (tableau de contingence)
    if out_nature in ("qualitative", "ordinale") and not (outcome.type == "numerique" and out_nature == "ordinale"):
        _contingency(advice, df, group, outcome,
                     f"« {outcome.name} » est {NATURE_LABEL[out_nature]} : comparer sa répartition entre les groupes "
                     f"revient à tester l'association entre « {group.name} » et « {outcome.name} ».")
        if out_nature == "ordinale" and k == 2:
            advice.missing.append(f"« {outcome.name} » est ordinale mais de type texte : pour tenir compte de l'ordre "
                                  "(test de Mann-Whitney), recodez-la en valeurs numériques ordonnées.")
        return

    _likert_check(advice, outcome, df[outcome.key])
    chosen = levels if isinstance(levels, list) and len(levels) == 2 and all(lv in present for lv in levels) else None
    if k > 2 and chosen is None:
        advice.blocking = (f"« {group.name} » compte {k} groupes. La méthode adaptée (ANOVA de Welch ou test de "
                           "Kruskal-Wallis) n'est pas encore disponible dans STATPFE.")
        advice.not_available("anova_welch", "Variable quantitative, plus de deux groupes.")
        advice.not_available("kruskal", "Variable ordinale ou distributions très asymétriques, plus de deux groupes.")
        advice.missing.append("Vous pouvez comparer deux groupes précis (choisissez-les), en gardant à l'esprit que "
                              "multiplier les comparaisons deux à deux augmente le risque de faux positif.")
        return
    a, b = chosen or present[:2]
    y = pd.to_numeric(df[outcome.key], errors="coerce")
    x1 = y[(labels == a) & y.notna()].to_numpy("float64")
    x2 = y[(labels == b) & y.notna()].to_numpy("float64")
    s1, s2 = _shape(x1), _shape(x2)
    la, lb = level_label(group, a), level_label(group, b)
    advice.observations += [_shape_text(f"Groupe « {la} »", s1), _shape_text(f"Groupe « {lb} »", s2)]
    params = {"outcome": outcome.key, "group": group.key, "levels": [a, b]}
    if min(s1["n"], s2["n"]) < 2:
        advice.blocking = "Un des groupes a moins de deux valeurs : la comparaison est impossible."
        return
    small = min(s1["n"], s2["n"]) < SMALL_N
    irregular = s1["irregular"] or s2["irregular"]
    checks = ["Valeurs extrêmes et forme des distributions (boîtes à moustaches, histogrammes).",
              "Écart entre les tailles des groupes."]
    if out_nature == "ordinale":
        advice.recommend("mann_whitney", params, [
            f"« {outcome.name} » est ordinale : une moyenne suppose des écarts égaux entre niveaux, ce qui n'est pas "
            "garanti. Le test de Mann-Whitney compare les rangs."], [
            "Il compare la tendance d'un groupe à prendre des valeurs plus élevées, pas exactement les médianes.",
            "Avec beaucoup d'ex aequo, la valeur p est approchée."], checks)
        advice.alternative("welch", params, "Si l'échelle peut raisonnablement être traitée comme quantitative "
                                            "(score composite avec de nombreux niveaux, par exemple).")
    elif small and irregular:
        advice.recommend("mann_whitney", params, [
            f"Petits groupes (moins de {SMALL_N} observations dans au moins un groupe) et distribution asymétrique ou "
            "avec des valeurs extrêmes : la moyenne et le test t sont alors fragiles.",
            "Le test de Mann-Whitney, fondé sur les rangs, est peu sensible aux valeurs extrêmes."], [
            "Il ne compare pas les moyennes ; présentez plutôt les médianes et les quartiles."], checks)
        advice.alternative("welch", params, "Si les valeurs extrêmes sont des erreurs corrigées ou si l'objectif porte "
                                            "explicitement sur les moyennes.")
    else:
        reasons = [f"« {outcome.name} » est quantitative et les deux groupes sont indépendants : on compare les "
                   "moyennes.",
                   "Le test de Welch ne suppose pas que les variances des groupes sont égales ; quand elles le sont, "
                   "il donne pratiquement le même résultat que le test de Student. Il est donc recommandé par défaut."]
        if not small:
            reasons.append(f"Avec au moins {SMALL_N} observations par groupe, le test t reste fiable même si la "
                           "distribution n'est pas parfaitement normale.")
        limits = []
        if irregular:
            limits.append("Des valeurs extrêmes ou une asymétrie sont présentes : vérifiez-les et comparez avec le test "
                          "de Mann-Whitney (analyse de sensibilité).")
        advice.recommend("welch", params, reasons, limits, checks)
        advice.alternative("mann_whitney", params, "Si la distribution est très asymétrique, avec des valeurs "
                                                   "extrêmes, ou si la variable est en réalité ordinale.")
    advice.alternative("student", params, "Uniquement si l'égalité des variances est justifiée à l'avance (le test de "
                                          "Welch reste préférable en général).")
    if k > 2:
        advice.missing.append(f"Seuls les groupes « {la} » et « {lb} » sont comparés ; les {k - 2} autre(s) groupe(s) "
                              "sont exclus. Une comparaison globale (ANOVA) n'est pas encore disponible.")


def _compare_paired(advice: Advice, df: pd.DataFrame, first: Variable, second: Variable) -> None:
    for v in (first, second):
        if v.type != "numerique":
            advice.blocking = (f"« {v.name} » n'est pas numérique : pour comparer deux mesures appariées "
                               "qualitatives (test de McNemar), STATPFE n'a pas encore de méthode.")
            return
    a = pd.to_numeric(df[first.key], errors="coerce")
    b = pd.to_numeric(df[second.key], errors="coerce")
    ok = a.notna() & b.notna()
    d = (a[ok] - b[ok]).to_numpy("float64")
    s = _shape(d)
    advice.observations.append(_shape_text("Différences entre les deux mesures", s))
    if s["n"] < 2:
        advice.blocking = "Moins de deux paires complètes : la comparaison est impossible."
        return
    zeros = int((d == 0).sum())
    if zeros:
        advice.observations.append(f"{zeros} paire(s) avec une différence nulle.")
    params = {"first": first.key, "second": second.key}
    checks = ["Distribution des différences (histogramme), différences extrêmes."]
    if first.unit and second.unit and first.unit != second.unit:
        advice.missing.append(f"Les deux mesures n'ont pas la même unité ({first.unit} et {second.unit}) : leur "
                              "différence n'a de sens que si elles sont exprimées de la même façon.")
    for v in (first, second):
        _likert_check(advice, v, df[v.key])
    ordinal = "ordinale" in (nature(first), nature(second))
    if ordinal or (s["n"] < SMALL_N and s["irregular"]):
        reason = ("Au moins une mesure est ordinale : on compare les rangs des différences plutôt que leur moyenne."
                  if ordinal else
                  f"Peu de paires (moins de {SMALL_N}) et différences asymétriques ou extrêmes : la moyenne des "
                  "différences est fragile.")
        advice.recommend("wilcoxon", params, [reason, "Le test de Wilcoxon apparié repose sur les rangs des "
                                                      "différences."],
                         ["Les paires sans différence sont écartées du calcul."], checks)
        advice.alternative("paired_t", params, "Si les mesures sont quantitatives et que l'on s'intéresse à la "
                                               "différence moyenne.")
    else:
        reasons = ["Deux mesures quantitatives sur les mêmes individus : on étudie la moyenne des différences, ce qui "
                   "élimine les écarts propres à chaque individu."]
        if s["n"] >= SMALL_N:
            reasons.append(f"Avec au moins {SMALL_N} paires, le test t apparié reste fiable même si les différences ne "
                           "suivent pas exactement une loi normale.")
        advice.recommend("paired_t", params, reasons,
                         ["Différences extrêmes présentes : comparez avec le test de Wilcoxon."] if s["irregular"] else [],
                         checks)
        advice.alternative("wilcoxon", params, "Si les différences sont très asymétriques ou comportent des valeurs "
                                               "extrêmes, ou si les mesures sont ordinales.")


def _relate(advice: Advice, df: pd.DataFrame, x: Variable, y: Variable) -> None:
    nx, ny = nature(x), nature(y)
    if "date" in (nx, ny):
        advice.blocking = "Les variables de type date ne peuvent pas être utilisées ici."
        return
    numeric_x = x.type == "numerique"
    numeric_y = y.type == "numerique"
    quant_like = {"quantitative", "ordinale"}
    if nx in quant_like and ny in quant_like and numeric_x and numeric_y:
        a = pd.to_numeric(df[x.key], errors="coerce")
        b = pd.to_numeric(df[y.key], errors="coerce")
        ok = a.notna() & b.notna()
        sx, sy = _shape(a[ok].to_numpy("float64")), _shape(b[ok].to_numpy("float64"))
        advice.observations += [_shape_text(f"« {x.name} »", sx), _shape_text(f"« {y.name} »", sy)]
        n = sx["n"]
        if n < 3:
            advice.blocking = "Moins de trois observations complètes : aucune corrélation n'est calculable."
            return
        for v in (x, y):
            _likert_check(advice, v, df[v.key])
        params = {"x": x.key, "y": y.key}
        checks = ["Nuage de points : forme de la relation (droite, courbe), sous-groupes, points isolés."]
        limits = ["Une corrélation ne démontre pas un lien de cause à effet."]
        if n < 10:
            limits.append("Moins de 10 observations : l'estimation de la corrélation sera très imprécise.")
        if "ordinale" in (nx, ny):
            advice.recommend("spearman", params, ["Au moins une variable est ordinale : la corrélation de Spearman "
                                                  "utilise les rangs et mesure une relation monotone."], limits, checks)
            advice.alternative("pearson", params, "Si les deux variables peuvent être traitées comme quantitatives.")
        elif sx["outliers"] or sy["outliers"] or (sx["irregular"] and sy["irregular"]):
            advice.recommend("spearman", params, [
                "Valeurs extrêmes ou distributions très asymétriques : le coefficient de Pearson peut être dominé "
                "par quelques points. La corrélation de Spearman, fondée sur les rangs, y est peu sensible."],
                limits, checks)
            advice.alternative("pearson", params, "Pour décrire une relation linéaire, après vérification des valeurs "
                                                  "extrêmes (à présenter avec Spearman en analyse de sensibilité).")
        else:
            advice.recommend("pearson", params, [
                "Deux variables quantitatives sans valeurs extrêmes marquées : la corrélation de Pearson mesure "
                "l'intensité de la relation linéaire et fournit un intervalle de confiance."], limits, checks)
            advice.alternative("spearman", params, "Si la relation est monotone mais pas linéaire, ou en analyse de "
                                                   "sensibilité.")
        return
    qual_like = {"qualitative", "ordinale"}
    if nx in qual_like and ny in qual_like:
        _contingency(advice, df, x, y, "Deux variables qualitatives : on teste leur association à partir du tableau "
                                       "croisé.")
        return
    # Une quantitative et une qualitative : c'est une comparaison de groupes.
    quant, qual = (x, y) if nx == "quantitative" else (y, x)
    advice.observations.append(f"« {quant.name} » est quantitative et « {qual.name} » qualitative : étudier leur lien "
                               "revient à comparer « " + quant.name + " » entre les groupes définis par « "
                               + qual.name + " ».")
    advice.objective = "compare_groups"
    _compare_groups(advice, df, quant, qual, None)
    advice.missing.append("Vérifiez que chaque individu n'appartient qu'à un seul groupe (groupes indépendants).")


def _contingency(advice: Advice, df: pd.DataFrame, row: Variable, col: Variable, intro: str) -> None:
    r = as_labels(df[row.key])
    c = as_labels(df[col.key])
    ok = r.notna() & c.notna()
    table = pd.crosstab(r[ok], c[ok])
    if table.shape[0] > MAX_GROUP_LEVELS or table.shape[1] > MAX_GROUP_LEVELS:
        advice.blocking = "Une des variables a trop de modalités pour un tableau croisé : regroupez-les (recodage)."
        return
    if table.shape[0] < 2 or table.shape[1] < 2:
        advice.blocking = "Une des variables ne prend qu'une seule modalité dans les données."
        return
    obs = table.to_numpy(dtype="float64")
    n = obs.sum()
    expected = np.outer(obs.sum(axis=1), obs.sum(axis=0)) / n
    low = int((expected < 5).sum())
    cells = expected.size
    poor = bool((expected < 1).any()) or low / cells > 0.2
    advice.observations.append(f"Tableau {table.shape[0]} × {table.shape[1]}, n = {int(n)} ; {low} case(s) sur {cells} "
                               f"avec un effectif théorique inférieur à 5 (minimum {fr(float(expected.min()))}).")
    params = {"row": row.key, "col": col.key}
    checks = ["Effectifs théoriques et résidus standardisés ajustés."]
    fisher_ok = n <= FISHER_MAX_N and cells <= FISHER_MAX_CELLS
    if poor and fisher_ok:
        advice.recommend("fisher", params, [intro, "Plus de 20 % des cases ont un effectif théorique inférieur à 5 "
                                                   "(ou une case inférieure à 1) : l'approximation du khi-deux n'est "
                                                   "pas fiable. Le test exact de Fisher ne dépend pas de cette "
                                                   "approximation."],
                         ["Le test indique s'il existe une association, pas son sens ni sa cause."], checks)
        advice.alternative("chi2", params, "Si des modalités sont regroupées de façon à obtenir des effectifs "
                                           "théoriques suffisants.")
    else:
        reasons = [intro]
        limits = ["Le test indique s'il existe une association, pas son sens ni sa cause ; lisez les pourcentages et "
                  "les résidus."]
        if poor:
            limits.append("Effectifs théoriques trop faibles et tableau trop grand pour le test exact : regroupez des "
                          "modalités avant d'interpréter le résultat.")
        else:
            reasons.append("Les effectifs théoriques sont suffisants pour l'approximation du khi-deux.")
        advice.recommend("chi2", params, reasons, limits, checks)
        if fisher_ok:
            advice.alternative("fisher", params, "Si les effectifs sont faibles (valeur p exacte).")
    advice.alternative("crosstab", {**params, "percentages": "all"}, "Pour décrire la répartition sans tester.")
