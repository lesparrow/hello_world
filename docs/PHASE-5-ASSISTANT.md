# STATPFE Desktop : Phase 5, assistant méthodologique

Date : 22 novembre 2026
Statut : **terminée côté code, en attente de validation**.

## 1. Objectif de la phase

Aider l'étudiant à choisir une méthode statistique avec un assistant déterministe, transparent et indépendant de toute IA. Pour chaque recommandation, l'assistant affiche la méthode, la raison, les conditions, les diagnostics à examiner, les limites, les alternatives et les informations manquantes. L'étudiant peut choisir une autre méthode, et sa justification est enregistrée avec l'analyse.

## 2. Ce qui a été observé

Le catalogue de la Phase 4 décrit déjà chaque méthode (objectif, conditions, équivalent R), et le dictionnaire des variables donne leur type et leur niveau de mesure (quantitatif, ordinal, nominal). Les hypothèses de l'étude sont saisies dans la fiche « Étude » depuis la Phase 2. Il manquait la logique qui relie un objectif de recherche et des données à une méthode, et la trace du choix.

## 3. Décisions et justifications

| Décision | Justification |
|---|---|
| Règles écrites en Python, lisibles et versionnées (`assistant-1`) | Même situation, même recommandation. La version des règles est enregistrée avec chaque choix, donc un changement de règles futur ne réécrit pas l'histoire. |
| Quatre objectifs : décrire, comparer des groupes indépendants, comparer deux mesures appariées, étudier un lien | Ils couvrent toutes les méthodes disponibles. L'étudiant raisonne en objectif de recherche, pas en nom de test. |
| Critères utilisés : nature des variables (dictionnaire), nombre de groupes, appariement, effectifs, asymétrie G1, valeurs extrêmes (1,5 × EIQ), effectifs théoriques des tableaux croisés, nature confirmatoire ou exploratoire | Ce sont les éléments listés au §11 du cahier des charges. |
| **Aucun test de normalité dans les règles** | Exigence du §11. Un test de Shapiro-Wilk est surtout sensible à la taille de l'échantillon. Un test vérifie que les recommandations ne citent jamais Shapiro ni un test de normalité. |
| Welch recommandé par défaut pour deux groupes ; Mann-Whitney pour une variable ordinale, ou pour de petits groupes (n < 15) à distribution irrégulière (\|G1\| ≥ 1 ou valeurs extrêmes) | Welch reste valide quand les variances sont égales. Avec 15 observations ou plus par groupe, le test t est robuste à un écart modéré à la normalité. |
| Spearman pour une variable ordinale, en présence de valeurs extrêmes, ou quand les deux distributions sont irrégulières ; sinon Pearson | Pearson est sensible aux points isolés ; Spearman mesure une relation monotone. |
| Fisher quand un effectif théorique est inférieur à 1 ou que plus de 20 % sont inférieurs à 5 (dans les limites du calcul exact) ; sinon khi-deux | Règle de Cochran, celle qu'utilise aussi le diagnostic de la Phase 4. |
| Plus de deux groupes : **pas de recommandation**, ANOVA de Welch et Kruskal-Wallis listées comme « pas encore disponibles » | Honnêteté : ces méthodes ne sont pas implémentées. L'étudiant peut choisir deux groupes précis, avec un avertissement sur les comparaisons multiples. |
| Une variable numérique déclarée quantitative qui ne prend que 3 à 7 valeurs déclenche une question (« échelle de Likert ? ») | Erreur fréquente en mémoire de fin d'études ; l'assistant ne corrige pas le dictionnaire à la place de l'étudiant. |
| Le moteur **recalcule** la recommandation au moment de l'enregistrement | L'interface ne peut pas enregistrer un choix « suivi » qui ne le serait pas. Si la méthode diffère de la recommandation, le moteur exige une justification. |
| Le choix enregistré contient : mode (assistant ou direct), objectif, méthode recommandée et ses raisons, méthode retenue, justification, informations manquantes au moment du choix, nature confirmatoire ou exploratoire, hypothèse liée, version des règles | Traçabilité demandée par un jury : pourquoi cette méthode, et qui l'a décidé. |
| Un écart à la recommandation est aussi inscrit au journal du projet | Le journal reste la chronologie complète du projet. |
| Format du projet passé à la version 4 (colonne `choice`), avec migration automatique depuis les versions 1, 2 et 3 | Les projets existants restent ouvrables ; leurs anciennes analyses affichent « non enregistré ». |

## 4. Fichiers concernés

```text
engine/statpfe/stats/advisor.py        Règles de l'assistant (nouveau)
engine/statpfe/stats/store.py          Validation et enregistrement du choix, migration v3 → v4
engine/statpfe/core/project.py         Format 4
engine/statpfe/rpc/server.py           analysis.advise ; analysis.run accepte « choice »
engine/tests/test_advisor.py           25 tests (nouveau)
apps/desktop/src/screens/analysis/AdvisorStep.tsx      Parcours guidé (nouveau)
apps/desktop/src/screens/analysis/NewAnalysisModal.tsx Entrée « Être guidé », contexte en choix direct
apps/desktop/src/screens/analysis/ResultView.tsx       Section « Choix de la méthode »
apps/desktop/src/screens/analysis/variables.ts         Règles d'exclusion des variables (déplacées)
apps/desktop/src/engine/types.ts                       Types de l'assistant et du choix
```

## 5. Ce qui a réellement été implémenté

**Parcours guidé** dans « Nouvelle analyse » : choix de l'objectif, des variables (identifiants et variables exclues grisés), confirmation que les groupes sont indépendants, choix éventuel de deux groupes parmi plusieurs, nature de l'analyse (confirmatoire, exploratoire ou non précisée), hypothèse de l'étude mise à l'épreuve.

**Recommandation** affichée avec : méthode, « Pourquoi », conditions nécessaires, ce qu'il faut examiner dans le résultat, limites, ce que l'assistant a observé dans les données (effectifs, asymétrie, valeurs extrêmes, répartition des groupes), informations manquantes ou à vérifier, alternatives avec leur cas d'usage, et le principe de l'assistant.

**Choix de la méthode** : l'étudiant retient la méthode recommandée ou une alternative. S'il s'écarte de la recommandation, une justification est obligatoire (le bouton reste désactivé sans elle, et le moteur la refuse s'il la reçoit vide). Les variables sont ensuite verrouillées dans l'écran de configuration ; les options (hypothèse unilatérale, niveau de confiance…) restent réglables.

**Choix direct** : toujours possible. La nature de l'analyse et l'hypothèse liée peuvent y être précisées.

**Résultat** : une section « Choix de la méthode » indique le mode, l'objectif, la méthode recommandée et ses raisons, la méthode retenue, la justification de l'écart, les informations manquantes, la version des règles, la nature de l'analyse et l'hypothèse liée. Un badge indique « recommandation suivie » ou « autre méthode, justifiée ».

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 205 tests `pytest` (dont 25 nouveaux pour l'assistant) | 205 réussis (Linux, Python 3.13) |
| Scénarios de l'assistant : Welch, petits groupes asymétriques → Mann-Whitney, petits groupes réguliers → Welch, variable ordinale, question Likert, trois groupes (blocage honnête puis choix de deux groupes), variable qualitative → khi-deux, Fisher sur petits effectifs, un seul groupe, t apparié, Wilcoxon, McNemar non disponible, unités différentes, Pearson, Spearman (valeurs extrêmes, ordinal), lien mixte → comparaison de groupes, description | Réussis |
| Invariants : la méthode recommandée existe toujours dans le catalogue ; aucune recommandation ne cite un test de normalité ; les réponses sont sérialisables | Réussis |
| Enregistrement : recommandation suivie, écart sans justification refusé, écart justifié inscrit au journal, choix direct, choix invalides refusés, migration d'un projet au format 3 | Réussis |
| Interface : typecheck, 8 tests `vitest` | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface, vrai moteur), enquête fictive de 61 réponses avec deux hypothèses : comparaison Note × Tutorat guidée (Welch recommandé, suivi, H1 liée), lien Note × Satisfaction (Pearson recommandé, Spearman choisi : bouton bloqué sans justification, puis justification enregistrée et inscrite au journal), fréquences en choix direct avec nature « exploratoire » | Réussi, aucune erreur dans la console. Captures dans `captures-phase5/` |

CI sur ce commit : moteur sous Ubuntu et Windows, validation contre R, interface et installateur Windows (calcul réel par le moteur autonome, installation et désinstallation silencieuses) : tous réussis.

## 7. Limites et points non terminés

- Les règles couvrent les 12 méthodes disponibles. ANOVA, Kruskal-Wallis, McNemar et les régressions sont signalées comme non disponibles, jamais simulées.
- Les seuils (n < 15, |G1| ≥ 1, 1,5 × EIQ) sont des repères usuels, pas des vérités : l'assistant le dit et laisse le choix final à l'étudiant.
- L'assistant ne connaît pas le plan d'étude au-delà de ce qui est déclaré (indépendance, appariement) ; il ne peut pas détecter seul des mesures répétées cachées.
- Une analyse « exploratoire » n'est pas encore regroupée ou signalée dans un futur rapport : ce sera traité avec les rapports (Phase 6).
- Pas encore de test manuel sur un vrai PC Windows.

## 8. Vérifications manuelles proposées

1. Lancer « Être guidé » sur vos propres données et vérifier que les raisons affichées correspondent à ce que vous savez de vos variables.
2. Choisir une méthode différente de la recommandation : le bouton doit rester bloqué tant que la justification est vide.
3. Ouvrir « Choix de la méthode » dans le résultat, puis le journal du projet.
4. Déclarer une échelle de Likert comme ordinale dans le dictionnaire, relancer l'assistant : la recommandation doit passer à une méthode de rangs.

## 9. Documentation mise à jour

`README.md` et ce document.

## 10. Phase suivante proposée

**Phase 6 : rapports.** Exports professionnels (Word, PDF ou HTML) des analyses enregistrées avec tableaux, graphiques, traçabilité et choix de méthode, et contrôles de cohérence avant export (données modifiées depuis l'analyse, analyses exploratoires présentées comme telles, hypothèses sans analyse).

```text
PHASE 5 TERMINÉE — En attente de validation avant le démarrage de la PHASE 6.
```
