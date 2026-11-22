# STATPFE Desktop

Logiciel local d'analyse statistique guidée pour les étudiants en PFE, master et doctorat : de la question de recherche au rapport académique, avec des calculs fiables, une méthode expliquée et une traçabilité complète.

**État actuel : Phase 2 (socle).** On peut créer, modifier, enregistrer, dupliquer, fermer et rouvrir un projet d'étude. L'import de données et les analyses ne sont pas encore disponibles.

- Architecture : [docs/PHASE-1-AUDIT-ARCHITECTURE.md](docs/PHASE-1-AUDIT-ARCHITECTURE.md)
- Rapport de la Phase 2 : [docs/PHASE-2-SOCLE.md](docs/PHASE-2-SOCLE.md)

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
