# STATPFE Desktop : Phase 2, socle fonctionnel

Date : 22 novembre 2026
Statut : **terminée côté code, en attente de validation**.

## 1. Objectif de la phase

Lancer l'application, créer un projet d'étude, stocker ses informations et gérer proprement son cycle de vie (création, modification, enregistrement, copie, fermeture, réouverture), avec l'architecture validée en Phase 1 : interface React dans Tauri, moteur Python séparé.

## 2. Ce qui a été observé

Dépôt sans code au départ (Phase 1). L'environnement de développement (Linux) permet de compiler Tauri, de construire le moteur avec PyInstaller et de lancer l'application sous un écran virtuel. Il ne permet pas de produire ni de tester l'installateur Windows : c'est confié à la CI sur un runner Windows.

## 3. Décisions et justifications

| Décision | Justification |
|---|---|
| Fichier projet `.statpfe` = archive ZIP (`manifest.json` + `project.sqlite`) | Un seul fichier portable, facile à copier ou envoyer à un encadrant ; SQLite est robuste et lisible pendant des décennies. |
| Enregistrement atomique + copie `.statpfe.bak` de la version précédente | Un plantage ou une coupure pendant l'enregistrement ne peut pas corrompre le projet ; la version précédente reste récupérable. |
| Édition dans un dossier de travail temporaire, fermeture qui le supprime | Le fichier de l'utilisateur n'est modifié que lorsqu'il clique sur « Enregistrer ». |
| Version de format dans le manifeste ; refus clair d'un projet plus récent | Prépare les mises à jour sans risque de corrompre un projet ouvert avec une ancienne version. |
| Journal qui note quels champs ont changé, jamais leur contenu | Traçabilité sans dupliquer d'informations potentiellement sensibles. |
| Validation de toutes les entrées dans le moteur (titre obligatoire, longueurs, taille d'échantillon entière positive, chemins absolus avec extension `.statpfe`) | L'interface n'est pas une source de confiance ; les règles sont au même endroit pour l'interface et les tests. |
| Communication JSON-RPC sur stdin/stdout ; Tauri réécrit les identifiants de requête | Aucun port réseau ; un rechargement de l'interface ne peut pas mélanger les réponses. |
| Moteur redémarré automatiquement s'il s'arrête | Un plantage du moteur affiche une erreur compréhensible, sans figer l'application. |
| Permissions Tauri minimales (dialogues ouvrir/enregistrer, fermeture de fenêtre) et CSP stricte | L'interface ne peut ni lire ni écrire de fichiers elle-même ni charger de script distant. |
| Mantine (MIT) pour les composants, police Inter embarquée | Interface soignée, accessible, en français, et fonctionnement 100 % hors ligne. |
| Étapes futures (Données, Préparation, Analyses, Rapport) visibles mais grisées, avec leur phase | Règle du cahier des charges : aucun bouton actif qui ne fait rien. |

## 4. Fichiers concernés

```text
engine/statpfe/core/study.py       Informations de l'étude et validation
engine/statpfe/core/project.py     Format .statpfe, cycle de vie, enregistrement atomique
engine/statpfe/core/recent.py      Projets récents (chemin, titre, date uniquement)
engine/statpfe/rpc/server.py       Serveur JSON-RPC (stdin/stdout)
engine/statpfe/rpc/devbridge.py    Passerelle HTTP locale, développement uniquement
engine/packaging/                  Construction du moteur autonome (PyInstaller)
engine/tests/                      44 tests
apps/desktop/src/                  Interface React (accueil, nouveau projet, espace de travail)
apps/desktop/src-tauri/            Coquille Tauri (lancement du moteur, dialogues, sécurité)
.github/workflows/ci.yml           Tests Linux et Windows, installateur Windows, installation silencieuse
```

## 5. Ce qui a réellement été implémenté

- Écran d'accueil : nouveau projet, ouvrir un projet, projets récents (fichiers introuvables signalés, retrait de la liste sans suppression du fichier), version du moteur affichée.
- Assistant « Nouveau projet » en deux étapes (titre et problématique, puis objectifs et hypothèses) puis choix de l'emplacement.
- Espace de travail : fiche de l'étude (titre, problématique, objectifs, hypothèses H1, H2…, population, méthode d'échantillonnage avec suggestions, taille d'échantillon prévue), état « Enregistré » ou « Modifications non enregistrées », Enregistrer (Ctrl+S), Enregistrer une copie, Fermer.
- Confirmation avant de fermer le projet ou la fenêtre avec des modifications non enregistrées : enregistrer et fermer, fermer sans enregistrer, annuler.
- Journal du projet affiché dans l'espace de travail.
- Erreurs compréhensibles en français (fichier introuvable, endommagé, créé par une version plus récente, titre manquant…).

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 44 tests `pytest` (validation, aller-retour création / réouverture, enregistrement, copie, sauvegarde `.bak` restaurable, aucune donnée d'étude dans le journal, fichiers corrompus, archive non ZIP, format futur, entrée ZIP malveillante `../`, chemins invalides, protocole JSON-RPC, erreurs internes non divulguées, moteur lancé en processus séparé avec chemin accentué) | 44 réussis (Linux, Python 3.13) |
| Interface : 5 tests `vitest` + vérification de types TypeScript + build | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface + vrai moteur) : créer un projet, modifier, Ctrl+S, modifier puis fermer sans enregistrer, rouvrir depuis les récents et vérifier que seules les données enregistrées sont présentes | Réussi, aucune erreur dans la console |
| Application Tauri compilée en mode release sous Linux, lancée sous écran virtuel : le moteur autonome démarre, l'accueil affiche les projets récents, ouverture d'un projet réussie | Réussi (captures dans le dossier du projet) |
| Moteur autonome PyInstaller (Linux) : réponse à `engine.info` | Réussi, 12 Mo |
| Installateur Windows, installation et désinstallation silencieuses | Confié à la CI : voir le résultat du job « Installateur Windows » sur la PR |

## 7. Limites et points non terminés

- **Aucun test manuel sur un vrai PC Windows** n'a encore été fait. La CI vérifie la construction, l'installation et la désinstallation, mais pas l'affichage de l'interface sous Windows.
- L'installateur n'est **pas signé** : Windows SmartScreen affichera un avertissement au premier lancement.
- Si l'application est tuée brutalement, le dossier de travail temporaire peut rester sur le disque (le fichier projet, lui, n'est pas touché). Un nettoyage au démarrage sera ajouté.
- Aucun verrou n'empêche d'ouvrir le même projet dans deux instances de l'application.
- Le moteur est empaqueté en un seul fichier (PyInstaller `--onefile`) : démarrage un peu plus lent, et certains antivirus peuvent le surveiller. À réévaluer quand scipy et pandas seront ajoutés (Phase 3-4), car la taille augmentera.
- La restauration de la sauvegarde `.bak` se fait pour l'instant en la renommant en `.statpfe` ; une commande dans l'interface reste à ajouter.
- macOS et Linux ne sont pas distribués (Linux compile et fonctionne en développement).

## 8. Vérifications manuelles proposées

1. Télécharger l'artefact `statpfe-windows-installateurs` de la CI, installer STATPFE sur un PC Windows 10 ou 11.
2. Créer un projet, remplir la fiche, enregistrer, fermer l'application, la rouvrir et rouvrir le projet depuis les récents.
3. Modifier un champ puis fermer la fenêtre : vérifier que la confirmation apparaît.
4. Copier le fichier `.statpfe` sur une autre machine et l'ouvrir.

## 9. Documentation mise à jour

`README.md` (organisation, développement, construction) et ce document.

## 10. Phase suivante proposée

**Phase 3 : Données.** Import CSV et Excel, aperçu, détection des types, dictionnaire des variables, valeurs manquantes, doublons, version originale figée et versions de travail. C'est la phase qui ajoutera pandas au moteur.

```text
PHASE 2 TERMINÉE — En attente de validation avant le démarrage de la PHASE 3.
```
