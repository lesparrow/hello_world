# STATPFE Desktop : Phase 4, statistiques fondamentales

Date : 22 novembre 2026
Statut : **terminée côté code, en attente de validation**.

## 1. Objectif de la phase

Ajouter les statistiques descriptives, les premiers graphiques, les premiers tests statistiques validés et leurs diagnostics, avec des résultats enregistrés dans le projet et reproductibles.

## 2. Ce qui a été observé

Le socle des données de la Phase 3 (versions reproductibles, empreinte de contenu par version, dictionnaire) fournit exactement ce qu'une analyse doit enregistrer. Le moteur n'avait pas de bibliothèque statistique. R 4.3.3 est installable dans l'environnement de développement et sur les machines de CI Ubuntu.

## 3. Décisions et justifications

| Décision | Justification |
|---|---|
| Calculs dans le moteur Python avec numpy et scipy (scipy ≥ 1.15) | Bibliothèques de référence, déjà compatibles avec PyInstaller. Le moteur autonome passe de 57 à 86 Mo. |
| Reproduction du comportement **par défaut de R** pour chaque test (`t.test`, `wilcox.test`, `cor.test`, `chisq.test`, `fisher.test`) | Un étudiant ou un jury qui vérifie avec R obtient les mêmes chiffres. Cela fixe aussi des choix précis : Welch par défaut, correction de Yates en 2 × 2, loi exacte de Mann-Whitney et Wilcoxon sans ex aequo et pour n < 50, approximation d'Edgeworth (AS 89) pour Spearman. |
| Lois exactes de Mann-Whitney, Wilcoxon et Spearman, et test de Fisher r × c, réimplémentées par dénombrement | Les fonctions de scipy ne suivent pas toujours les règles de R (seuils « exact », Fisher r × c par simulation). Le dénombrement donne les mêmes valeurs que R. |
| Validation automatique contre R : 47 cas, 311 valeurs | Exigence du cahier des charges. La CI réinstalle R, recalcule toutes les valeurs de référence et y compare le moteur à chaque modification. |
| Une analyse enregistre : jeu de données, version (et son nom), empreinte SHA-256 des données utilisées, méthode, paramètres, versions de Python, numpy, scipy, pandas et du moteur, date, résultat complet | Reproductibilité exigée au §9 du cahier des charges. Une analyse dont les données ont changé est signalée « à vérifier » ; le bouton « Reproduire » recalcule et compare valeur par valeur. |
| Valeurs manquantes : observations complètes pour les variables de l'analyse ; descriptives sur les valeurs disponibles de chaque variable | Stratégie simple, standard, toujours affichée avec le nombre d'exclusions. |
| Variables « identifiant », « exclue » ou signalées comme identifiant potentiel refusées dans les analyses | Protection des données personnelles : aucun nom ni e-mail ne peut apparaître dans un tableau de fréquences. |
| Interprétation par des règles fixes, avec mises en garde (signification ≠ importance ni causalité ; non significatif ≠ absence d'effet) | Aucune IA : le texte ne fait que reformuler les valeurs calculées. |
| Test de normalité (Shapiro-Wilk) et Levene affichés à titre indicatif seulement | Le cahier des charges interdit de choisir une méthode sur la seule base d'un test de normalité ; la note l'explique à l'utilisateur. |
| Graphiques dessinés en SVG à partir des valeurs calculées par le moteur | Aucune bibliothèque graphique supplémentaire ; les graphiques ne recalculent rien, donc ils ne peuvent pas contredire les tableaux. |
| Format du projet passé à la version 3 (table des analyses), avec migration automatique des formats 1 et 2 | Les projets existants restent ouvrables. |

## 4. Fichiers concernés

```text
engine/statpfe/stats/common.py         Sélection et contrôle des variables, mise en forme, structure des résultats
engine/statpfe/stats/descriptive.py    Descriptives, fréquences, tableaux croisés, histogrammes, boîtes à moustaches
engine/statpfe/stats/tests.py          Tests t, Mann-Whitney, Wilcoxon, Pearson, Spearman, khi-deux, Fisher
engine/statpfe/stats/distributions.py  Lois exactes (pwilcox, psignrank, AS 89) comme dans R
engine/statpfe/stats/catalog.py        Catalogue des méthodes (objectif, conditions, résultats, équivalent R)
engine/statpfe/stats/store.py          Analyses enregistrées, statut, reproduction
engine/statpfe/rpc/server.py           8 nouvelles méthodes analysis.*
engine/tests/reference/                Jeux de référence, script R, valeurs de R
engine/tests/test_reference_r.py       Comparaison à R
engine/tests/test_analyses.py          Cas limites, diagnostics, enregistrement, reproduction
apps/desktop/src/screens/analysis/     Écran Analyses, choix de méthode, résultats
apps/desktop/src/components/charts/    Histogramme, boîte à moustaches, barres, barres empilées, nuage de points
.github/workflows/ci.yml               Job « Validation des statistiques contre R », test d'analyse dans le moteur Windows
```

## 5. Ce qui a réellement été implémenté

**Décrire** : statistiques descriptives (n, manquants, moyenne, écart-type, erreur type, IC de la moyenne, médiane, quartiles, min, max, asymétrie G1, aplatissement G2), éventuellement par groupe, avec histogrammes et boîtes à moustaches ; fréquences et pourcentages (total, valides, cumulés) avec diagramme en barres ; tableaux croisés (effectifs, pourcentages en ligne ou en colonne) avec barres empilées.

**Tests** : t de Welch, t de Student, Mann-Whitney, t apparié, Wilcoxon apparié, corrélations de Pearson et de Spearman, khi-deux d'indépendance, test exact de Fisher (2 × 2 avec rapport de cotes et IC ; r × c jusqu'à 20 cases et 300 observations). Pour chacun, selon le cas : statistique, degrés de liberté, valeur p, intervalle de confiance, taille d'effet (d de Cohen, g de Hedges, dz, corrélation bisériale de rangs, V de Cramér, rapport de cotes, r²), effectifs utilisés, traitement des manquants, hypothèse unilatérale ou bilatérale, niveau de confiance 90, 95 ou 99 %.

**Diagnostics** classés (important, méthodologique, information) : petits groupes, variable constante, valeurs extrêmes (1,5 × EIQ), forte asymétrie, groupes déséquilibrés, variable ordinale traitée par une moyenne, effectifs théoriques faibles (recommande Fisher), différences nulles écartées, ex aequo, normalité et homogénéité des variances à titre indicatif.

**Analyses enregistrées** : liste, titre, note personnelle, suppression, duplication (nouvelle analyse avec les mêmes réglages), statut des données (inchangées, modifiées, version supprimée, version à corriger), reproduction avec comparaison de chaque valeur, journal du projet.

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 180 tests `pytest` (dont 87 nouveaux) | 180 réussis (Linux, Python 3.13) |
| Validation contre R 4.3.3 : 47 cas couvrant toutes les méthodes, hypothèses bilatérales et unilatérales, niveaux 90/95/99 %, petits échantillons, ex aequo, différences nulles, tableaux 2 × 2, 2 × 3, 3 × 3 | 311 valeurs identiques à R à 1e-9 près (relatif). Exceptions documentées : Shapiro-Wilk (1e-5) ; rapport de cotes de Fisher et son IC, que R calcule avec une tolérance d'environ 1e-4 (un test vérifie que la borne calculée par STATPFE satisfait exactement sa définition) |
| Interface : typecheck, 8 tests `vitest`, build | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface, vrai moteur), enquête fictive de 61 réponses : import, test de Welch, khi-deux, descriptives, Spearman, variable « Nom » refusée dans les listes, reproduction (résultats identiques), Ctrl+S, fermeture, réouverture : les 4 analyses sont retrouvées | Réussi, aucune erreur dans la console |
| Moteur autonome PyInstaller sous Linux avec scipy : projet, import, test de Welch, Mann-Whitney | Réussi (86 Mo) |
| CI : moteur sous Ubuntu et Windows, validation R, installateur Windows avec calcul d'un test de Welch par le moteur autonome | Voir le résultat de la CI ci-dessous |

## 7. Limites et points non terminés

- Pas encore de test manuel sur un vrai PC Windows.
- Moteur autonome de 86 Mo (scipy) ; démarrage d'environ 1 à 2 s.
- Pas d'intervalle de confiance pour rho de Spearman ni pour le décalage de Mann-Whitney (estimateur de Hodges-Lehmann), ni d'IC pour le d de Cohen : non calculés plutôt que mal calculés.
- Test exact de Fisher r × c limité à 20 cases et 300 observations ; au-delà, un message propose le khi-deux.
- Les seuils de taille d'effet (Cohen) sont présentés comme des repères indicatifs, sans adaptation au domaine.
- Pas encore d'assistant de choix de méthode (Phase 5) ni d'export des résultats (Phase 6).
- ANOVA, Kruskal-Wallis, régressions et autres méthodes : prévues plus tard ; elles ne sont pas affichées.
- Correction apportée en passant : « 1.234 » était lu comme 1234 (séparateur de milliers) ; il est maintenant lu comme 1,234. Seuls « 1.234,5 » et « 1.234.567 » sont lus avec un séparateur de milliers.

## 8. Vérifications manuelles proposées

1. Sur vos propres données, lancer un test de Welch et comparer avec R ou SPSS.
2. Déclarer un code manquant (ex. 99) après une analyse : vérifier que l'analyse passe « à vérifier » et que « Reproduire » montre l'écart.
3. Essayer une analyse sur une colonne de noms : elle doit être refusée.
4. Enregistrer, fermer, rouvrir : les analyses et leurs notes sont retrouvées.

## 9. Documentation mise à jour

`README.md`, ce document, et le commentaire de `engine/tests/reference/r_reference.R` (régénération des valeurs de référence).

## 10. Phase suivante proposée

**Phase 5 : assistant méthodologique.** Un assistant déterministe qui, à partir de l'objectif, du type des variables, du nombre de groupes, de l'appariement et des diagnostics, recommande une méthode, explique pourquoi, liste les conditions, les alternatives et les informations manquantes, et enregistre le choix final de l'étudiant avec sa justification.

```text
PHASE 4 TERMINÉE — En attente de validation avant le démarrage de la PHASE 5.
```
