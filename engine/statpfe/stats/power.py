"""Puissance statistique et taille d'échantillon.

Formules de Cohen (1988), identiques à celles du paquet R `pwr` (et, pour le
test t, à `power.t.test(strict = TRUE)` de R de base) :

- test t (deux groupes, apparié, un échantillon) : loi de Student non centrale ;
- deux proportions : transformation arc sinus, h = 2·asin√p₁ − 2·asin√p₂ ;
- khi-deux : loi du khi-deux non centrale, paramètre N·w² ;
- corrélation : transformation de Fisher avec correction de biais (pwr.r.test).

Un calcul de puissance est une estimation qui dépend entièrement des
hypothèses fournies (effet attendu, seuil, conditions du test) : ce module
renvoie toujours ces hypothèses avec le résultat. Il ne calcule jamais une
« puissance observée » à partir de l'effet mesuré sur les données.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from scipy import optimize
from scipy.stats import chi2 as chi2_dist
from scipy.stats import ncx2, nct, norm
from scipy.stats import t as t_dist

from statpfe.errors import ValidationError
from statpfe.stats.common import _finite, fr
from statpfe.stats.common import fr_pct as _fr_pct

N_MAX = 10_000_000
MAX_EFFECTS = 6
ALPHA_RANGE = (0.0001, 0.2)
POWER_RANGE = (0.5, 0.999)
ARE_NORMAL = 3 / math.pi  # efficacité relative asymptotique de Mann-Whitney / Wilcoxon sous normalité
ARE_MIN = 0.864           # borne inférieure, quelle que soit la loi (Hodges et Lehmann, 1956)

MODES = {
    "sample_size": "Taille d'échantillon nécessaire",
    "power": "Puissance pour un effectif donné",
    "effect": "Plus petit effet détectable",
}
SIDES = {"two-sided": "bilatéral", "one-sided": "unilatéral (dans le sens attendu)"}

DESIGNS: dict[str, dict[str, Any]] = {
    "t_two": {
        "label": "Comparer deux groupes indépendants (test t)",
        "effect": "d", "effect_label": "d de Cohen", "groups": 2, "sided": True,
        "benchmarks": [0.2, 0.5, 0.8], "n_min": 2,
        "methods": ["student", "welch", "mann_whitney"],
        "unit": "par groupe",
        "r_equivalent": "pwr::pwr.t2n.test(n1, n2, d, sig.level) ; power.t.test(strict = TRUE) si n₁ = n₂",
    },
    "t_paired": {
        "label": "Comparer deux mesures appariées (test t apparié)",
        "effect": "d", "effect_label": "dz (moyenne des différences / écart-type des différences)", "groups": 1,
        "sided": True, "benchmarks": [0.2, 0.5, 0.8], "n_min": 2,
        "methods": ["paired_t", "wilcoxon"], "unit": "paires",
        "r_equivalent": "pwr::pwr.t.test(type = \"paired\") ; power.t.test(type = \"paired\", strict = TRUE)",
    },
    "t_one": {
        "label": "Comparer une moyenne à une valeur de référence (test t à un échantillon)",
        "effect": "d", "effect_label": "d de Cohen", "groups": 1, "sided": True,
        "benchmarks": [0.2, 0.5, 0.8], "n_min": 2, "methods": [], "unit": "observations",
        "r_equivalent": "pwr::pwr.t.test(type = \"one.sample\") ; power.t.test(type = \"one.sample\", strict = TRUE)",
    },
    "prop_two": {
        "label": "Comparer deux proportions (groupes indépendants)",
        "effect": "h", "effect_label": "h de Cohen", "groups": 2, "sided": True,
        "benchmarks": [0.2, 0.5, 0.8], "n_min": 2, "methods": ["chi2", "fisher"], "unit": "par groupe",
        "r_equivalent": "pwr::pwr.2p2n.test(h, n1, n2, sig.level) ; pwr::ES.h(p1, p2)",
    },
    "chi2": {
        "label": "Tester l'association de deux variables qualitatives (khi-deux)",
        "effect": "w", "effect_label": "w de Cohen", "groups": 1, "sided": False,
        "benchmarks": [0.1, 0.3, 0.5], "n_min": 2, "methods": ["chi2"], "unit": "observations au total",
        "r_equivalent": "pwr::pwr.chisq.test(w, N, df, sig.level)",
    },
    "correlation": {
        "label": "Tester une corrélation entre deux variables quantitatives",
        "effect": "r", "effect_label": "r de Pearson", "groups": 1, "sided": True,
        "benchmarks": [0.1, 0.3, 0.5], "n_min": 4, "methods": ["pearson", "spearman"], "unit": "observations",
        "r_equivalent": "pwr::pwr.r.test(n, r, sig.level)",
    },
}

METHOD_TO_DESIGN = {m: d for d, spec in DESIGNS.items() for m in spec["methods"]}
METHOD_TO_DESIGN["fisher"] = "chi2"

ASSUMPTIONS = {
    "t_two": ["Observations indépendantes, deux groupes indépendants.",
              "Variable de résultat approximativement normale dans chaque groupe.",
              "Même écart-type dans les deux groupes (le calcul suit le test t de Student ; pour le test de Welch "
              "avec des écarts-types proches, le résultat est très voisin).",
              "d = différence de moyennes attendue divisée par l'écart-type commun."],
    "t_paired": ["Paires indépendantes les unes des autres.",
                 "Différences approximativement normales.",
                 "dz = moyenne attendue des différences divisée par l'écart-type des différences (et non par "
                 "l'écart-type d'une mesure)."],
    "t_one": ["Observations indépendantes.", "Variable approximativement normale.",
              "d = écart attendu à la valeur de référence divisé par l'écart-type."],
    "prop_two": ["Observations indépendantes, deux groupes indépendants.",
                 "Approximation normale après transformation arc sinus (Cohen, 1988) ; pour de très petits "
                 "effectifs, le test exact de Fisher est un peu moins puissant que ce calcul."],
    "chi2": ["Observations indépendantes, chaque observation dans une seule case du tableau.",
             "w = √(Σ (p₁ᵢ − p₀ᵢ)² / p₀ᵢ) ; pour un tableau 2 × 2, w est égal au coefficient phi.",
             "Effectifs théoriques suffisants (au moins 5 par case) pour que le khi-deux soit valide."],
    "correlation": ["Couples d'observations indépendants.",
                    "Relation linéaire, distribution approximativement normale des deux variables.",
                    "Approximation de Fisher avec correction de biais (identique à pwr.r.test)."],
}


# ---------------------------------------------------------------------- fonctions de puissance
def power_t(d: float, n1: float, n2: float | None, alpha: float, sides: str) -> float:
    """Test t : n2 = None pour un échantillon ou des mesures appariées (d = dz)."""
    if n2 is None:
        df, ncp = n1 - 1, d * math.sqrt(n1)
    else:
        df, ncp = n1 + n2 - 2, d * math.sqrt(n1 * n2 / (n1 + n2))
    if sides == "two-sided":
        q = t_dist.isf(alpha / 2, df)
        return float(nct.sf(q, df, ncp) + nct.cdf(-q, df, ncp))
    return float(nct.sf(t_dist.isf(alpha, df), df, ncp))


def power_prop(h: float, n1: float, n2: float, alpha: float, sides: str) -> float:
    z = h * math.sqrt(n1 * n2 / (n1 + n2))
    if sides == "two-sided":
        return float(norm.sf(norm.isf(alpha / 2) - z) + norm.cdf(norm.ppf(alpha / 2) - z))
    return float(norm.sf(norm.isf(alpha) - z))


def power_chi2(w: float, n: float, df: int, alpha: float) -> float:
    return float(ncx2.sf(chi2_dist.isf(alpha, df), df, n * w * w))


def power_r(r: float, n: float, alpha: float, sides: str) -> float:
    a = alpha / 2 if sides == "two-sided" else alpha
    q = t_dist.isf(a, n - 2)
    rc = math.sqrt(q * q / (q * q + n - 2))
    zr = math.atanh(r) + r / (2 * (n - 1))
    zrc = math.atanh(rc)
    s = math.sqrt(n - 3)
    p = norm.cdf((zr - zrc) * s)
    if sides == "two-sided":
        p += norm.cdf((-zr - zrc) * s)
    return float(p)


def cohen_h(p1: float, p2: float) -> float:
    return 2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p2))


# ---------------------------------------------------------------------- validation
def _number(raw: Any, label: str, lo: float, hi: float, *, open_lo: bool = False, open_hi: bool = False) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise ValidationError(f"« {label} » doit être un nombre.")
    x = float(raw)
    if x < lo or x > hi or (open_lo and x == lo) or (open_hi and x == hi):
        lo_s, hi_s = _g(lo, 4), _g(hi, 4)
        raise ValidationError(f"« {label} » doit être compris entre {lo_s} et {hi_s}"
                              f"{' (bornes exclues)' if open_lo and open_hi else ''}.")
    return x


def fr_pct(x: float) -> str:
    return _fr_pct(x).replace(" %", "\u00a0%")


def _g(x: float, digits: int = 3) -> str:
    """Nombre court : au plus `digits` décimales, sans zéros inutiles (0,5 et non 0,500)."""
    s = fr(x, digits)
    return s.rstrip("0").rstrip(",") if "," in s else s


def _int(raw: Any, label: str, lo: int, hi: int) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        if isinstance(raw, float) and raw.is_integer():
            raw = int(raw)
        else:
            raise ValidationError(f"« {label} » doit être un nombre entier.")
    if not lo <= raw <= hi:
        raise ValidationError(f"« {label} » doit être un entier compris entre {lo} et {hi}.")
    return raw


def _text(raw: Any, label: str, max_len: int = 2000) -> str:
    if raw is None:
        return ""
    if not isinstance(raw, str) or len(raw) > max_len:
        raise ValidationError(f"« {label} » : texte invalide ou trop long ({max_len} caractères au plus).")
    return raw.strip()


def _effect(design: str, raw: Any, sides: str) -> dict[str, Any]:
    """Un effet attendu : renvoie la taille d'effet standardisée et sa description."""
    spec = DESIGNS[design]
    if not isinstance(raw, dict):
        raise ValidationError("Effet attendu invalide.")
    if spec["effect"] == "d":
        if "diff" in raw or "sd" in raw:
            diff = _number(raw.get("diff"), "Différence attendue", -1e12, 1e12)
            sd = _number(raw.get("sd"), "Écart-type", 0, 1e12, open_lo=True)
            d = diff / sd
            text = f"différence {_g(diff, 3)}, écart-type {_g(sd, 3)} (d = {_g(abs(d), 3)})"
            inputs = {"diff": diff, "sd": sd}
        else:
            d = _number(raw.get("d"), spec["effect_label"].split(" (")[0], -10, 10)
            text = f"d = {_g(abs(d), 3)}"
            inputs = {"d": d}
        size = abs(d)
    elif spec["effect"] == "h":
        if "p1" in raw or "p2" in raw:
            p1 = _number(raw.get("p1"), "Proportion attendue dans le groupe 1", 0, 1, open_lo=True, open_hi=True)
            p2 = _number(raw.get("p2"), "Proportion attendue dans le groupe 2", 0, 1, open_lo=True, open_hi=True)
            h = cohen_h(p1, p2)
            text = f"p₁ = {_g(p1, 3)}, p₂ = {_g(p2, 3)} (h = {_g(abs(h), 3)})"
            inputs = {"p1": p1, "p2": p2}
        else:
            h = _number(raw.get("h"), "h de Cohen", -math.pi, math.pi)
            text = f"h = {_g(abs(h), 3)}"
            inputs = {"h": h}
        size = abs(h)
    elif spec["effect"] == "w":
        size = _number(raw.get("w"), "w de Cohen", 0, 10)
        text, inputs = f"w = {_g(size, 3)}", {"w": size}
    else:
        r = _number(raw.get("r"), "Corrélation attendue", -1, 1, open_lo=True, open_hi=True)
        size = abs(r)
        text, inputs = f"r = {_g(size, 3)}", {"r": r}
    if size == 0:
        raise ValidationError("Un effet attendu nul ne peut pas être détecté : indiquez un effet différent de 0.")
    return {"size": size, "text": text, "inputs": inputs}


def clean_request(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError("Demande de calcul invalide.")
    design = raw.get("design")
    if design not in DESIGNS:
        raise ValidationError("Choisissez le type de test.")
    spec = DESIGNS[design]
    mode = raw.get("mode")
    if mode not in MODES:
        raise ValidationError("Choisissez ce que vous voulez calculer.")
    alpha = _number(raw.get("alpha", 0.05), "Seuil α", *ALPHA_RANGE)
    sides = raw.get("alternative", "two-sided") if spec["sided"] else "two-sided"
    if sides not in SIDES:
        raise ValidationError("Hypothèse alternative inconnue.")
    out: dict[str, Any] = {"design": design, "mode": mode, "alpha": alpha, "alternative": sides}
    if mode in ("sample_size", "effect"):
        out["power"] = _number(raw.get("power", 0.8), "Puissance visée", *POWER_RANGE)
    if mode in ("sample_size", "power"):
        effects = raw.get("effects")
        if not isinstance(effects, list) or not effects:
            raise ValidationError("Indiquez au moins un effet attendu.")
        if len(effects) > MAX_EFFECTS:
            raise ValidationError(f"Au plus {MAX_EFFECTS} effets à comparer.")
        out["effects"] = [_effect(design, e, sides)["inputs"] for e in effects]
    if design == "chi2":
        if raw.get("rows") is not None or raw.get("cols") is not None:
            rows = _int(raw.get("rows"), "Nombre de lignes", 2, 50)
            cols = _int(raw.get("cols"), "Nombre de colonnes", 1, 50)
            out.update(rows=rows, cols=cols, df=(rows - 1) * max(cols - 1, 1))
        else:
            out["df"] = _int(raw.get("df"), "Degrés de liberté", 1, 2500)
    if mode == "sample_size":
        if spec["groups"] == 2:
            out["ratio"] = _number(raw.get("ratio", 1), "Rapport des effectifs n₂ / n₁", 0.1, 10)
        out["attrition"] = _number(raw.get("attrition", 0), "Perte prévue (abandons, réponses inexploitables)",
                                   0, 0.9)
    else:
        n_min = spec["n_min"]
        if spec["groups"] == 2:
            out["n1"] = _int(raw.get("n1"), "Effectif du groupe 1", n_min, N_MAX)
            out["n2"] = _int(raw.get("n2"), "Effectif du groupe 2", n_min, N_MAX)
        else:
            out["n"] = _int(raw.get("n"), "Effectif", n_min if design != "chi2" else 2, N_MAX)
    if mode == "effect" and design == "prop_two" and raw.get("p_ref") is not None:
        out["p_ref"] = _number(raw.get("p_ref"), "Proportion de référence (groupe 2)", 0, 1, open_lo=True,
                               open_hi=True)
    out["effect_source"] = _text(raw.get("effect_source"), "Origine de l'effet attendu")
    source = raw.get("source_analysis")
    if source is not None and (isinstance(source, bool) or not isinstance(source, int) or source < 1):
        raise ValidationError("Analyse de référence invalide.")
    out["source_analysis"] = source
    return out


# ---------------------------------------------------------------------- calcul
def _power_fn(req: dict[str, Any]) -> Callable[[float, float, float | None], float]:
    """Fonction (effet, n1, n2) → puissance pour le plan demandé."""
    design, alpha, sides = req["design"], req["alpha"], req["alternative"]
    if design == "t_two":
        return lambda e, n1, n2: power_t(e, n1, n2, alpha, sides)
    if design in ("t_paired", "t_one"):
        return lambda e, n1, n2: power_t(e, n1, None, alpha, sides)
    if design == "prop_two":
        return lambda e, n1, n2: power_prop(e, n1, n2, alpha, sides)
    if design == "chi2":
        return lambda e, n1, n2: power_chi2(e, n1, req["df"], alpha)
    return lambda e, n1, n2: power_r(e, n1, alpha, sides)


def _sizes(req: dict[str, Any], n1: int) -> tuple[int, int | None]:
    if DESIGNS[req["design"]]["groups"] == 2:
        return n1, max(DESIGNS[req["design"]]["n_min"], math.ceil(req.get("ratio", 1) * n1 - 1e-9))
    return n1, None


def required_n(req: dict[str, Any], size: float) -> int:
    """Plus petit effectif (du groupe 1) atteignant la puissance visée : recherche exacte sur les entiers."""
    f = _power_fn(req)
    target = req["power"]
    lo = DESIGNS[req["design"]]["n_min"]
    if req["design"] == "chi2":
        lo = 2

    def ok(n: int) -> bool:
        return f(size, *_sizes(req, n)) >= target

    if ok(lo):
        return lo
    hi = lo
    while not ok(hi):
        if hi >= N_MAX:
            raise ValidationError("Effet trop faible : il faudrait plus de 10 millions d'observations pour le "
                                  "détecter avec cette puissance.")
        hi = min(N_MAX, hi * 2)
    lo_bad = hi // 2 if hi > lo else lo
    while hi - lo_bad > 1:
        mid = (hi + lo_bad) // 2
        if ok(mid):
            hi = mid
        else:
            lo_bad = mid
    return hi


def min_effect(req: dict[str, Any]) -> float:
    f = _power_fn(req)
    n1, n2 = (req["n1"], req["n2"]) if "n1" in req else (req["n"], None)
    cap = {"d": 50.0, "h": math.pi, "w": 50.0, "r": 1 - 1e-12}[DESIGNS[req["design"]]["effect"]]
    target = req["power"]

    def g(e: float) -> float:
        v = f(e, n1, n2)
        return 1.0 if math.isnan(v) else v  # loi non centrale hors de portée numérique : puissance ≈ 1

    lo, hi = 1e-12, min(cap, 0.05)
    while g(hi) < target:
        if hi >= cap:
            raise ValidationError("Avec cet effectif, aucune taille d'effet n'atteint la puissance visée.")
        lo, hi = hi, min(cap, hi * 2)
    return float(optimize.brentq(lambda e: g(e) - target, lo, hi, xtol=1e-14, rtol=1e-13, maxiter=500))


def _p2_for(h: float, p_ref: float) -> tuple[float | None, float | None]:
    """Proportions du groupe 1 qui s'écartent de h de la proportion de référence (au-dessus, au-dessous)."""
    base = 2 * math.asin(math.sqrt(p_ref))
    up, down = base + h, base - h
    hi = math.sin(up / 2) ** 2 if up <= math.pi else None
    lo = math.sin(down / 2) ** 2 if down >= 0 else None
    return hi, lo


def compute(raw: Any) -> dict[str, Any]:
    req = clean_request(raw)
    design, mode = req["design"], req["mode"]
    spec = DESIGNS[design]
    f = _power_fn(req)
    two = spec["groups"] == 2
    alpha_s, sides_s = _g(req["alpha"], 4), SIDES[req["alternative"]]
    summary: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    interpretation: list[str] = []
    diagnostics: list[dict[str, Any]] = []
    rows_out: list[dict[str, Any]] = []
    values: dict[str, Any] = {}
    df_s = f", {req['df']} degré(s) de liberté" if design == "chi2" else ""
    test_s = f"test {sides_s}" if spec["sided"] else "test du khi-deux"

    if mode in ("sample_size", "power"):
        effects = [_effect(design, e, req["alternative"]) for e in req["effects"]]
        for i, e in enumerate(effects):
            row: dict[str, Any] = {"effect": e["size"], "effect_text": e["text"], "inputs": e["inputs"]}
            if mode == "sample_size":
                n1 = required_n(req, e["size"])
                n1, n2 = _sizes(req, n1)
                total = n1 + (n2 or 0)
                achieved = f(e["size"], n1, n2)
                att = req["attrition"]
                recruit1 = math.ceil(n1 / (1 - att) - 1e-9)
                recruit2 = math.ceil(n2 / (1 - att) - 1e-9) if n2 is not None else None
                row.update(n1=n1, n2=n2, n_total=total, power=achieved,
                           recruit1=recruit1, recruit2=recruit2, recruit_total=recruit1 + (recruit2 or 0))
                if design in ("t_two", "t_paired"):
                    row["n_nonparametric"] = [math.ceil(n1 / ARE_NORMAL - 1e-9),
                                              math.ceil(n2 / ARE_NORMAL - 1e-9) if n2 is not None else None]
                    row["n_nonparametric_any"] = [math.ceil(n1 / ARE_MIN - 1e-9),
                                                  math.ceil(n2 / ARE_MIN - 1e-9) if n2 is not None else None]
                sizes = (f"{n1} {spec['unit']}" if not two else
                         (f"{n1} par groupe ({total} au total)" if n1 == n2 else
                          f"{n1} dans le groupe 1 et {n2} dans le groupe 2 ({total} au total)"))
                interpretation.append(
                    f"Pour détecter un effet {e['text']} avec α = {alpha_s} ({test_s}{df_s}) et une puissance d'au "
                    f"moins {fr_pct(req['power'])}, il faut {sizes} ; la puissance atteinte avec ces effectifs est de "
                    f"{fr_pct_1(achieved)}.")
                if att > 0:
                    interpretation.append(
                        f"En prévoyant {fr_pct(att)} de pertes, recrutez {row['recruit_total']} participant(s)"
                        + (f" ({recruit1} et {recruit2})." if two else "."))
            else:
                n1, n2 = (req["n1"], req["n2"]) if two else (req["n"], None)
                achieved = f(e["size"], n1, n2)
                row.update(n1=n1, n2=n2, n_total=n1 + (n2 or 0), power=achieved)
                interpretation.append(
                    f"Avec {n1 + (n2 or 0)} observation(s){f' ({n1} et {n2})' if two else ''}, α = {alpha_s} "
                    f"({test_s}{df_s}), la probabilité de détecter un effet {e['text']}, s'il existe réellement, est "
                    f"de {fr_pct_1(achieved)}.")
                if achieved < 0.8:
                    diagnostics.append({"level": "important",
                                        "title": f"Puissance inférieure à 80 % pour {e['text']}",
                                        "detail": "Un résultat non significatif ne permettrait pas de conclure à "
                                                  "l'absence d'effet de cette taille."})
            rows_out.append(row)
            values[f"row{i}"] = {k: v for k, v in row.items() if k not in ("effect_text", "inputs")}
        cols = ["Effet attendu"]
        kinds = ["text"]
        if mode == "sample_size":
            cols += (["n₁", "n₂", "Total"] if two else ["Effectif"]) + ["Puissance atteinte"]
            kinds += (["int", "int", "int"] if two else ["int"]) + ["pct"]
            if req["attrition"] > 0:
                cols.append(f"À recruter ({fr_pct(req['attrition'])} de pertes)")
                kinds.append("int")
        else:
            cols += (["n₁", "n₂"] if two else ["Effectif"]) + ["Puissance"]
            kinds += (["int", "int"] if two else ["int"]) + ["pct"]
        rows_t = []
        for r in rows_out:
            line: list[Any] = [r["effect_text"], r["n1"]] + ([r["n2"], r["n_total"]] if two and mode == "sample_size"
                                                            else [r["n2"]] if two else [])
            line.append(r["power"])
            if mode == "sample_size" and req["attrition"] > 0:
                line.append(r["recruit_total"])
            rows_t.append(line)
        tables.append({"title": "Résultats par effet attendu", "columns": cols, "rows": rows_t,
                       "note": "Effectifs arrondis à l'entier supérieur ; la puissance atteinte est recalculée avec "
                               "ces effectifs entiers." if mode == "sample_size" else "", "kinds": kinds})
        if mode == "sample_size" and design in ("t_two", "t_paired"):
            np_rows = [[r["effect_text"], _pair(r["n_nonparametric"]), _pair(r["n_nonparametric_any"])]
                       for r in rows_out]
            label = "Mann-Whitney" if design == "t_two" else "Wilcoxon"
            tables.append({"title": f"Si vous prévoyez le test de {label}",
                           "columns": ["Effet attendu", "Données normales (ERA 3/π ≈ 0,955)",
                                       "Toute distribution (ERA ≥ 0,864)"],
                           "rows": np_rows, "kinds": ["text", "text", "text"],
                           "note": "Approximation par l'efficacité relative asymptotique (ERA) du test de rangs par "
                                   "rapport au test t (Lehmann, 1975). Effectifs " + spec["unit"] + "."})
        first = rows_out[0]
        if mode == "sample_size":
            summary.append({"key": "n_total", "label": "Effectif total nécessaire" if two else "Effectif nécessaire",
                            "value": first["n_total"], "kind": "int", "digits": 0})
        summary.append({"key": "power", "label": "Puissance atteinte" if mode == "sample_size" else "Puissance",
                        "value": first["power"], "kind": "pct", "digits": 1})
    else:
        size = min_effect(req)
        n1, n2 = (req["n1"], req["n2"]) if two else (req["n"], None)
        row = {"effect": size, "n1": n1, "n2": n2, "n_total": n1 + (n2 or 0), "power": req["power"]}
        rows_out.append(row)
        values["row0"] = dict(row)
        name = spec["effect"]
        text = f"{name} = {_g(size)}"
        extra = ""
        if design == "prop_two" and "p_ref" in req:
            hi, lo = _p2_for(size, req["p_ref"])
            row.update(p_ref=req["p_ref"], p_high=hi, p_low=lo)
            values["row0"].update(p_high=hi, p_low=lo)
            parts = [_g(x) for x in (lo, hi) if x is not None]
            extra = (f" : avec une proportion de référence de {_g(req['p_ref'])}, cela correspond à une proportion "
                     f"de {' ou '.join(parts)} dans l'autre groupe")
        interpretation.append(
            f"Avec {row['n_total']} observation(s){f' ({n1} et {n2})' if two else ''}, α = {alpha_s} ({test_s}{df_s}) "
            f"et une puissance de {fr_pct(req['power'])}, le plus petit effet détectable est {text}{extra}.")
        summary.append({"key": "effect", "label": f"Plus petit effet détectable ({spec['effect_label'].split(' (')[0]})",
                        "value": size, "kind": "effect", "digits": 3})
        tables.append({"title": "Plus petit effet détectable",
                       "columns": ["Effectif"] + (["n₁", "n₂"] if two else []) + ["Puissance visée", spec["effect"]],
                       "rows": [[row["n_total"]] + ([n1, n2] if two else []) + [req["power"], size]],
                       "kinds": ["int"] + (["int", "int"] if two else []) + ["pct", "value"], "note": ""})

    benchmarks = spec["benchmarks"]
    interpretation.append(
        f"Repères de Cohen (1988) pour {spec['effect']} : {fr(benchmarks[0], 1)} petit, {fr(benchmarks[1], 1)} moyen, "
        f"{fr(benchmarks[2], 1)} grand. Ils ne remplacent pas un effet tiré de la littérature ou d'une étude pilote.")
    if not req["effect_source"] and mode != "effect":
        diagnostics.append({"level": "methodologique", "title": "Origine de l'effet attendu non précisée",
                            "detail": "Indiquez d'où vient l'effet supposé (étude antérieure, étude pilote, plus "
                                      "petit effet d'intérêt pratique) : le résultat en dépend entièrement."})
    if mode == "power" and req["source_analysis"] is not None:
        diagnostics.append({"level": "information", "title": "Puissance après la collecte",
                            "detail": "La puissance est calculée pour l'effet que vous supposez, avec les effectifs "
                                      "obtenus. STATPFE ne calcule pas de « puissance observée » à partir de l'effet "
                                      "mesuré : elle se déduit de la valeur p et n'apporte aucune information de "
                                      "plus."})
    if design == "chi2" and mode != "effect":
        for r in rows_out:
            if r.get("n_total", 0) < 5 * req["df"] + 5:
                diagnostics.append({"level": "important", "title": "Effectif faible pour un khi-deux",
                                    "detail": "Avec si peu d'observations, des effectifs théoriques inférieurs à 5 "
                                              "sont probables : le khi-deux et ce calcul deviennent approximatifs."})
                break
    if design == "prop_two":
        diagnostics.append({"level": "information", "title": "Approximation normale",
                            "detail": "Le calcul repose sur une approximation normale ; avec de petits effectifs, "
                                      "le test exact de Fisher est un peu moins puissant que l'estimation."})

    assumptions = [f"Seuil de signification α = {alpha_s}, {test_s}."] + (
        [f"Puissance visée : {fr_pct(req['power'])}."] if "power" in req else []) + ASSUMPTIONS[design]
    if design == "chi2":
        assumptions.insert(1, f"Degrés de liberté : {req['df']}"
                              + (f" (tableau {req['rows']} × {req['cols']})." if "rows" in req else "."))
    if mode == "sample_size" and two and req["ratio"] != 1:
        assumptions.append(f"Effectifs déséquilibrés : n₂ = {_g(req['ratio'], 2)} × n₁.")
    if mode == "sample_size" and req["attrition"] > 0:
        assumptions.append(f"Pertes prévues : {fr_pct(req['attrition'])} (effectif à recruter = effectif nécessaire "
                           f"/ (1 − pertes)).")
    if req["effect_source"]:
        assumptions.append(f"Origine de l'effet attendu : {req['effect_source']}")

    charts = [_curve(req, rows_out, f)]
    title = f"{MODES[mode]} : {spec['label'][0].lower()}{spec['label'][1:]}"
    return _finite({
        "request": req, "design": design, "design_label": spec["label"], "mode": mode, "mode_label": MODES[mode],
        "title": title, "summary": summary, "tables": tables, "charts": charts, "diagnostics": diagnostics,
        "interpretation": interpretation, "assumptions": assumptions, "rows": rows_out, "values": values,
        "effect_label": spec["effect_label"], "unit": spec["unit"],
        "method_note": "Calcul exact par la loi non centrale (Student ou khi-deux) ou approximation normale (arc sinus, "
                       "Fisher), selon Cohen (1988).",
        "r_equivalent": spec["r_equivalent"],
        "disclaimer": "Estimation qui dépend entièrement des hypothèses ci-dessus (effet attendu, seuil, conditions "
                      "du test). Elle ne garantit pas la validité scientifique de l'étude.",
    })


def fr_pct_1(x: float) -> str:
    """Pourcentage à une décimale (même arrondi que les tableaux), espace insécable avant « % »."""
    return f"{fr(x * 100, 1)}\u00a0%"


def _pair(v: list[int | None]) -> str:
    return str(v[0]) if v[1] is None else (f"{v[0]} par groupe" if v[0] == v[1] else f"{v[0]} et {v[1]}")


def _curve(req: dict[str, Any], rows: list[dict[str, Any]], f) -> dict[str, Any]:
    """Courbe de puissance calculée par le moteur (l'interface ne fait que la dessiner)."""
    spec = DESIGNS[req["design"]]
    two = spec["groups"] == 2
    if req["mode"] == "effect":
        n1, n2 = rows[0]["n1"], rows[0]["n2"]
        top = min({"d": 50.0, "h": math.pi, "w": 50.0, "r": 0.999}[spec["effect"]], rows[0]["effect"] * 2.2)
        xs = [top * i / 40 for i in range(1, 41)]
        series = [{"label": f"n = {rows[0]['n_total']}", "points": [[x, f(x, n1, n2)] for x in xs]}]
        return {"type": "power_curve", "title": "Puissance selon la taille de l'effet",
                "data": {"x_label": spec["effect_label"].split(" (")[0], "series": series, "target": req["power"],
                         "marker": rows[0]["effect"]}}
    n_min = spec["n_min"] if req["design"] != "chi2" else 2
    ref = max(r["n1"] for r in rows)
    top = max(n_min + 10, math.ceil(ref * (1.6 if req["mode"] == "sample_size" else 2)))
    step = max(1, (top - n_min) // 60)
    ns = list(range(n_min, top + 1, step))
    equal = req.get("ratio", 1) == 1 if req["mode"] == "sample_size" else all(r["n1"] == r["n2"] for r in rows)
    series = []
    for r in rows:
        pts = []
        for n in ns:
            a, b = (n, (math.ceil(req.get("ratio", 1) * n - 1e-9) if req["mode"] == "sample_size"
                        else max(n_min, round(n * r["n2"] / r["n1"])))) if two else (n, None)
            pts.append([n, f(r["effect"], a, max(b, n_min) if b is not None else None)])
        series.append({"label": r["effect_text"], "points": pts})
    return {"type": "power_curve", "title": "Puissance selon l'effectif",
            "data": {"x_label": ("Effectif par groupe" if equal else "Effectif du groupe 1") if two else "Effectif",
                     "series": series,
                     "target": req.get("power", 0.8), "marker": rows[0]["n1"] if len(rows) == 1 else None}}


def catalog() -> dict[str, Any]:
    return {
        "designs": [{"key": k, "label": v["label"], "effect": v["effect"], "effect_label": v["effect_label"],
                     "groups": v["groups"], "sided": v["sided"], "benchmarks": v["benchmarks"], "unit": v["unit"],
                     "n_min": v["n_min"], "methods": v["methods"], "assumptions": ASSUMPTIONS[k],
                     "r_equivalent": v["r_equivalent"]} for k, v in DESIGNS.items()],
        "modes": [{"key": k, "label": v} for k, v in MODES.items()],
        "alternatives": [{"key": k, "label": v} for k, v in SIDES.items()],
        "max_effects": MAX_EFFECTS, "alpha_range": list(ALPHA_RANGE), "power_range": list(POWER_RANGE),
    }


def from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """Pré-remplit un calcul de puissance après la collecte avec les effectifs d'une analyse enregistrée."""
    method = analysis["method"]
    design = METHOD_TO_DESIGN.get(method)
    if design is None:
        raise ValidationError("Cette analyse ne correspond à aucun calcul de puissance disponible.")
    values = analysis["result"].get("values", {})
    params = analysis.get("params", {})
    req: dict[str, Any] = {"design": design, "mode": "power", "source_analysis": analysis["id"],
                           "alpha": round(1 - float(params.get("conf_level", 0.95)), 10)}
    alt = params.get("alternative", "two-sided")
    if DESIGNS[design]["sided"]:
        req["alternative"] = "two-sided" if alt == "two-sided" else "one-sided"
    if DESIGNS[design]["groups"] == 2:
        req.update(n1=int(values["n1"]), n2=int(values["n2"]))
    else:
        n = analysis["result"].get("n_used") or values.get("n")
        req["n"] = int(n)
    if design == "chi2":
        exp = values.get("expected")
        if isinstance(exp, list) and exp:
            req.update(rows=len(exp), cols=len(exp[0]))
        elif "odds_ratio" in values:
            req.update(rows=2, cols=2)
    return {"request": req, "analysis_id": analysis["id"], "analysis_title": analysis["title"],
            "design_label": DESIGNS[design]["label"]}
