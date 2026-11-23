# Jeu de données de test : stress et réussite des étudiants

**Données entièrement fictives** (générées par simulation), pour essayer STATPFE de bout en bout.
Elles ne décrivent aucune population réelle.

- `etude_stress_etudiants.xlsx` : feuille **Données** (152 lignes, 13 variables) et feuille **Dictionnaire**
  (description de chaque variable). STATPFE lit la première feuille.
- `etude_stress_etudiants.csv` : les mêmes données au format CSV français (séparateur `;`, virgule décimale).

**Étude imaginaire.** 150 étudiants (Licence, Master, Doctorat) ; une partie a suivi un programme de gestion
du stress de 8 semaines. On mesure le stress perçu (score PSS de 0 à 40) avant et après, la moyenne du semestre,
le sommeil, la satisfaction (échelle de Likert 1 à 5), le tabac et l'envie d'abandonner.

## Texte de l'étude à saisir (écran « Étude »)

- **Titre** : Effet d'un programme de gestion du stress sur le stress perçu et la réussite des étudiants universitaires
- **Problématique** : Le stress perçu est élevé chez les étudiants et peut nuire à leur sommeil, à leurs résultats et à leur persévérance. Un programme de gestion du stress de 8 semaines réduit-il le stress perçu des étudiants qui le suivent, et le niveau de stress est-il lié à la réussite académique ?
- **Objectifs** : (1) mesurer l'évolution du stress perçu avant et après le programme ; (2) comparer le stress et la satisfaction des participants et des non-participants ; (3) étudier le lien entre stress, sommeil et moyenne du semestre ; (4) décrire les facteurs associés au tabac et à l'envie d'abandonner.
- **Population** : étudiants inscrits en Licence, Master et Doctorat, toutes filières.
- **Méthode d'échantillonnage** : échantillonnage de convenance (questionnaire diffusé aux étudiants volontaires).
- **Taille d'échantillon prévue** : 150
- **Hypothèses** :
  - H1 : le stress perçu diminue entre le début et la fin du programme (test t apparié).
  - H2 : les participants au programme ont un stress initial différent des non-participants (test t).
  - H3 : la satisfaction est plus élevée chez les participants (Mann-Whitney).
  - H4 : plus le stress est élevé, plus la moyenne du semestre est basse (Spearman).
  - H5 : la moyenne du semestre diffère selon le sexe (test t de Welch).
  - H6 : le tabagisme est associé au sexe (khi-deux).

## Défauts placés volontairement (pour tester le contrôle qualité)

| Défaut | Où | Ce que STATPFE doit signaler |
|---|---|---|
| 2 lignes en double | E025 et E062 répétées en fin de fichier | Qualité : 2 doublons |
| Saisies incohérentes | `sexe` contient « F », « H », « femme » en plus de « Femme » / « Homme » | 5 modalités au lieu de 2 |
| Valeur aberrante | `age` = 99 pour E096 | Maximum 99 dans les descriptives |
| Valeurs manquantes | `note_moyenne` (3), `heures_sommeil` (2), `stress_apres` (3), `satisfaction` (1) | Taux de manquants par variable |

## Parcours de test conseillé

1. **Nouveau projet**, remplir l'étude (titre, problématique, hypothèses, par exemple
   « Le programme réduit le stress perçu »).
2. **Importer** `etude_stress_etudiants.xlsx`. Vérifier : 152 lignes, 13 variables, feuille « Données » lue.
3. **Qualité** : 2 doublons, 143 lignes complètes, `sexe` à 5 modalités.
4. Essayer un **test t de Welch** de `note_moyenne` selon `sexe` sur les données d'origine : STATPFE doit
   **refuser** (5 modalités) et demander de choisir deux groupes. C'est voulu.
5. **Créer une version nettoyée** (l'original reste intact) avec trois étapes :
   - supprimer les doublons ;
   - recoder `sexe` en `sexe_propre` (F → Femme, H → Homme, femme → Femme) ;
   - garder les lignes où `age` est inférieur à 60.
   Résultat attendu : **149 lignes**, 0 doublon, 140 lignes complètes.
6. Lancer les analyses ci-dessous sur la version nettoyée, puis l'**assistant de choix de test**,
   le **calcul de puissance**, le **plan d'analyse**, le **rapport Word et PDF** et l'**IA** (interprétation).

## Résultats attendus (version nettoyée, 149 lignes)

Ces valeurs ont été obtenues en lançant réellement le moteur STATPFE 0.1.0 sur ce fichier.
Si vous obtenez autre chose, c'est un problème à signaler.

| Analyse | Variables | Résultat attendu |
|---|---|---|
| Statistiques descriptives | `age` | n = 149, moyenne 23,86 (ET 3,72), de 19 à 34 |
| | `stress_avant` / `stress_apres` | moyennes 23,62 (n = 149) et 21,08 (n = 146) |
| | `note_moyenne` | n = 146, moyenne 12,16 (ET 2,38) |
| Fréquences | `niveau` | Licence la plus fréquente : 65 (43,6 %) |
| Test t de Welch | `note_moyenne` selon `sexe_propre` | t(141,94) = 0,16, p = 0,876 : **non significatif**, d = 0,03 |
| Test t de Student | `stress_avant` selon `programme` | t(147) = 2,14, p = 0,034, d = 0,35 |
| Mann-Whitney | `satisfaction` selon `programme` | W = 1 967,5, p = 0,003 |
| Test t apparié | `stress_avant` − `stress_apres` | différence 2,45 [1,86 ; 3,03], t(145) = 8,26, p < 0,001, dz = 0,68 |
| Wilcoxon apparié | `stress_avant`, `stress_apres` | V = 7 521,0, p < 0,001 |
| Pearson | `heures_sommeil`, `note_moyenne` | r = 0,12, p = 0,141 : **non significatif** |
| Spearman | `stress_avant`, `note_moyenne` | rho = −0,18, p = 0,028 |
| Khi-deux | `sexe_propre` × `tabac` | χ²(1) = 13,41, p < 0,001, V de Cramér = 0,32 |
| Test exact de Fisher | `programme` × `abandon` | p = 0,548 : **non significatif** |

Les résultats non significatifs sont voulus : ils permettent de vérifier que STATPFE et l'IA
ne concluent pas à un effet qui n'existe pas.

Remarque : l'ANOVA (comparer `note_moyenne` entre les trois niveaux) n'est pas encore disponible
dans cette version ; STATPFE le dit au lieu de proposer un test inadapté.
