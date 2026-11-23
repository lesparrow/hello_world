# Phase 9 : distribution Windows, Linux et macOS

## 1. Objectif de la phase

Livrer STATPFE comme une application ordinaire, sans Python ni R à installer, sur Windows, Linux et macOS ;
vérifier réellement l'installation, le lancement, la mise à jour (qui doit préserver les projets),
la désinstallation et les bibliothèques incluses.

## 2. Ce qui a été observé dans le dépôt

- Le moteur était déjà empaqueté en exécutable autonome (PyInstaller) et lancé par Tauri comme « sidecar ».
- Seul un installateur Windows était construit en CI, sans essai d'installation ni de mise à jour.
- Aucun moyen, pour un étudiant, de vérifier que les bibliothèques incluses fonctionnent sur sa machine.

## 3. Décisions prises et justifications

- **Formats** : Windows NSIS (par utilisateur, sans droits d'administrateur) et MSI (salles informatiques) ;
  Linux .deb, .rpm et AppImage ; macOS .app et .dmg. Ce sont les formats attendus par les étudiants et les services informatiques.
- **Linux construit sur Ubuntu 22.04** : la glibc la plus ancienne raisonnable, donc compatible avec les distributions de 2022 et plus récentes.
- **Diagnostic réel** (`engine.selfcheck`, écran « À propos et diagnostic ») : chaque bibliothèque est essayée sur un vrai calcul
  (numpy, scipy, pandas, openpyxl, matplotlib, python-docx, reportlab, sqlite), pas seulement importée.
- **Mise à jour testée** avec une version 0.1.1 construite exprès (`packaging/test-mise-a-jour.json`) : un projet créé avec 0.1.0
  est rouvert après installation de 0.1.1.
- **Pas de signature payante** à ce stade : signer exige un certificat d'éditeur (Windows) et un compte Apple Developer (macOS).
  Les avertissements sont documentés dans le guide d'installation au lieu d'être cachés.

## 4. Fichiers concernés

- `engine/statpfe/core/diagnostics.py`, `engine/statpfe/rpc/server.py` (engine.info, engine.selfcheck), `engine/tests/test_diagnostics.py`
- `apps/desktop/src/components/DiagnosticModal.tsx`, `apps/desktop/src/screens/Home.tsx`
- `apps/desktop/src-tauri/tauri.conf.json` (cibles, métadonnées, Linux, macOS)
- `packaging/engine_functional.py`, `packaging/linux-smoke.sh`, `packaging/test-mise-a-jour.json`
- `.github/workflows/ci.yml` (jobs « Installateur Windows », « Paquets Linux », « Paquet macOS », moteur sous macOS)
- `docs/INSTALLATION.md` (guide pour les étudiants), `docs/exemples/` (jeu de données de test)

## 5. Ce qui a réellement été implémenté

- Construction des 7 paquets (exe, msi, deb, rpm, AppImage, app, dmg) en CI, publiés comme artefacts.
- Pour chaque plateforme, un parcours réel : installation, diagnostic du moteur installé, projet créé (import CSV,
  test de Welch, calcul de puissance, rapports Word et PDF), lancement de l'application avec capture d'écran, désinstallation.
- Windows et .deb : mise à jour 0.1.0 → 0.1.1, puis réouverture du projet (étude, données, analyse, puissance, projets récents intacts) ;
  la désinstallation laisse projets et réglages.
- Écran « À propos et diagnostic » dans l'application.
- Guide d'installation (`docs/INSTALLATION.md`) et jeu de données de test avec résultats attendus (`docs/exemples/`).

## 6. Tests exécutés et résultats

CI, exécution 45088167135 (commit b2eaadd) : **11 jobs sur 11 réussis**.

| Job | Ce qui est vérifié | Résultat |
|---|---|---|
| Moteur Python (Ubuntu, Windows, macOS) | 365 tests | réussi |
| Validation contre R | statistiques et puissance | réussi |
| Interface React | typecheck, tests, build | réussi |
| Installateur Windows | NSIS : installation, diagnostic, parcours, lancement, mise à jour 0.1.1, désinstallation | réussi |
| Paquets Linux | .deb : installation, lancement sous Xvfb, mise à jour, désinstallation ; AppImage : lancement ; .rpm : installation et parcours sous Fedora (conteneur) | réussi |
| Paquet macOS | .dmg : installation, lancement, désinstallation (Apple Silicon) | réussi |
| IA locale, Claude Code (Ubuntu, Windows) | téléchargement réel d'un modèle, installation réelle de Claude Code | réussi |

En local (Ubuntu) : .deb installé, lancé, mis à jour et désinstallé ; AppImage lancée (captures `p9-01`, `p9-02`).

## 7. Limites et points non terminés

- **Windows** : installateurs non signés, donc avertissement SmartScreen au premier lancement. Le MSI est construit mais son installation n'est pas testée en CI (seul le NSIS l'est).
- **macOS** : signature ad hoc seulement, **non notarisé** (clic droit > Ouvrir nécessaire). Apple Silicon uniquement ; les Mac Intel ne sont pas pris en charge.
  La mise à jour n'est pas testée sous macOS.
- **Linux** : .rpm testé dans un conteneur Fedora **sans affichage** (moteur et parcours, pas l'interface) ; AppImage testée sans FUSE
  (`APPIMAGE_EXTRACT_AND_RUN=1`). Pas de mise à jour automatique : il faut installer la nouvelle version.
- Les tests tournent sur les machines virtuelles de GitHub, pas sur des ordinateurs d'étudiants réels (anciens Windows 10, faible mémoire, antivirus).
- La connexion réelle à un compte Claude n'est pas testée en CI (elle demande un compte) ; l'installation de Claude Code, elle, l'est.

## 8. Vérifications manuelles proposées

1. Télécharger l'artefact `statpfe-windows-installateurs`, installer sur un vrai PC Windows 10 ou 11, passer SmartScreen, ouvrir « À propos et diagnostic ».
2. Sur un Mac à puce Apple, installer le `.dmg`, ouvrir par clic droit > Ouvrir.
3. Suivre `docs/exemples/GUIDE-DE-TEST.md` avec le jeu de données et comparer aux résultats attendus.
4. Créer un projet, installer par-dessus une version suivante, vérifier que le projet s'ouvre.

## 9. Documentation mise à jour

`README.md`, `docs/INSTALLATION.md`, `docs/PHASE-9-DISTRIBUTION.md`, `docs/exemples/GUIDE-DE-TEST.md`.

## 10. Phase suivante proposée

Les 9 phases prévues sont terminées. Suites possibles, par ordre d'utilité pour les étudiants :
- essais avec de vrais étudiants sur leurs ordinateurs, puis corrections ;
- ANOVA, Kruskal-Wallis et régressions (linéaire, logistique), très demandées en PFE et en thèse ;
- signature des installateurs (certificat Windows, notarisation Apple) et version pour Mac Intel ;
- mise à jour automatique intégrée.
