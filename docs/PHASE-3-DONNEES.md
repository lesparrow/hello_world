# STATPFE Desktop : Phase 3, données

Date : 22 novembre 2026
Statut : **terminée côté code, en attente de validation**.

## 1. Objectif de la phase

Importer des données réelles (CSV, Excel), les prévisualiser, comprendre et corriger les variables, repérer les problèmes de qualité, et préparer des versions de travail sans jamais modifier l'original.

## 2. Ce qui a été observé

Le socle de la Phase 2 (projet `.statpfe`, moteur JSON-RPC, interface React) était stable et testé sous Linux et Windows. Le moteur n'avait aucune dépendance externe ; cette phase ajoute pandas et openpyxl.

## 3. Décisions et justifications

| Décision | Justification |
|---|---|
| Le fichier importé est copié **octet pour octet** dans le projet (`sources/<sha256>.<ext>`) avec son empreinte SHA-256 | C'est la seule façon de garantir que l'original n'est jamais modifié et de le prouver. Une altération est détectée à l'ouverture. |
| Lecture de toutes les cellules comme **textes bruts**, puis conversion explicite par le dictionnaire | Rien n'est converti en silence : « 007 » reste « 007 », « 3,5 » n'est pas perdu, « NSP » est signalé comme valeur invalide au lieu de disparaître. |
| Une version = l'original + le dictionnaire + une liste d'étapes rejouées | Toute version est reproductible et réversible (retirer une étape la recalcule). Chaque version a une empreinte de contenu, que les analyses de la Phase 4 enregistreront. |
| Pas de format Parquet pour l'instant (écart par rapport au document de Phase 1) | Les données sont recalculées à partir de la source en moins d'une seconde pour des tailles de PFE ; cela évite d'embarquer pyarrow (environ 40 Mo de plus). À réévaluer si de gros fichiers posent problème. |
| Détection automatique des types et des identifiants potentiels, toujours modifiable | Gain de temps pour l'étudiant, mais la décision finale lui revient, avec le type détecté visible. |
| Colonnes identifiantes (nom, e-mail, téléphone, CIN, matricule…) **masquées par défaut** dans tous les aperçus | Protection des données personnelles d'enquête ; affichage possible à la demande. |
| Le journal note les variables modifiées et les opérations, jamais les valeurs | Traçabilité sans dupliquer de données sensibles. |
| Migration automatique des projets créés en Phase 2 (format 1 vers format 2) | Un projet existant reste ouvrable ; la migration est notée dans le journal. |
| Excel ancien (`.xls`) et SPSS (`.sav`) : refusés avec un message clair | Pas de prise en charge fiable sans dépendances supplémentaires ; prévu plus tard. |

## 4. Fichiers concernés

```text
engine/statpfe/data/sources.py      Lecture CSV (encodage, séparateur) et Excel (feuilles), textes bruts
engine/statpfe/data/types.py        Dictionnaire : types, niveaux, rôles, modalités, codes manquants, conversion
engine/statpfe/data/quality.py      Diagnostic de qualité et avertissements classés
engine/statpfe/data/transforms.py   Étapes : doublons, filtre, cas complets, recodage, variables calculées
engine/statpfe/data/store.py        Stockage dans le projet, versions, aperçu, empreintes
engine/statpfe/core/project.py      Format 2 de l'archive, migration du format 1
engine/statpfe/rpc/server.py        12 nouvelles méthodes data.*
apps/desktop/src/screens/data/      Import, aperçu, dictionnaire, qualité, préparation
engine/tests/test_data.py           49 nouveaux tests
```

## 5. Ce qui a réellement été implémenté

**Import**
- CSV, TXT, TSV : détection de l'encodage (UTF-8, Windows cp1252, Latin-1), du séparateur (`;`, `,`, tabulation, `|`), lignes de longueur irrégulière signalées, alerte si des accents semblent mal décodés.
- Excel `.xlsx` : choix de la feuille, valeurs calculées des formules, dates et booléens.
- Option « la première ligne contient les noms », noms vides ou en double renommés (V2, a_2…).
- Fenêtre d'import avec aperçu, types proposés, colonnes masquées, réglages modifiables avant validation.

**Dictionnaire des variables** : nom, libellé, type (numérique, texte, oui/non, date), niveau de mesure (nominal, ordinal, quantitatif, avec contrôle de cohérence), rôle (à expliquer, explicative, identifiant, exclue), codes de valeurs manquantes (ex. NSP, 99), modalités avec libellés et ordre, masquage.

**Qualité** : lignes, variables, lignes complètes, doublons exacts ; valeurs invalides avec exemples ; manquants par variable ; variables constantes ; identifiants potentiels ; suggestion « échelle de Likert ? ». Classement : erreur bloquante, avertissement important, avertissement méthodologique, suggestion, information.

**Préparation** : original en lecture seule ; versions de travail (créer, dupliquer, renommer, supprimer) ; étapes « supprimer les doublons », « filtrer les lignes » (=, ≠, <, ≤, >, ≥, parmi, hors de, manquant), « exclure les lignes incomplètes », « recoder / regrouper des modalités », « variable calculée » (ln, log10, score z, normalisation 0-1) ; effectifs avant et après chaque étape ; avertissements (ex. logarithme de valeurs nulles) ; retrait d'une étape refusé si une étape suivante en dépend ; version signalée « à corriger » si un changement du dictionnaire casse une étape.

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 93 tests `pytest` (dont 49 nouveaux) : nombres français (« 12,5 », « 1 234,5 », « 1.234,5 »), encodages UTF-8 avec BOM et cp1252, mauvais encodage détecté, lignes irrégulières, en-têtes vides ou doublés, fichiers vides ou illisibles, `.xls`, SPSS, faux `.xlsx`, feuilles Excel, copie exacte conservée et identique après réouverture, codes manquants, contrôles du dictionnaire, masquage, pagination, versions, retrait d'étape, dépendances entre étapes, score z vérifié (moyenne 0, écart-type 1), logarithme de valeurs négatives, variable constante, source altérée détectée, migration d'un projet Phase 2, protocole JSON-RPC | 93 réussis (Linux, Python 3.13) |
| Interface : typecheck, 5 tests `vitest`, build | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface, vrai moteur) avec une enquête fictive de 61 réponses en cp1252 : création du projet, import, aperçu masqué, déclaration de « NSP » et « 99 » comme manquants, onglet qualité, version de travail avec suppression des doublons (61 → 60 lignes) et score z de la note, Ctrl+S, fermeture, réouverture : les deux étapes sont retrouvées | Réussi, aucune erreur dans la console |
| Moteur autonome PyInstaller sous Linux avec pandas : lecture d'un CSV et d'un classeur Excel | Réussi (57 Mo, démarrage environ 1,2 s) |
| CI Windows : tests du moteur, construction de l'installateur, lecture d'un CSV cp1252 par le moteur autonome, installation et désinstallation | Voir le résultat de la CI sur la PR |

## 7. Limites et points non terminés

- Pas encore de test manuel sur un vrai PC Windows.
- Taille du moteur autonome passée de 12 à 57 Mo (pandas). Démarrage d'environ 1 s, toujours en `--onefile`.
- Pas de prise en charge de `.xls`, `.ods` ni SPSS.
- Les fichiers de plus de 200 Mo sont refusés ; les performances au-delà de quelques centaines de milliers de lignes n'ont pas été mesurées.
- L'étape « filtrer » accepte une seule condition à la fois (plusieurs étapes successives donnent un « ET »).
- Pas d'export d'une version vers CSV/Excel ni d'export anonymisé (prévu avec les rapports).
- Pas de comparaison visuelle entre deux versions (seulement effectifs et empreintes).
- La correction d'une valeur individuelle (cellule par cellule) n'est volontairement pas proposée : elle doit passer par un recodage traçable.

## 8. Vérifications manuelles proposées

1. Importer un vrai export de questionnaire (Google Forms en CSV, ou Excel).
2. Vérifier que les types proposés sont corrects ; corriger un type et déclarer un code « NSP ».
3. Créer une version de travail, filtrer une population, puis retirer le filtre.
4. Enregistrer, fermer, rouvrir : vérifier que tout est retrouvé et que le fichier original sur le disque n'a pas changé.

## 9. Documentation mise à jour

`README.md` et ce document.

## 10. Phase suivante proposée

**Phase 4 : statistiques fondamentales.** Descriptives, fréquences, tableaux croisés, histogrammes et boxplots, puis les tests prévus (t de Student, Welch, apparié, Mann-Whitney, Wilcoxon, Pearson, Spearman, khi-deux, Fisher), chacun validé contre R en CI, avec la version et l'empreinte des données enregistrées dans chaque résultat.

```text
PHASE 3 TERMINÉE — En attente de validation avant le démarrage de la PHASE 4.
```
