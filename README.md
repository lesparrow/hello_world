# STATPFE Desktop

Logiciel local d'analyse statistique guidée pour les étudiants en PFE, master et doctorat : de la question de recherche au rapport académique, avec des calculs fiables, une méthode expliquée et une traçabilité complète.

**État actuel : Phase 8 (IA optionnelle : locale ou Claude Code).** On peut créer et rouvrir un projet d'étude, importer des données CSV ou Excel, corriger le dictionnaire des variables, préparer des versions de travail, puis lancer des analyses : descriptives, fréquences, tableaux croisés, tests t (Student, Welch, apparié), Mann-Whitney, Wilcoxon, corrélations de Pearson et Spearman, khi-deux et Fisher. Chaque méthode est validée contre R en CI, et chaque analyse enregistre la version et l'empreinte des données utilisées. Un assistant déterministe (sans IA) recommande une méthode et enregistre le choix final avec sa justification. Les rapports Word et PDF (PFE, mémoire, thèse, article, enquête) sont produits à partir des résultats enregistrés, après des contrôles de cohérence qui recalculent chaque analyse. Le calcul de taille d'échantillon et de puissance (tests t, deux proportions, khi-deux, corrélation) reproduit le paquet R pwr, vérifié en CI. Un plan d'analyse se rédige avant l'analyse finale, se verrouille et garde l'historique de ses versions ; le rapport distingue les analyses prévues de celles ajoutées après avoir vu les données. Une IA optionnelle, désactivée par défaut (locale avec Ollama ou un serveur compatible OpenAI, ou Claude Code en ligne après autorisation explicite), aide à expliquer et à rédiger à partir des résultats déjà calculés ; chaque nombre qu'elle écrit est vérifié, et seuls les textes relus et retenus entrent dans le rapport, signalés comme tels.

- Architecture : [docs/PHASE-1-AUDIT-ARCHITECTURE.md](docs/PHASE-1-AUDIT-ARCHITECTURE.md)
- Rapport de la Phase 2 : [docs/PHASE-2-SOCLE.md](docs/PHASE-2-SOCLE.md)
- Rapport de la Phase 3 : [docs/PHASE-3-DONNEES.md](docs/PHASE-3-DONNEES.md)
- Rapport de la Phase 4 : [docs/PHASE-4-STATISTIQUES.md](docs/PHASE-4-STATISTIQUES.md)
- Rapport de la Phase 5 : [docs/PHASE-5-ASSISTANT.md](docs/PHASE-5-ASSISTANT.md)
- Rapport de la Phase 6 : [docs/PHASE-6-RAPPORTS.md](docs/PHASE-6-RAPPORTS.md)
- Rapport de la Phase 7 : [docs/PHASE-7-PUISSANCE-PLAN.md](docs/PHASE-7-PUISSANCE-PLAN.md)
- Rapport de la Phase 8 : [docs/PHASE-8-IA-LOCALE.md](docs/PHASE-8-IA-LOCALE.md)

## Organisation

```text
engine/              Moteur Python (projets, puis données et statistiques). Aucun code d'interface.
apps/desktop/        Interface React + TypeScript (Mantine)
apps/desktop/src-tauri/  Coquille Tauri (Rust) : fenêtre, dialogues, lancement du moteur
.github/workflows/   Tests et construction de l'installateur Windows
```

## Développement

Prérequis : Python 3.11 ou plus, Node 22, Rust stable. Sous Linux, les bibliothèques WebKitGTK de Tauri (`libwebkit2gtk-4.1-dev`, voir la documentation Tauri).

```bash
# Moteur
cd engine
pip install -e ".[dev]"
python -m pytest

# Valeurs de référence calculées par R (R de base, sans paquet)
Rscript tests/reference/r_reference.R

# Interface
cd apps/desktop
npm ci
npm test
npm run typecheck
```

### Lancer l'application de bureau (développement)

```bash
cd engine && python packaging/build_sidecar.py   # une fois : requis par la configuration Tauri
cd apps/desktop && npx tauri dev
```

En mode développement, Tauri lance le moteur avec `python -m statpfe` depuis `engine/`
(variable `STATPFE_PYTHON` pour choisir l'interpréteur).

### Travailler sur l'interface dans un navigateur

```bash
export STATPFE_DEV_TOKEN=un-secret-local
(cd engine && python -m statpfe.rpc.devbridge) &
(cd apps/desktop && npx vite)
# puis ouvrir http://localhost:5173
```

La passerelle de développement n'écoute que sur 127.0.0.1, exige le jeton, et n'est jamais incluse dans l'application distribuée.

### Construire l'installateur Windows

Il est produit automatiquement par la CI (job « Installateur Windows ») et téléchargeable dans les artefacts de l'exécution GitHub Actions. En local sous Windows :

```bash
cd engine && pip install pyinstaller && python packaging/build_sidecar.py
cd apps/desktop && npm ci && npx tauri build
```
