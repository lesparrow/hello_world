# STATPFE Desktop : Phase 6, rapports

Date : 22 novembre 2026
Statut : **terminée côté code, en attente de validation**.

## 1. Objectif de la phase

Produire des rapports académiques professionnels en Word et en PDF à partir de l'étude et des analyses enregistrées, avec des modèles personnalisables et des contrôles de cohérence avant export (§17 du cahier des charges). Le rapport est toujours présenté comme un document de travail à réviser, jamais comme un travail validé.

## 2. Ce qui a été observé

Toutes les informations d'un rapport existent déjà dans le projet : fiche de l'étude et hypothèses, dictionnaire et qualité des variables, versions et étapes de préparation, résultats complets des analyses (tableaux, graphiques, diagnostics, lecture), choix de méthode et traçabilité. Il manquait leur mise en page et un contrôle de cohérence au moment de l'export. Les graphiques de l'interface sont dessinés dans le navigateur : il fallait un moteur de dessin côté Python pour les fichiers.

## 3. Décisions et justifications

| Décision | Justification |
|---|---|
| Rapport construit par le moteur Python, dans une représentation unique (titres, paragraphes, tableaux, figures) rendue ensuite en Word et en PDF | Word et PDF ont exactement le même contenu. Aucun nombre n'est recalculé ni retapé : tout vient des résultats enregistrés. |
| Word avec python-docx, PDF avec reportlab, figures avec matplotlib | Bibliothèques libres, éprouvées, fonctionnant hors ligne et dans l'exécutable autonome. Pas de dépendance à Word ou LibreOffice sur la machine de l'étudiant. |
| Figures en niveaux de gris, avec hachures pour distinguer les séries | Lisibles à l'impression en noir et blanc (§15). |
| Police DejaVu incorporée au PDF | Les caractères « − », « ≥ », « χ² », « α » et les accents s'affichent sur toute machine. |
| Chaque tableau et figure : numéro, légende, source (jeu, version, numéro d'analyse, empreinte des données) ; chaque figure : description textuelle | Exigences du §15 et du §17. |
| Numérotation Word par de vrais champs (SEQ) et sommaire en champ TOC | L'étudiant peut réorganiser son document dans Word et générer une table des illustrations. |
| Mêmes règles d'arrondi que l'interface : valeurs p à trois décimales et « < 0,001 », virgule décimale, signe moins typographique | Présentation homogène des valeurs p (§17). Des tests vérifient l'accord avec l'interface. |
| Cinq modèles : PFE, mémoire de master, thèse, article, rapport d'enquête ; 15 sections activables ; page de garde personnalisable | Modèles personnalisables demandés au §17. |
| Discussion, conclusion et une partie des limites marquées « à rédiger », surlignées | Seul l'auteur peut interpréter ses résultats au regard de la littérature. STATPFE n'invente aucun texte. |
| Contrôles avant export : les analyses sont **recalculées** et comparées valeur par valeur (valeurs, effectifs, tableaux, graphiques) ; une donnée modifiée depuis l'analyse ou un écart bloque l'export | Contrôle réel de la cohérence des effectifs, des tableaux et des graphiques et de la version des données. |
| Avertissements importants des analyses, analyses exploratoires, écarts à la recommandation, informations manquantes et hypothèses sans analyse : repris dans la section Limites | Un avertissement ignoré reste visible dans le rapport (§14). |
| Valeurs des variables identifiantes jamais reproduites (le dictionnaire cite leur nom seulement) ; aucune note personnelle reprise | Confidentialité (§18). Un test vérifie qu'aucun nom ni e-mail ne figure dans le rapport. |
| Options du rapport enregistrées dans le projet (sans changer le format de fichier) | On retrouve son modèle et sa page de garde à la réouverture. |
| Fichier écrit dans un fichier temporaire puis renommé ; export inscrit au journal | Jamais de fichier à moitié écrit ; traçabilité. |

## 4. Fichiers concernés

```text
engine/statpfe/report/options.py       Modèles, sections, page de garde, validation des options
engine/statpfe/report/build.py         Contenu du rapport à partir du projet
engine/statpfe/report/checks.py        Contrôles avant export
engine/statpfe/report/charts.py        Figures (matplotlib) et leurs descriptions textuelles
engine/statpfe/report/fmt.py           Mise en forme des nombres (mêmes règles que l'interface)
engine/statpfe/report/model.py         Représentation intermédiaire du document
engine/statpfe/report/render_docx.py   Rendu Word
engine/statpfe/report/render_pdf.py    Rendu PDF
engine/statpfe/report/service.py       Options enregistrées, contrôle, export
engine/statpfe/stats/store.py          verify() : recalcul silencieux d'une analyse
engine/statpfe/rpc/server.py           report.templates, report.options, report.check, report.export
engine/packaging/build_sidecar.py      Fichiers de python-docx embarqués, modules graphiques inutiles exclus
engine/tests/test_report.py            36 tests (nouveau)
apps/desktop/src/screens/report/ReportPage.tsx  Écran « Rapport »
.github/workflows/ci.yml               Export Word et PDF par le moteur autonome Windows
```

## 5. Ce qui a réellement été implémenté

**Écran « Rapport »** (activé dans le parcours dès qu'une analyse existe) : choix du modèle ; page de garde (auteurs, encadrant, établissement, filière, année, lieu) ; 15 sections activables ; figures incluses ou non ; choix et ordre des analyses ; contrôles mis à jour à chaque modification ; plan du rapport avec le nombre de tableaux et de figures ; export Word ou PDF.

**Contenu du rapport** : page de garde avec la mention « document de travail à réviser », sommaire, présentation de l'étude (problématique, objectifs), hypothèses avec les analyses qui les mettent à l'épreuve, population et échantillonnage (taille prévue et taille obtenue), dictionnaire des variables avec valeurs manquantes, préparation des données (fichier source, empreinte, étapes de chaque version utilisée), méthodologie (logiciels et versions, tableau des analyses, seuil et caractère bilatéral, valeurs manquantes, choix des méthodes et justifications), statistiques descriptives, analyses inférentielles (résultats principaux, tableaux, figures, lecture produite par des règles fixes, diagnostics), discussion à rédiger, limites, conclusion à rédiger, annexe de traçabilité (paramètres, empreinte SHA-256 complète, environnement), journal méthodologique.

**Contrôles avant export** : bloquants (analyse introuvable, aucune analyse, données modifiées, version supprimée ou à corriger, recalcul impossible ou différent, effectif incohérent) ; importants (avertissements des analyses, section Limites désactivée alors qu'il y a des avertissements) ; méthodologiques (hypothèse sans analyse, analyse confirmatoire sans hypothèse, problématique vide) ; informations (exploratoire, écart justifié, sections à rédiger, versions de logiciel différentes). Les contrôles réussis sont listés, dont l'absence de texte généré par IA.

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 241 tests `pytest` (dont 36 nouveaux pour les rapports) | 241 réussis (Linux, Python 3.13) |
| Fichiers relus : le .docx est rouvert avec python-docx, le PDF avec pypdf ; toutes les statistiques du test de Welch y figurent telles que mises en forme ; nombre d'images = nombre de figures ; champs SEQ et TOC présents ; police DejaVu incorporée ; métadonnées (titre, auteur) | Réussi |
| Contrôles : données modifiées → export refusé et aucun fichier écrit ; effectif modifié à la main dans un résultat enregistré → détecté au recalcul ; aucune analyse → bloquant | Réussi |
| Confidentialité : aucun des 40 noms ni e-mail du jeu de test dans le rapport | Réussi |
| Interface : typecheck, 8 tests `vitest` | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface, vrai moteur) : projet de 61 réponses, 4 analyses, page de garde remplie, journal en annexe, export Word (12 tableaux, 7 figures) puis PDF, puis données modifiées → contrôles bloquants et bouton d'export désactivé | Réussi, aucune erreur dans la console. Captures dans `captures-phase6/`, rapports d'exemple joints |
| Rendu du .docx vérifié en le convertissant avec LibreOffice (mise en page, tableaux, figures) | Correct |
| Moteur autonome PyInstaller sous Linux : projet, import, Welch, export Word et PDF | Réussi (100 Mo, contre 86 Mo avant) |

CI sur ce commit : moteur sous Ubuntu et Windows (241 tests), validation contre R, interface, et installateur Windows où le moteur autonome produit réellement un rapport Word et un rapport PDF : tous réussis.

## 7. Limites et points non terminés

- Le rendu dans Microsoft Word n'a pas été vérifié à l'œil sur un vrai PC : le fichier a été relu par python-docx et affiché par LibreOffice. Word demande de mettre à jour les champs à l'ouverture (sommaire et numéros).
- Pas de bouton « Ouvrir le fichier » : le chemin du rapport exporté est affiché.
- Pas de matrice de corrélation, de barres d'erreur ni de graphique des valeurs manquantes (§15) : ces graphiques n'existent pas encore dans les analyses.
- Le premier export sur une machine construit le cache des polices de matplotlib (quelques secondes, une seule fois).
- Pas d'export d'une copie anonymisée des données ni de format LaTeX.
- Les modèles diffèrent par leur page de garde et leurs sections, pas encore par la mise en forme (normes d'un établissement particulier).
- Moteur autonome plus lourd (100 Mo) à cause de matplotlib et reportlab.

## 8. Vérifications manuelles proposées

1. Ouvrir le rapport d'exemple .docx dans Word, accepter la mise à jour des champs : vérifier le sommaire, la numérotation et l'impression en noir et blanc.
2. Exporter un rapport sur vos propres analyses et comparer quelques valeurs avec l'écran des résultats.
3. Modifier une donnée après une analyse : l'export doit être bloqué jusqu'à ce que l'analyse soit relancée ou retirée.

## 9. Documentation mise à jour

`README.md` et ce document.

## 10. Phase suivante proposée

**Phase 7 : puissance et plan d'analyse.** Estimation de la taille d'échantillon et de la puissance pour les tests disponibles (t, proportions, corrélation), et plan d'analyse rédigé avant la collecte des données, relié aux hypothèses, puis repris dans le rapport.

```text
PHASE 6 TERMINÉE — En attente de validation avant le démarrage de la PHASE 7.
```
