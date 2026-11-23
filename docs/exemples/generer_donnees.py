import numpy as np, pandas as pd, sys
out = sys.argv[1]
rng = np.random.default_rng(2026)
n = 150
sexe = rng.choice(["Femme", "Homme"], n, p=[0.55, 0.45])
niveau = rng.choice(["Licence", "Master", "Doctorat"], n, p=[0.45, 0.40, 0.15])
age = np.where(niveau == "Licence", rng.integers(19, 24, n), np.where(niveau == "Master", rng.integers(22, 28, n), rng.integers(25, 36, n)))
filiere = rng.choice(["Sciences", "Économie", "Lettres", "Médecine"], n, p=[0.3, 0.3, 0.2, 0.2])
programme = rng.choice(["Oui", "Non"], n)  # a suivi le programme de gestion du stress
sommeil = np.clip(rng.normal(6.8, 1.0, n), 4, 9.5).round(1)
stress_avant = np.clip(rng.normal(24, 6, n) - 1.5 * (sommeil - 6.8), 5, 40).round(0)
baisse = np.where(programme == "Oui", rng.normal(5, 3.5, n), rng.normal(0.8, 3, n))
stress_apres = np.clip(stress_avant - baisse, 0, 40).round(0)
note = np.clip(rng.normal(12.5, 2.2, n) + 0.45 * (sommeil - 6.8) - 0.08 * (stress_avant - 24), 4, 19.5).round(2)
satisf_p = np.where(programme == "Oui", None, None)
satisfaction = np.array([rng.choice([1,2,3,4,5], p=[.05,.10,.25,.35,.25] if p == "Oui" else [.15,.25,.30,.20,.10]) for p in programme])
tabac = np.where(rng.random(n) < np.where(sexe == "Homme", 0.28, 0.12), "Oui", "Non")
abandon = np.where(rng.random(n) < np.where(stress_avant > 30, 0.25, 0.04), "Oui", "Non")
df = pd.DataFrame({
    "id": [f"E{i:03d}" for i in range(1, n + 1)], "sexe": sexe, "age": age, "niveau": niveau, "filiere": filiere,
    "heures_sommeil": sommeil, "programme": programme, "stress_avant": stress_avant.astype(float),
    "stress_apres": stress_apres.astype(float), "note_moyenne": note, "satisfaction": satisfaction,
    "tabac": tabac, "abandon": abandon,
})
# Défauts volontaires, pour tester le contrôle qualité et le nettoyage
df["sexe"] = df["sexe"].astype(object)
df.loc[[7, 41, 88], "sexe"] = ["F", "H", "femme"]          # saisies incohérentes -> recodage
for col, rows in {"note_moyenne": [12, 57, 103], "heures_sommeil": [30, 66], "stress_apres": [19, 120, 140], "satisfaction": [75]}.items():
    df[col] = df[col].astype(object); df.loc[rows, col] = None
df["age"] = df["age"].astype(object); df.loc[95, "age"] = 99   # valeur aberrante (erreur de saisie)
df = pd.concat([df, df.iloc[[24, 61]]], ignore_index=True)     # 2 doublons exacts
dico = pd.DataFrame([
    ("id", "Identifiant anonyme de l'étudiant", "Texte", "E001 à E150"),
    ("sexe", "Sexe déclaré", "Qualitative nominale", "Femme, Homme (+ 3 saisies à recoder : F, H, femme)"),
    ("age", "Âge en années", "Quantitative", "19 à 35 (+ 1 valeur aberrante : 99)"),
    ("niveau", "Niveau d'études", "Qualitative ordinale", "Licence < Master < Doctorat"),
    ("filiere", "Filière", "Qualitative nominale", "Sciences, Économie, Lettres, Médecine"),
    ("heures_sommeil", "Heures de sommeil par nuit (moyenne déclarée)", "Quantitative", "4 à 9,5 (2 manquantes)"),
    ("programme", "A suivi le programme de gestion du stress (8 semaines)", "Qualitative nominale", "Oui, Non"),
    ("stress_avant", "Score de stress perçu avant le programme (PSS, 0-40)", "Quantitative", "0 à 40"),
    ("stress_apres", "Score de stress perçu après 8 semaines (PSS, 0-40)", "Quantitative", "0 à 40 (3 manquantes)"),
    ("note_moyenne", "Moyenne générale du semestre (/20)", "Quantitative", "0 à 20 (3 manquantes)"),
    ("satisfaction", "Satisfaction vis-à-vis de la formation", "Qualitative ordinale (Likert)", "1 = pas du tout … 5 = tout à fait (1 manquante)"),
    ("tabac", "Fumeur", "Qualitative nominale", "Oui, Non"),
    ("abandon", "A envisagé d'abandonner ses études ce semestre", "Qualitative nominale", "Oui, Non"),
], columns=["Variable", "Description", "Type", "Valeurs"])
with pd.ExcelWriter(f"{out}/etude_stress_etudiants.xlsx") as w:
    df.to_excel(w, sheet_name="Données", index=False)
    dico.to_excel(w, sheet_name="Dictionnaire", index=False)
df.to_csv(f"{out}/etude_stress_etudiants.csv", sep=";", decimal=",", index=False, encoding="utf-8-sig")
print(df.shape)
