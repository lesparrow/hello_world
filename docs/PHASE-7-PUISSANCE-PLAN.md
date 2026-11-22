# STATPFE Desktop : Phase 7, puissance et plan d'analyse

Date : 22 novembre 2026
Statut : **terminée côté code, en attente de validation**.

## 1. Objectif de la phase

Permettre à l'étudiant de justifier la taille de son échantillon et de fixer son plan d'analyse avant l'analyse finale (§12 et §13 du cahier des charges) :

- estimer une taille d'échantillon avant l'étude, évaluer la puissance après la collecte, comparer plusieurs tailles d'effet, choisir α et la puissance visée, enregistrer les hypothèses du calcul et les reprendre dans le rapport ;
- rédiger un plan d'analyse (objectifs, hypothèses, variables principales et secondaires, analyses prévues, critères d'exclusion, valeurs manquantes, analyses exploratoires), le verrouiller et historiser toute modification ;
- distinguer dans le rapport les analyses prévues de celles ajoutées après avoir vu les données.

La puissance est toujours présentée comme une estimation qui dépend des hypothèses, jamais comme une garantie.

## 2. Ce qui a été observé

Le projet contenait déjà les hypothèses de l'étude, la taille d'échantillon prévue et, pour chaque analyse, sa date, sa nature (confirmatoire ou exploratoire) et l'hypothèse liée. Rien ne permettait de savoir si une analyse avait été prévue avant de voir les données : une analyse « confirmatoire » pouvait être déclarée telle après coup. Il fallait donc une trace datée et non modifiable du plan, et un rattachement des analyses à ce plan au moment du calcul.

## 3. Décisions et justifications

| Décision | Justification |
|---|---|
| Formules de Cohen (1988), identiques au paquet R pwr : loi de Student non centrale (tests t), arc sinus (deux proportions), khi-deux non central, transformation de Fisher (corrélation) | Références les plus citées dans les mémoires ; reproduisibles dans R. Les deux faces du test bilatéral sont comptées (comme `power.t.test(strict = TRUE)`). |
| Taille d'échantillon : recherche exacte du plus petit entier qui atteint la puissance visée, puissance recalculée avec cet entier | Un effectif est un entier ; on affiche la puissance réellement atteinte, pas une valeur arrondie. |
| Six plans : deux groupes, apparié, un échantillon, deux proportions, khi-deux, corrélation ; trois calculs : taille, puissance, plus petit effet détectable | Couvre les tests disponibles dans STATPFE (§12). |
| Jusqu'à six effets comparés, courbe de puissance calculée par le moteur | Comparer plusieurs hypothèses d'effet ; l'interface ne fait que dessiner. |
| Groupes déséquilibrés (rapport n₂/n₁) et pertes prévues | Situations courantes en PFE (groupes inégaux, abandons). |
| Pour Mann-Whitney et Wilcoxon : effectif du test t divisé par l'efficacité relative asymptotique (3/π sous normalité, 0,864 au pire) | Approximation classique (Lehmann), présentée comme telle. |
| Après la collecte : seuls les effectifs d'une analyse sont repris ; l'effet reste celui supposé par l'auteur. Pas de « puissance observée » | La puissance calculée avec l'effet observé se déduit de la valeur p et n'apporte rien ; c'est une erreur fréquente. Le plus petit effet détectable est proposé à la place. |
| Hypothèses du calcul listées avec chaque résultat, origine de l'effet demandée (avertissement si absente) | §12 : enregistrer les hypothèses ; le résultat en dépend entièrement. |
| Plan en versions : brouillon modifiable, version verrouillée immuable ; une modification après verrouillage crée une nouvelle version, verrouillée avec un motif obligatoire | §13 : verrouillage et historisation. Les versions verrouillées ne sont jamais réécrites. |
| Références stables des analyses prévues (A1, A2…), jamais réutilisées | Une analyse retirée puis ajoutée ne prend pas l'identité d'une autre. |
| Une analyse est « prévue » seulement si elle est rattachée, au moment du calcul, à un plan déjà verrouillé ; un écart (méthode ou variables) exige une raison | Par construction, une analyse prévue est postérieure au verrouillage : on ne peut pas reclasser après coup. |
| Rapport : section « Plan d'analyse » (contenu, date de verrouillage avant ou après l'import et les analyses, historique), section « Taille d'échantillon et puissance », colonne « Plan » dans la méthodologie, statut de chaque analyse, limites (hors plan, prévue non réalisée, plan modifié après le début des analyses, effectif inférieur au calcul) | §13 : distinguer prévu et exploratoire ; aucune information gênante n'est omise. |
| Contrôles avant export : calculs de puissance refaits et comparés ; analyses prévues absentes ; plan non verrouillé ; plan modifié après le début des analyses ; effectif insuffisant | Même exigence de cohérence que pour les analyses. |
| Format de projet 5 (deux tables), migration automatique des projets au format 4 ; horodatage à la milliseconde | Ancien projet ouvert sans perte ; ordre fiable entre verrouillage et analyses. |
| Un calcul cité par un plan verrouillé ne peut pas être supprimé | La justification de la taille reste disponible. |

## 4. Fichiers concernés

```text
engine/statpfe/stats/power.py           Calculs de puissance, taille, plus petit effet, courbes, hypothèses
engine/statpfe/stats/power_store.py     Calculs enregistrés (table power_calcs), recalcul de contrôle
engine/statpfe/core/plan.py             Plan d'analyse versionné (table plan_versions), rattachement, statut des analyses
engine/statpfe/core/project.py          Format 5, migration, état du plan et nombre de calculs
engine/statpfe/core/timeutil.py         Horodatage à la milliseconde
engine/statpfe/stats/store.py           Rattachement d'une analyse au plan au moment du calcul
engine/statpfe/report/build.py          Sections Plan et Puissance, colonne Plan, limites
engine/statpfe/report/checks.py         Contrôles liés au plan et à la puissance
engine/statpfe/report/charts.py         Courbe de puissance (niveaux de gris, traits différents)
engine/statpfe/report/options.py        Sections plan et power, choix des calculs inclus
engine/statpfe/report/service.py        Options : calculs de puissance inclus
engine/statpfe/rpc/server.py            power.* et plan.*
engine/tests/reference/r_power.R        Valeurs de référence calculées par R (pwr, power.t.test)
engine/tests/test_power_r.py            31 cas comparés à R
engine/tests/test_plan_power.py         31 tests (calculs, plan, rattachement, migration, rapport, RPC)
apps/desktop/src/screens/power/PowerPage.tsx   Écran « Puissance »
apps/desktop/src/screens/plan/PlanPage.tsx     Écran « Plan d'analyse »
apps/desktop/src/screens/analysis/NewAnalysisModal.tsx  Rattachement au plan, raison d'un écart
apps/desktop/src/screens/report/ReportPage.tsx  Choix des calculs de puissance
apps/desktop/src/components/charts/Charts.tsx   Courbe de puissance
.github/workflows/ci.yml                 R avec pwr ; calcul de puissance par le moteur autonome Windows
```

## 5. Ce qui a réellement été implémenté

**Écran « Puissance »** : calcul de la taille d'échantillon, de la puissance ou du plus petit effet détectable ; six types de test ; α, puissance visée, test bilatéral ou unilatéral ; effet saisi directement (d, r, w) ou à partir d'une différence et d'un écart-type, ou de deux proportions ; bouton « Comparer petit, moyen, grand » (repères de Cohen, présentés comme un pis-aller) ; rapport des effectifs, pertes prévues ; reprise des effectifs d'une analyse enregistrée ; résultat recalculé à chaque modification avec lecture par règles fixes, tableau, courbe, hypothèses, avertissements et équivalent R ; enregistrement et liste des calculs du projet.

**Écran « Plan d'analyse »** : objectifs et hypothèses (reprise possible de la fiche Étude), variables principales et secondaires, seuil, taille prévue et calcul de puissance de référence, analyses prévues (méthode, variables par rôle, hypothèse, rôle principal ou secondaire, test, calcul de puissance, précisions), critères d'exclusion, valeurs manquantes, tests multiples, analyses exploratoires ; enregistrement automatique du brouillon ; verrouillage avec confirmation ; modifications en attente par rapport à la version verrouillée ; historique avec motifs et changements ; lecture d'une ancienne version ; abandon d'un brouillon.

**Nouvelle analyse** : si un plan est verrouillé, l'analyse prévue correspondante est proposée automatiquement (même méthode, mêmes variables) ; un écart demande sa raison ; sans rattachement, l'interface indique que l'analyse sera présentée comme ajoutée après consultation des données.

**Rapport** : voir le tableau des décisions ; exemples joints (`exemple-rapport-phase7.docx` et `.pdf`).

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 304 tests `pytest` (dont 62 nouveaux) | 304 réussis (Linux, Python 3.13) |
| Validation contre R 4.3.3 et pwr 1.3.0 : 31 cas (tailles, puissances, plus petits effets ; bilatéral et unilatéral ; groupes déséquilibrés ; α = 0,01 à 0,10), 64 valeurs | Effectifs identiques ; puissances à 10⁻⁹ près ; effets à 10⁻⁸ près ; accord avec `power.t.test(strict = TRUE)` |
| Valeurs de manuel : d = 0,5 → 64 par groupe ; r = 0,3 → 85 | Conformes |
| Plan : versions, verrouillage, motif obligatoire, immutabilité, références stables, rattachement et écarts, migration du format 4 | Réussis |
| Rapport : prévu / hors plan / avant le plan, prévue non réalisée, historique, effectif insuffisant, calcul modifié à la main détecté (bloquant) | Réussis |
| Interface : typecheck, 8 tests `vitest` | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface, vrai moteur) : calcul de taille avec trois effets et 10 % de pertes, enregistrement ; plan rédigé (2 analyses prévues), verrouillé ; analyse lancée et rattachée automatiquement à A1 ; écart justifié à A2 ; analyse hors plan ; plan modifié puis verrouillé en version 2 avec motif ; puissance après la collecte ; contrôles et export Word puis PDF | Réussi, aucune erreur dans la console. Captures dans `captures-phase7/` |

## 7. Limites et points non terminés

- Pas de calcul pour plus de deux groupes (ANOVA), la régression ou les tests non paramétriques exacts : ces méthodes n'existent pas encore dans STATPFE. Pour Mann-Whitney et Wilcoxon, l'ajustement est une approximation.
- Le calcul de deux proportions utilise l'approximation arc sinus (pwr) ; il ne reproduit pas `power.prop.test` (formule voisine, résultats proches mais pas identiques).
- Le test t de Welch est planifié avec la formule du test de Student (écarts-types égaux supposés).
- Le brouillon du plan n'est historisé qu'au verrouillage : les retouches successives d'un même brouillon ne sont pas conservées une à une.
- Le rattachement au plan se fait au lancement de l'analyse ; une analyse déjà calculée ne peut pas être rattachée ensuite (volontairement).
- Les dates de verrouillage reposent sur l'horloge de l'ordinateur ; ce n'est pas un préenregistrement public (OSF, par exemple).
- Rendu Word toujours non vérifié dans Microsoft Word lui-même (vérifié par python-docx et LibreOffice).

## 8. Vérifications manuelles proposées

1. Calculer une taille d'échantillon pour votre propre étude et comparer avec G*Power ou R (`pwr::pwr.t.test`).
2. Rédiger et verrouiller un plan, lancer une analyse prévue puis une analyse non prévue, et vérifier leur présentation dans le rapport.
3. Modifier le plan après une analyse : vérifier que le motif est demandé et qu'il apparaît dans l'historique et dans les limites.

## 9. Documentation mise à jour

`README.md` et ce document.

## 10. Phase suivante proposée

**Phase 8 : IA locale (optionnelle).** Un modèle installé sur l'ordinateur, désactivable, qui aide à expliquer une méthode ou un tableau et à proposer un paragraphe prudent. Il ne calcule rien, n'invente aucun nombre, n'envoie aucune donnée à l'extérieur, et chaque texte produit est signalé « à vérifier ».

Hors phases, toujours possible avant ou après : ANOVA, Kruskal-Wallis, McNemar et régressions (avec leurs calculs de puissance), matrice de corrélation et graphiques manquants.

```text
PHASE 7 TERMINÉE — En attente de validation avant le démarrage de la PHASE 8.
```
