# Phase 8 : IA locale (optionnelle)

## 1. Objectif de la phase

Ajouter un module d'IA facultatif, une fois le logiciel complet sans lui (cahier des charges §3.3, §16 et §17). Il doit expliquer une méthode, un tableau ou une figure, reformuler, proposer un paragraphe prudent, aider à discuter, repérer les limites visibles et formuler une conclusion. Il ne doit jamais calculer, inventer un nombre, modifier les données ou une analyse, remplacer l'assistant déterministe, se présenter comme une validation, ni envoyer des données hors de l'ordinateur. Il faut aussi vérifier les ressources de la machine, gérer l'absence de modèle, permettre de tout désactiver, minimiser ce qui est transmis, exclure les colonnes identifiantes et signaler chaque texte comme une proposition à vérifier.

## 2. Ce qui a été observé dans le dépôt

- Le moteur traite une requête à la fois (JSON-RPC sur stdin/stdout, SQLite sur un seul fil). Or une rédaction par un modèle sur processeur peut durer une minute.
- Les résultats enregistrés contiennent déjà tout ce qu'il faut expliquer (indicateurs, tableaux, descriptions textuelles des figures, diagnostics, lecture déterministe). Les variables identifiantes sont déjà repérées et bloquées en analyse depuis la Phase 3.
- Le contrôle avant export affichait « aucun texte généré par IA » : il fallait le remplacer par un vrai contrôle.
- Dans ce conteneur, aucun modèle n'est téléchargeable (Hugging Face et le registre Ollama sont bloqués par le réseau). L'essai avec un vrai modèle est donc fait dans le CI GitHub, qui a accès à Internet.

## 3. Décisions prises et justifications

| Décision | Justification |
|---|---|
| Le modèle tourne dans un serveur déjà répandu, installé par l'utilisateur : **Ollama** (conseillé), ou tout serveur **compatible OpenAI** (llama.cpp, LM Studio). | Ollama s'installe en un clic sous Windows et gère les modèles (`ollama pull qwen2.5:3b`). Embarquer un modèle de 2 à 5 Go dans l'installateur et un moteur d'inférence compilé dans PyInstaller alourdirait fortement l'application pour une fonction facultative. |
| **Seule la boucle locale** est acceptée (127.0.0.1, localhost, ::1), en http, sans chemin ni identifiants. `localhost` est contacté par 127.0.0.1 (pas de résolution DNS), les mandataires (proxy) du système sont ignorés et les redirections refusées. | Rien ne peut quitter l'ordinateur, même par une variable d'environnement ou une redirection. |
| L'IA est **désactivée par défaut** ; les réglages sont propres à l'application (dossier de configuration), pas aux projets. Un fichier de réglages altéré fait revenir aux réglages sûrs (IA désactivée). | « L'application doit rester fonctionnelle sans IA. » |
| **Contexte minimisé et visible** : méthode, noms et libellés des variables analysées, n, indicateurs, tableaux de synthèse (30 lignes au plus), descriptions des figures, diagnostics, lecture déterministe, hypothèse liée et lien au plan. Jamais de données brutes, de variable identifiante (refus explicite), de note libre, de titre d'étude ni de noms d'auteurs. Un bouton « Voir ce qui sera transmis » affiche le texte exact. | §16 : contenu contrôlé et minimisé. L'utilisateur peut vérifier lui-même. |
| **Contrôle de chaque nombre** du texte produit : il doit figurer dans le contexte transmis, éventuellement arrondi correctement (4,146 → 4,15 ou 4,1, mais pas 4,1460 ni 4,2). Les petits entiers (0 à 10) et les étiquettes (H1, Q3) sont admis. Un texte qui contient un nombre non retrouvé **ne peut pas être retenu** tant que l'utilisateur ne l'a pas corrigé. | « L'IA ne doit jamais inventer un nombre. » On ne peut pas l'empêcher de le tenter, mais on peut l'empêcher d'atteindre le rapport. |
| Avertissements, sans blocage, pour les formulations à risque : « prouve », « démontre », lien de cause à effet, « absence d'effet », « validé scientifiquement », références ou dates citées. | Ces formulations sont des erreurs fréquentes en PFE ; c'est à l'auteur de trancher. |
| Consignes système prudentes, versionnées (`PROMPT_VERSION`), température 0,2 et graine fixée ; le contenu placé entre balises est déclaré comme donnée (protection contre les instructions cachées dans un libellé). | Reproductibilité autant que possible ; traçabilité des consignes. |
| La rédaction tourne **dans un fil séparé** qui ne parle qu'au serveur de modèles (pas au projet ni à SQLite). L'interface suit l'avancement, voit le texte s'écrire et peut annuler. Une seule rédaction à la fois. | Le moteur reste réactif pendant la rédaction. |
| **Traçabilité** : chaque proposition terminée est enregistrée dans le projet (format 6, table `ai_texts`) avec le texte exact transmis, son empreinte, le modèle, les réglages, la version des consignes, le texte brut et le texte affiché. Statuts : proposition, retenue (après case « J'ai relu et vérifié », modification possible), écartée. Journal : « ia ». | « Chaque texte généré doit être identifié comme une proposition à vérifier. » |
| **Rapport** : seuls les textes retenus y figurent, encadrés et précédés de « Texte rédigé avec l'aide d'une IA locale (tâche ; modèle ; date), relu et retenu par l'auteur [puis modifié] ». L'annexe de traçabilité indique, par analyse, le nombre de propositions et de textes retenus, et un paragraphe « Utilisation de l'intelligence artificielle » résume l'usage (ou indique qu'il n'y en a pas). Option pour ne pas les inclure. | §17 : identification des textes générés par IA avant export. |
| **Contrôles avant export** : texte retenu dont un nombre n'est plus retrouvé (modifié dans le fichier) : bloquant ; contexte de l'analyse modifié depuis la proposition : important ; propositions non relues : information. | Même logique que les autres contrôles : rien d'invérifiable n'entre dans le rapport. |
| Conseil de taille de modèle selon la mémoire (moins de 4 Go : déconseillé ; 4 Go : 1 à 2 milliards de paramètres ; 8 Go : 3 à 4 ; 16 Go : 7 à 8), avec avertissements (mémoire libre, disque). Mémoire lue par l'API Windows, `/proc/meminfo` ou `sysctl`. | §16 : vérifier les ressources de la machine. |

## 4. Fichiers concernés

- Moteur, nouveau module `engine/statpfe/ai/` : `settings.py` (réglages, adresse locale), `client.py` (HTTP local, Ollama et OpenAI, flux), `system.py` (ressources, conseil), `context.py` (contexte minimisé), `prompts.py` (consignes et 7 demandes), `guard.py` (contrôle des nombres et des formulations), `jobs.py` (rédaction en arrière-plan, annulation), `store.py` (propositions dans le projet), `service.py`.
- Moteur, modifiés : `core/project.py` (format 6, migration), `stats/store.py` (suppression d'une analyse : ses propositions aussi), `rpc/server.py` (11 méthodes `ai.*`, annulation à la fermeture), `report/build.py`, `report/checks.py`, `report/options.py`, `report/render_docx.py`, `report/render_pdf.py`, `report/model.py` (style « ai »).
- Interface : `screens/ai/AiSettingsPage.tsx` (réglages), `screens/analysis/AiAssistPanel.tsx` (aide sous chaque résultat), `ResultView.tsx`, `AnalysesPage.tsx`, `Workspace.tsx` (entrée « IA locale »), `ReportPage.tsx` (option), `engine/types.ts`, `lib/format.ts`.
- Tests : `tests/test_ai.py` (41 tests), `tests/fake_model_server.py` (serveur factice pour les tests), `tests/test_ai_live.py` (vrai modèle, CI).
- CI : nouveau job « IA locale avec un vrai modèle (Ollama) » ; le test du moteur autonome Windows vérifie aussi `ai.status`.

## 5. Ce qui a réellement été implémenté

- Page **IA locale** : ce que fait l'IA et ce qu'elle ne fait jamais, interrupteur (désactivée par défaut), type de serveur, adresse (refus de toute adresse non locale), test de connexion, choix parmi les modèles installés, ressources de l'ordinateur et taille de modèle conseillée, réglages avancés (température, longueur, délai). Messages guidés selon l'état : serveur absent (installer Ollama et un modèle), aucun modèle, modèle absent, prête.
- Sous chaque résultat, panneau **Aide à la rédaction** : 7 demandes (expliquer la méthode ; expliquer les tableaux et figures ; paragraphe de résultats ; pistes de discussion ; limites visibles ; conclusion ; reformuler mon texte), aperçu exact du contexte, texte qui s'écrit en direct, annulation, puis proposition avec nombres non retrouvés surlignés, avertissements de formulation, modification libre avec nouveau contrôle à la volée, case de relecture obligatoire, « Retenir pour le rapport » (refusé tant qu'un nombre n'est pas retrouvé) ou « Écarter ». Historique des propositions de l'analyse. Quand l'IA est désactivée, le panneau le dit et tout le reste fonctionne.
- Rapport Word et PDF : textes retenus encadrés et signalés, résumé par analyse dans l'annexe, paragraphe « Utilisation de l'intelligence artificielle », contrôles avant export, option d'exclusion.

## 6. Tests exécutés et résultats

| Test | Résultat |
|---|---|
| Moteur : 345 tests `pytest` (dont 41 nouveaux pour l'IA) ; 2 tests « vrai modèle » ignorés ici faute de modèle | 345 réussis (Linux, Python 3.13) |
| IA (serveur factice) : désactivée par défaut ; 9 adresses non locales refusées (réseau local, nom de domaine, https, identifiants, chemin, 0.0.0.0…) ; mandataire système ignoré ; réglages altérés → IA désactivée ; 6 états de connexion ; protocoles Ollama et OpenAI ; aucune donnée brute ni nom ni adresse électronique dans ce qui est envoyé ; refus si une variable devient identifiante ; 12 cas du contrôle des nombres ; avertissements ; raisonnement `<think>` retiré ; nombre inventé → texte non retenable ; relecture obligatoire ; enregistrement unique ; annulation ; une rédaction à la fois ; erreurs lisibles ; rapport (texte signalé, annexe, contrôle bloquant si le texte est altéré, option d'exclusion, export Word et PDF) ; suppression d'une analyse ; migration d'un projet au format 5 | Réussis |
| Interface : typecheck, 8 tests `vitest`, build | Réussis |
| Parcours de bout en bout dans Chromium (vraie interface, vrai moteur, **serveur de modèles factice** dont la réponse contient volontairement un nombre inventé et une formulation causale) : IA désactivée, adresse extérieure refusée, activation, choix du modèle, aperçu du contexte, rédaction en direct, nombre « 120 » surligné et blocage, correction, relecture, texte retenu, limites retenues, contrôles et export Word et PDF | Réussi, aucune erreur dans la console. Captures dans `captures-phase8/` |
| CI GitHub, job « IA locale avec un vrai modèle » : Ollama et `qwen2.5:0.5b`, deux demandes par protocole | À compléter avec le résultat du CI |

Les captures montrent la réponse d'un serveur de test, pas celle d'un vrai modèle : le conteneur de développement n'a pas accès aux modèles. Les textes réellement produits par le modèle dans le CI sont publiés comme artefact (`textes-produits-par-le-modele`).

## 7. Limites et points non terminés

- STATPFE n'installe pas lui-même de modèle : l'utilisateur doit installer Ollama (ou un serveur compatible) et télécharger un modèle. Un modèle embarqué pourra être étudié en Phase 9.
- Le contrôle des nombres vérifie qu'un nombre existe dans les résultats, pas qu'il est employé au bon endroit (par exemple une valeur p présentée comme une taille d'effet), ni le signe des nombres. Il ne juge pas le sens des phrases. La relecture reste indispensable, d'où la case obligatoire.
- Les nombres écrits en lettres (« vingt-trois ») ne sont pas contrôlés.
- La qualité du français dépend fortement du modèle ; les petits modèles (moins de 3 milliards de paramètres) rédigent souvent mal. Le conseil de taille reste indicatif.
- Même avec une température basse et une graine fixée, deux rédactions peuvent différer (selon le serveur et le matériel) : c'est pourquoi chaque proposition est conservée telle quelle.
- La rédaction ne fonctionne que pour une analyse enregistrée ; les calculs de puissance et le plan d'analyse ne sont pas encore pris en charge par l'IA.
- Le serveur local lui-même (Ollama) n'est pas contrôlé par STATPFE : on vérifie seulement qu'il est sur l'ordinateur.

## 8. Vérifications manuelles proposées

1. Sans rien installer, vérifier que l'application fonctionne normalement et que le panneau indique « désactivée ».
2. Installer Ollama sur un PC Windows, faire `ollama pull qwen2.5:3b` (ou le modèle conseillé par la page), activer l'IA, tester la connexion et choisir le modèle.
3. Sur une de vos analyses, cliquer sur « Voir ce qui sera transmis » et vérifier qu'aucune donnée personnelle n'apparaît.
4. Demander un paragraphe de résultats, le comparer aux tableaux, corriger ce qui doit l'être, puis le retenir et exporter le rapport.

## 9. Documentation mise à jour

`README.md` et ce document.

## 10. Phase suivante proposée

**Phase 9 : distribution.** Préparer les distributions réellement testées (installateur Windows signé si possible, puis macOS et Linux selon les possibilités de test), procédure de mise à jour qui préserve les projets, guide d'installation (y compris celle, facultative, d'Ollama) et documentation des limites de chaque plateforme.
