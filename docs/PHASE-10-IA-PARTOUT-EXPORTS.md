# Phase 10 : l'IA aide partout, exports en couleurs, LaTeX, images et Excel

## 1. Objectif de la phase

Faire de l'IA (optionnelle, désactivée par défaut) un assistant présent sur chaque écran : elle remplit la
fiche de l'étude, complète le dictionnaire et propose le nettoyage, propose le plan d'analyse et le choix des
tests, la taille d'échantillon, et rédige la discussion, les limites et la conclusion. Sans jamais calculer,
sans rien modifier sans accord, et avec une vérification par le moteur de chaque proposition.
Ajouter des rapports en couleurs (avec un thème « sobre »), l'export LaTeX pour Overleaf, l'export des
graphiques en images et des tableaux en Excel.

## 2. Ce qui a été observé dans le dépôt

- L'IA de la phase 8 ne rédigeait que sous un résultat d'analyse ; aucun autre écran n'en profitait.
- L'assistant méthodologique (phase 5) donnait déjà une recommandation déterministe : il pouvait servir
  d'arbitre pour les tests proposés par l'IA.
- Le contrôle des nombres (`guard.check`) existait pour les textes de l'IA et pouvait être réutilisé.
- Les rapports étaient en noir et blanc, en Word et PDF seulement ; les graphiques et tableaux n'étaient
  disponibles qu'à l'intérieur du rapport.

## 3. Décisions prises et justifications

- **L'IA propose, le moteur vérifie, l'étudiant applique.** Chaque demande produit une proposition
  structurée (JSON, imposé à Ollama par `format: "json"`), lue puis validée par le moteur avant d'être
  montrée. Rien n'est écrit dans le projet avant le bouton « Appliquer ».
- **Mention « Proposé par l'IA, à valider »** sur chaque élément appliqué (champ de l'étude, variable,
  version de données, plan, calcul de puissance, section du rapport). Elle disparaît quand l'étudiant
  valide ou modifie l'élément. Le contrôle du rapport signale les éléments non validés, et les textes
  non relus sont imprimés avec la mention « proposition NON ENCORE RELUE ».
- **Annulation complète** d'une application tant que rien n'a été modifié ou validé depuis
  (sinon l'annulation automatique écraserait le travail de l'étudiant : elle est alors refusée, avec la raison).
- **Choix des tests arbitré par le moteur** : chaque analyse proposée est confrontée à l'assistant
  méthodologique et reçoit un verdict (conforme, acceptable, écart, impossible). Les analyses impossibles
  ne peuvent pas être ajoutées ; en cas d'écart, la recommandation du moteur peut remplacer celle de l'IA en un clic.
- **Aucun chiffre inventé** : taille d'échantillon proposée sans être donnée par l'étudiant écartée ;
  taille d'effet repère de Cohen signalée ; l'effectif est calculé par le moteur ; un texte du rapport
  contenant un nombre absent des résultats ne peut pas être appliqué tel quel.
- **Données jamais transmises ligne à ligne** : seulement le dictionnaire, les effectifs des modalités
  (15 au plus par variable) et les résultats calculés ; les identifiants sont exclus. Le bouton
  « Voir ce qui sera transmis » montre le texte exact avant envoi.
- **Recodages dans une nouvelle version** « Préparée avec l'IA » : l'original reste intact.
- **Lancement du plan en un clic** : uniquement pour un plan verrouillé (le pré-enregistrement garde son sens).
- **Thèmes** bleu (par défaut), vert, bordeaux et sobre (noir et blanc avec hachures) ; palette Okabe-Ito
  pour les séries, lisible par les daltoniens.
- **LaTeX** : un .zip (`rapport.tex`, figures PNG, mode d'emploi) qui compile sur Overleaf avec pdflatex.

## 4. Fichiers concernés

- Moteur : `engine/statpfe/ai/copilot.py` (nouveau), `ai/service.py`, `ai/client.py`, `ai/jobs.py`,
  `core/plan_runner.py` (nouveau), `core/project.py` (format v7), `rpc/server.py`,
  `report/theme.py`, `report/render_latex.py`, `report/exports.py` (nouveaux), `report/charts.py`,
  `report/build.py`, `report/render_docx.py`, `report/render_pdf.py`, `report/options.py`,
  `report/service.py`, `report/checks.py`
- Interface : `components/ai/Copilot.tsx`, `components/ai/Assistant.tsx`, `screens/report/ReportTexts.tsx`
  (nouveaux), `screens/Workspace.tsx`, `StudyPage.tsx`, `data/DictionaryPanel.tsx`, `plan/PlanPage.tsx`,
  `power/PowerPage.tsx`, `report/ReportPage.tsx`, `analysis/ResultView.tsx`, `engine/types.ts`, `lib/files.ts`
- Tests : `engine/tests/test_copilot.py`, `test_exports.py`, `test_copilot_live.py` (nouveaux)
- CI : `.github/workflows/ci.yml` (job LaTeX avec TeX Live, copilote avec un vrai modèle Ollama)

## 5. Ce qui a réellement été implémenté

| Écran | Ce que fait l'IA | Ce que vérifie le moteur |
|---|---|---|
| Étude | Remplit ou améliore titre, problématique, objectifs, population, échantillonnage, hypothèses | Format de l'étude ; nombres absents du sujet signalés ; taille d'échantillon inventée écartée |
| Données (dictionnaire) | Libellés, niveaux, rôles, unités, codes manquants ; recodage des modalités mal saisies | Niveau compatible avec le type ; codes et modalités réellement observés ; nom unique |
| Plan d'analyse | Une analyse par hypothèse, variables de chaque rôle, justification, traitement des manquants | Verdict de l'assistant méthodologique pour chaque analyse ; hypothèses non couvertes signalées |
| Puissance | Plan de calcul, taille d'effet, seuil, puissance | Paramètres validés ; effectif calculé par le moteur ; repère de Cohen signalé |
| Rapport | Discussion, limites, conclusion | Chaque nombre comparé aux résultats ; nombres absents surlignés et bloquants |
| Partout | « Demander à l'IA » : question libre sur l'écran ouvert, avec lien vers l'aide adaptée | Nombres absents du contexte signalés |

- **Assistant complet** : le parcours en 7 étapes (étude, données, plan, verrouillage et lancement,
  puissance, rédaction, exports), avec l'état de chaque étape et l'action IA correspondante.
- **Rédaction du rapport** éditable sur l'écran Rapport, même sans IA (les textes de l'étudiant remplacent
  les emplacements « à rédiger »).
- **Exports** : rapport Word, PDF ou LaTeX en 4 thèmes ; tableaux en Excel (une feuille par analyse, nombres
  réels avec leur format) ; graphiques en PNG 300 dpi ou SVG, un par un depuis un résultat ou tous à la fois.

## 6. Tests exécutés et résultats

- Moteur : **384 tests réussis**, 6 ignorés (essais avec vrai modèle ou Claude Code, exécutés dans le CI).
  Dont 9 tests du copilote (avec un serveur de modèle factice : contexte, lecture, validation, application,
  mention, validation, annulation, refus) et 9 tests d'exports, dont la compilation pdflatex du .zip LaTeX
  dans chacun des 4 thèmes.
- Interface : vérification des types TypeScript et 8 tests vitest réussis.
- **Parcours complet dans le navigateur** (Playwright, 14 captures dans `captures-phase10/`) : étude
  remplie, dictionnaire complété et nettoyé, plan proposé et vérifié, verrouillé puis 5 analyses lancées
  en un clic, taille d'échantillon, rédaction, question libre, assistant complet. Ces captures utilisent un
  **modèle factice** aux réponses fixées : elles montrent l'interface, pas la qualité d'un vrai modèle.
- CI : nouveau job « Export LaTeX compilé avec pdflatex » ; le job Ollama essaie désormais le copilote
  avec un vrai petit modèle (qwen2.5:0.5b) et publie ses propositions.

## 7. Limites et points non terminés

- **Qualité des propositions** : elle dépend du modèle. Un petit modèle local (moins de 7 milliards de
  paramètres) renvoie souvent un JSON incomplet (« réponse illisible ») ou des choix discutables ; le moteur
  les arrête, mais ne les rend pas meilleurs. Un modèle de 7 à 8 milliards de paramètres ou Claude est conseillé.
- La vérification du plan se limite aux règles de l'assistant méthodologique (types, appariement,
  effectifs, normalité indicative) ; elle ne juge pas la pertinence scientifique d'une hypothèse.
- Le contrôle des nombres vérifie leur présence dans les résultats, pas qu'ils soient attribués à la bonne analyse.
- pdflatex ne gère pas l'arabe ni les emoji : ces caractères deviennent « ? » dans le .tex (le rapport Word
  et PDF les gardent). XeLaTeX n'est pas encore proposé.
- L'ANOVA reste indisponible : l'IA ne peut pas la proposer.
- Rien n'a été testé avec un vrai grand modèle local dans cette session ; le CI essaie seulement qwen2.5:0.5b.

## 8. Vérifications manuelles proposées

1. Avec l'IA désactivée, vérifier que chaque bouton IA ouvre une fenêtre qui l'explique et renvoie aux réglages.
2. Avec un modèle local, remplir l'étude depuis un sujet de deux lignes, appliquer, puis modifier un champ : la mention disparaît.
3. Données de test : « Compléter et nettoyer » doit proposer le recodage de `sexe` ; vérifier la nouvelle version (149 lignes après les autres étapes du guide).
4. Proposer le plan, vérifier les verdicts, verrouiller, puis « Lancer toutes les analyses prévues ».
5. Exporter le .zip LaTeX et le compiler sur Overleaf ; exporter les tableaux Excel et les graphiques SVG.

## 9. Documentation mise à jour

- `README.md` (état actuel), ce rapport, `docs/INSTALLATION.md` inchangé.

## 10. Phase suivante proposée

Phase 11 : ANOVA et Kruskal-Wallis (avec comparaisons multiples), régression linéaire et logistique,
validées contre R, pour que l'IA et l'assistant puissent les proposer.
