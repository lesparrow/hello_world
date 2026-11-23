"""Génère les jeux de données de référence (exécuté une fois ; les CSV sont versionnés).

Usage : python tests/reference/make_datasets.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "data"


def main() -> None:
    rng = np.random.default_rng(20261122)
    OUT.mkdir(exist_ok=True)

    # Deux groupes indépendants, valeurs continues (sans ex aequo), groupes déséquilibrés, une valeur manquante
    n1, n2 = 14, 23
    y = np.concatenate([rng.normal(12.0, 2.0, n1), rng.normal(13.4, 3.1, n2)]).round(4)
    g = ["A"] * n1 + ["B"] * n2
    df = pd.DataFrame({"y": y, "g": g})
    df.loc[5, "y"] = np.nan
    df.to_csv(OUT / "groups.csv", index=False)

    # Deux groupes, échelle de Likert (nombreux ex aequo), groupes de plus de 50
    ga = rng.choice([1, 2, 3, 4, 5], size=55, p=[0.1, 0.2, 0.3, 0.25, 0.15])
    gb = rng.choice([1, 2, 3, 4, 5], size=60, p=[0.2, 0.25, 0.3, 0.15, 0.1])
    pd.DataFrame({"score": np.concatenate([ga, gb]), "g": ["F"] * 55 + ["H"] * 60}).to_csv(
        OUT / "groups_ties.csv", index=False)

    # Très petits groupes
    pd.DataFrame({"y": [3.1, 4.7, 2.2, 5.9, 4.0, 6.3, 7.1, 5.5, 8.2, 6.8, 7.7],
                  "g": ["T"] * 5 + ["C"] * 6}).to_csv(OUT / "small.csv", index=False)

    # Mesures appariées continues (sans ex aequo)
    before = rng.normal(50, 8, 25).round(3)
    after = (before + rng.normal(2.5, 4, 25)).round(3)
    pd.DataFrame({"avant": before, "apres": after}).to_csv(OUT / "paired.csv", index=False)

    # Mesures appariées entières (ex aequo et différences nulles)
    b2 = rng.integers(5, 15, 30)
    a2 = b2 + rng.integers(-2, 4, 30)
    pd.DataFrame({"t1": b2, "t2": a2}).to_csv(OUT / "paired_ties.csv", index=False)

    # Corrélations
    x = rng.normal(0, 1, 30)
    yv = 0.5 * x + rng.normal(0, 1, 30)
    pd.DataFrame({"x": x.round(5), "y": yv.round(5)}).to_csv(OUT / "corr.csv", index=False)
    pd.DataFrame({"x": [1.2, 2.5, 2.9, 4.1, 3.3, 6.0, 5.2, 7.4],
                  "y": [2.0, 1.1, 3.6, 3.0, 4.8, 4.1, 6.6, 5.9]}).to_csv(OUT / "corr_small.csv", index=False)
    xi = rng.integers(1, 6, 40)
    yi = np.clip(xi + rng.integers(-2, 3, 40), 1, 5)
    pd.DataFrame({"x": xi, "y": yi}).to_csv(OUT / "corr_ties.csv", index=False)

    # Variables qualitatives
    n = 120
    sexe = rng.choice(["Femme", "Homme"], n)
    fumeur = np.where(rng.random(n) < np.where(sexe == "Homme", 0.38, 0.22), "oui", "non")
    satisf = rng.choice(["Faible", "Moyenne", "Forte"], n, p=[0.3, 0.45, 0.25])
    pd.DataFrame({"sexe": sexe, "fumeur": fumeur, "satisfaction": satisf}).to_csv(OUT / "cat.csv", index=False)
    pd.DataFrame({"traitement": ["A"] * 9 + ["B"] * 8, "guerison": ["oui"] * 7 + ["non"] * 2 + ["oui"] * 2
                  + ["non"] * 6}).to_csv(OUT / "cat_small.csv", index=False)
    pd.DataFrame({"r": ["a"] * 6 + ["b"] * 7 + ["c"] * 5,
                  "c": ["x", "x", "x", "y", "z", "z", "y", "y", "y", "y", "x", "z", "y", "z", "z", "z", "x", "z"]}
                 ).to_csv(OUT / "cat_small_rxc.csv", index=False)

    # Tableau 3 × 3 de taille moyenne (n = 180) pour le test exact de Fisher r × c
    counts = [[20, 30, 25], [15, 18, 12], [10, 8, 22]]
    r, c = [], []
    for i, row in enumerate(counts):
        for j, k in enumerate(row):
            r += [f"r{i + 1}"] * k
            c += [f"c{j + 1}"] * k
    pd.DataFrame({"r": r, "c": c}).to_csv(OUT / "cat_medium.csv", index=False)


if __name__ == "__main__":
    main()
