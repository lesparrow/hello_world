# STATPFE Desktop : Phases 0 et 1, audit et architecture

Date : 22 novembre 2026
Statut : **proposition, en attente de validation**. Aucune fonctionnalité n'est implémentée à ce stade.

---

## 1. Objectif de la phase

Comprendre l'existant (dépôt, outils, contraintes), comparer les architectures raisonnables, en recommander une, et proposer un plan par phases avec un MVP testable auprès d'étudiants en PFE et doctorat.

---

## 2. Ce qui a été observé

### 2.1 Le dépôt `lesparrow/hello_world`

| Élément | Constat |
|---|---|
| Fichiers | Un seul fichier, `text.txt` (2 lignes : « hello jack sparrow », « good »). |
| Historique | 5 commits d'exercice Git (ajout de lignes, résolution d'un conflit). |
| Branches | `main` et `claude/project-thread-0f8i5h`, identiques. |
| Instructions existantes | Aucune (pas de README, CLAUDE.md, licence, CI, dépendances). |
| Code STATPFE existant | **Aucun.** Rien à réutiliser ni à migrer. |

Conclusion : le dépôt est un bac à sable Git. On part d'une page blanche, ce qui laisse le choix d'architecture entièrement libre et sans dette.

### 2.2 Environnement de développement disponible (conteneur cloud Linux)

| Outil | Disponibilité |
|---|---|
| Python | 3.13 installé ; `numpy`, `pandas`, `openpyxl`, `python-docx` déjà présents |
| PyPI | Accessible : `scipy`, `statsmodels`, `PySide6` téléchargés avec succès |
| R | **Absent**, et non installable via `apt` dans ce conteneur |
| Node 22, Rust (cargo), Java | Présents |
| Wine / outils d'installation Windows | **Absents** |
| Machine | 4 cœurs, 15 Go de RAM, pas de GPU |

Conséquences honnêtes :

- **Le build Windows ne peut pas être produit ni testé dans ce conteneur.** Il faudra un runner Windows (GitHub Actions `windows-latest`, gratuit pour un dépôt public) et un test manuel sur un vrai PC Windows.
- **La comparaison avec R ne peut pas tourner ici.** Elle sera faite dans la CI (runner avec R installé) qui produira des fichiers de résultats de référence versionnés dans le dépôt.
- **L'IA locale ne peut pas être évaluée ici** (pas de GPU, pas de modèle). Elle reste en Phase 8, comme prévu.

### 2.3 État du moteur statistique et de l'IA

- Moteur statistique : inexistant.
- IA locale : inexistante.

---

## 3. Options d'architecture comparées

Critères issus du cahier des charges : fiabilité des calculs, fonctionnement 100 % local, maintenabilité par une petite équipe, packaging Windows d'abord, validation scientifique, rapports Word/PDF.

### Option A : Python seul, interface Qt (PySide6) — **recommandée**

- Moteur : `scipy.stats` + `statsmodels` (licences BSD, largement validées, utilisées en recherche).
- Données : `pandas` + `openpyxl` (Excel) ; `pyreadstat` pour SPSS plus tard.
- Interface : PySide6 (Qt 6, licence LGPL, compatible distribution commerciale).
- Graphiques : `matplotlib` (qualité publication, niveaux de gris, export SVG/PNG/PDF).
- Rapports : `python-docx` pour Word ; PDF via le moteur d'impression de Qt.
- Packaging : PyInstaller (ou Briefcase) + installateur Inno Setup, construit sur runner Windows.

| Avantages | Limites / risques |
|---|---|
| Un seul langage de bout en bout, moteur et interface. | Interface moins « web moderne » qu'Electron, mais tout à fait professionnelle. |
| Les calculs viennent directement de bibliothèques reconnues, sans couche réseau interne. | Installateur volumineux (environ 150 à 300 Mo). |
| Moteur testable sans l'interface (`pytest`). | Démarrage un peu plus lent qu'une application native. |
| Fonctionne hors ligne, aucun serveur local ni port ouvert. | |
| Linux et macOS possibles plus tard avec le même code. | |

### Option B : interface web (Tauri ou Electron, TypeScript) + moteur Python en processus séparé

| Avantages | Limites / risques |
|---|---|
| Interface très moderne, riche écosystème de composants. | Deux langages, deux chaînes de build, un protocole interne à sécuriser. |
| | Packaging Python embarqué + webview : la partie la plus fragile du projet sur Windows. |
| | Coût de maintenance environ doublé pour une petite équipe. |

À reconsidérer seulement si l'interface Qt se révèle bloquante après le MVP. Le moteur de l'option A étant indépendant de l'interface, ce changement resterait possible sans réécrire les calculs.

### Option C : R + Shiny en local

| Avantages | Limites / risques |
|---|---|
| R est la référence statistique. | Packaging desktop d'une appli Shiny sur Windows peu fiable et lourd. |
| | Interface navigateur, gestion de projets et de fichiers maladroite. |
| | Moins de développeurs disponibles pour maintenir. |

R est mieux utilisé comme **référence de validation** (en CI) que comme moteur embarqué.

### Option D : application web hébergée

Rejetée : contraire à l'exigence « les données de recherche restent sur l'ordinateur de l'utilisateur ».

### Synthèse

| Critère | A (Python/Qt) | B (Tauri+Python) | C (R/Shiny) | D (Web) |
|---|---|---|---|---|
| Fiabilité des calculs | ●●● | ●●● | ●●● | ●●● |
| Local / confidentialité | ●●● | ●●● | ●●● | ● |
| Simplicité / maintenance | ●●● | ● | ●● | ●● |
| Packaging Windows | ●● | ● | ● | n/a |
| Qualité d'interface | ●● | ●●● | ● | ●●● |

---

## 4. Architecture recommandée (option A)

### 4.1 Découpage en couches

```text
statpfe/
  core/        Modèle du projet, versions de données, journal, format de fichier
  data/        Import CSV/Excel, détection de types, dictionnaire, transformations
  engine/      Méthodes statistiques (pures, sans interface), diagnostics, avertissements
  advisor/     Assistant méthodologique déterministe (règles explicites)
  report/      Génération Word/PDF, contrôles de cohérence avant export
  ai/          (Phase 8) Module optionnel, désactivable, n'accède qu'aux résultats déjà calculés
  ui/          Interface PySide6, ne fait aucun calcul
tests/
  engine/      Tests unitaires + cas limites
  reference/   Jeux de données de référence + résultats attendus produits par R
```

Règle structurante : **l'interface n'appelle que `core`, `data`, `engine`, `advisor` et `report`**. Toute valeur numérique affichée provient d'un objet résultat produit par `engine`.

### 4.2 Contrat d'une méthode statistique

Chaque méthode est une classe déclarant : description, objectif, variables requises (avec niveau de mesure), conditions d'utilisation, paramètres, diagnostics, et un résultat structuré (statistique, ddl, p, IC, taille d'effet, n utilisés, traitement des manquants, avertissements). Une méthode n'apparaît dans l'interface que si elle est marquée `validated=True`, ce qui exige que ses tests de référence passent.

### 4.3 Format de projet `.statpfe`

Un fichier unique portable (archive ZIP) contenant :

- `project.sqlite` : métadonnées de l'étude, dictionnaire, plan d'analyse, analyses, journal, avertissements.
- `data/original/<hash>.parquet` : copie figée du fichier importé, identifiée par son empreinte SHA-256 (l'original de l'utilisateur n'est jamais modifié).
- `data/versions/` : versions dérivées, chacune décrite par la liste de transformations (JSON) qui permet de la recalculer depuis l'original.
- `figures/`, `reports/` : sorties générées.

Chaque analyse enregistre : version de données, transformations, méthode, paramètres, filtres, gestion des manquants, version de STATPFE et des bibliothèques (`scipy`, `statsmodels`), date. « Reproduire » consiste à rejouer ces éléments et comparer les résultats.

### 4.4 Validation scientifique

1. Jeux de données de référence publics (par ex. `sleep`, `mtcars`, `ToothGrowth`) et cas synthétiques (petits n, ex æquo, variance nulle, groupes déséquilibrés).
2. Un script R en CI calcule les résultats attendus et les enregistre en JSON dans `tests/reference/`.
3. Les tests Python comparent le moteur STATPFE à ces valeurs avec des tolérances explicites.
4. Points à surveiller dès le départ : corrections de continuité (Yates) du khi-deux, approximation normale vs exacte de Mann-Whitney et Wilcoxon, gestion des ex æquo, définition des tailles d'effet (d de Cohen vs g de Hedges, r rang-bisérial). Chaque convention sera documentée et alignée sur R.

### 4.5 Sécurité et confidentialité

- Aucun serveur local, aucun port ouvert, aucun appel réseau dans le MVP.
- Chemins de fichiers validés, écriture atomique des projets (fichier temporaire puis renommage) et sauvegarde automatique de la version précédente.
- Journal technique sans contenu des données.
- Détection simple des colonnes potentiellement identifiantes (noms, e-mails, téléphones) dès la Phase 3, masquage en aperçu.

### 4.6 IA locale (Phase 8, non engagée)

Piste : exécution locale via `llama.cpp` ou Ollama, modèle de petite taille, désactivée par défaut. Le module ne reçoit que des résultats déjà calculés et des métadonnées minimisées, jamais les données brutes ni les colonnes sensibles. Chaque texte produit est marqué « proposition générée par IA, à vérifier ».

### 4.7 Licences

Dépendances prévues sous licences permissives (BSD, MIT, LGPL pour Qt). À éviter : PyQt (GPL) et `pingouin` (GPL-3), qui imposeraient la GPL à STATPFE. Le choix de la licence de STATPFE lui-même (open source ou propriétaire) est à décider par le porteur du projet.

---

## 5. Risques identifiés

| Risque | Nature | Mitigation |
|---|---|---|
| Concurrence de **jamovi** et **JASP** (gratuits, open source, interface simple) | Produit | Se différencier sur ce qu'ils ne font pas bien : parcours guidé de la question de recherche au rapport PFE en français, assistant méthodologique expliqué, rapport Word prêt à intégrer, traçabilité. À valider auprès d'étudiants dès le MVP. |
| Erreurs de convention statistique | Scientifique | Validation systématique contre R en CI, conventions documentées. |
| Packaging Windows fragile | Technique | Build sur runner Windows dès la Phase 2, test manuel sur vrai PC à chaque jalon. |
| Antivirus signalant l'exécutable non signé | Distribution | Prévoir un certificat de signature de code avant diffusion large. |
| Périmètre très large pour une petite équipe | Projet | MVP resserré, méthodes avancées seulement après retour utilisateurs. |
| Données personnelles dans les enquêtes | Confidentialité | Fonctionnement local, détection des identifiants, pas de télémétrie. |

---

## 6. Plan de développement proposé

Les durées sont des ordres de grandeur pour une personne travaillant avec Claude Code, non des engagements.

| Phase | Contenu | Livrable vérifiable |
|---|---|---|
| 2. Socle | Squelette PySide6, créer/ouvrir/sauvegarder/fermer un projet `.statpfe`, CI (tests + build Windows) | Exécutable Windows qui crée et rouvre un projet |
| 3. Données | Import CSV/Excel, aperçu, dictionnaire, manquants, doublons, versions, transformations de base | Import d'un vrai fichier d'enquête sans perte |
| 4. Statistiques fondamentales | Descriptives, fréquences, tableaux croisés, histogramme, boxplot, t (Student, Welch, apparié), Mann-Whitney, Wilcoxon, Pearson, Spearman, khi-deux, Fisher, diagnostics | Tests de référence contre R au vert |
| 5. Assistant méthodologique | Arbre de décision explicite, justifications, alternatives, choix motivé enregistré | Recommandation affichée avec ses raisons |
| 6. Rapports | Rapport Word (puis PDF), tableaux et figures numérotés, contrôles avant export | Rapport ouvrable dans Word, cohérent avec l'écran |
| 7. Puissance et plan d'analyse | Taille d'échantillon, puissance, plan verrouillable | |
| 8. IA locale | Module optionnel | |
| 9. Distribution | Installateur signé, mises à jour, Linux/macOS si testés | |

### MVP à tester avec des étudiants : **fin de la Phase 6 simplifiée**

Le MVP couvre le parcours principal (section 6 du cahier des charges) avec un périmètre volontairement réduit :

- Projet d'étude (titre, problématique, objectifs, hypothèses).
- Import CSV et Excel, dictionnaire des variables, gestion des manquants, version de travail.
- Descriptives, fréquences, tableaux croisés, histogramme, boxplot.
- 6 tests validés contre R : t de Welch, t apparié, Mann-Whitney, khi-deux / Fisher, Pearson, Spearman.
- Assistant méthodologique simple pour ces 6 tests.
- Rapport Word avec méthodes, résultats, avertissements.
- Windows uniquement, sans IA.

Test proposé : 5 à 10 étudiants de PFE avec leurs propres données réelles, une séance d'observation chacun, puis priorisation de la suite selon leurs retours.

---

## 7. Dépôt : renommage conseillé

Le nom `hello_world` ne reflète pas le produit. Deux possibilités :

1. **Renommer le dépôt en `statpfe`** (GitHub, Settings → General → Repository name). GitHub redirige automatiquement l'ancienne adresse. Simple et recommandé.
2. Créer un nouveau dépôt `statpfe` vierge et y déplacer ce document, si l'on préfère ne pas garder l'historique d'exercice.

Le fichier `text.txt` n'a pas de lien avec le projet ; il pourra être supprimé au début de la Phase 2 avec votre accord.

---

## 8. Réponses au format demandé

1. **Objectif** : audit et choix d'architecture.
2. **Observé** : dépôt vide de code (un fichier d'exercice), Python 3.13 disponible, R et Windows absents de l'environnement.
3. **Décision proposée** : Python + PySide6 + scipy/statsmodels, validé contre R en CI, Windows d'abord.
4. **Fichiers concernés** : ce document et `README.md`.
5. **Implémenté** : rien de fonctionnel, volontairement.
6. **Tests exécutés** : aucun test applicatif (pas de code). Vérifié seulement la disponibilité des outils et des paquets.
7. **Limites** : build Windows et validation R impossibles dans ce conteneur, à faire en CI.
8. **Vérification manuelle** : relire ce document, valider ou modifier l'option retenue et le périmètre du MVP.
9. **Documentation** : ce document, `README.md`.
10. **Phase suivante proposée** : Phase 2, socle fonctionnel.

```text
PHASE 1 TERMINÉE — En attente de validation avant le démarrage de la PHASE 2.
```
