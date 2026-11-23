# Installer STATPFE

STATPFE s'installe comme une application ordinaire : il n'y a ni Python, ni R, ni outil de
développement à installer. Tout ce dont il a besoin est inclus dans le paquet.

Taille : environ 100 Mo une fois installé. Système conseillé : 8 Go de mémoire (4 Go suffisent sans IA locale).

## Windows 10 et 11

1. Téléchargez `STATPFE_x.y.z_x64-setup.exe`.
2. Double-cliquez dessus. L'installation se fait **dans votre compte**, sans droits d'administrateur
   (dossier `%LOCALAPPDATA%\STATPFE`), et ajoute STATPFE au menu Démarrer.
3. Windows peut afficher « Windows a protégé votre ordinateur » (SmartScreen), car l'installateur
   n'est pas encore signé par un certificat d'éditeur : cliquez sur **Informations complémentaires**,
   puis **Exécuter quand même**.

Pour un déploiement en salle informatique, un paquet `.msi` est aussi fourni.

**Désinstaller** : Paramètres > Applications > STATPFE > Désinstaller.

## macOS (Mac à puce Apple : M1, M2, M3, M4…)

1. Téléchargez `STATPFE_x.y.z_aarch64.dmg` et ouvrez-le.
2. Glissez **STATPFE** dans le dossier **Applications**.
3. Au premier lancement, macOS refuse d'ouvrir une application qui n'est pas notariée par Apple :
   faites un **clic droit** (ou Ctrl-clic) sur STATPFE > **Ouvrir**, puis confirmez **Ouvrir**.
   Si macOS indique que l'application « est endommagée », ouvrez le Terminal et tapez :
   `xattr -dr com.apple.quarantine /Applications/STATPFE.app`

Les Mac à processeur Intel ne sont pas encore pris en charge par ce paquet.

**Désinstaller** : glissez STATPFE depuis Applications vers la Corbeille.

## Linux

Trois formats, au choix :

- **Ubuntu, Debian, Linux Mint** : `sudo apt install ./STATPFE_x.y.z_amd64.deb`
  (désinstaller : `sudo apt remove statpfe`)
- **Fedora, openSUSE** : `sudo dnf install ./STATPFE-x.y.z-1.x86_64.rpm`
  (désinstaller : `sudo dnf remove statpfe`)
- **Toute distribution, sans installation** : `chmod +x STATPFE_x.y.z_amd64.AppImage`, puis double-clic.
  Si l'AppImage ne démarre pas (bibliothèque FUSE absente), lancez-la avec
  `APPIMAGE_EXTRACT_AND_RUN=1 ./STATPFE_x.y.z_amd64.AppImage`.

Paquets construits sur Ubuntu 22.04 : ils fonctionnent sur les distributions de 2022 et plus récentes.

## Mettre à jour

Installez simplement la nouvelle version par-dessus l'ancienne (même procédure que l'installation).
**Vos projets ne sont jamais touchés** : ce sont des fichiers `.statpfe` rangés où vous les avez enregistrés.
La liste des projets récents et les réglages (IA) sont conservés. Un projet créé avec une version plus
ancienne est converti automatiquement à l'ouverture, et à chaque enregistrement la version précédente du fichier est gardée à côté (`.statpfe.bak`).

## Où sont mes données ?

| Élément | Emplacement |
|---|---|
| Vos projets | les fichiers `.statpfe` que vous avez créés, là où vous les avez enregistrés |
| Réglages de l'application (projets récents, IA) | Windows : `%APPDATA%\STATPFE` · macOS : `~/Library/Application Support/STATPFE` · Linux : `~/.config/statpfe` |

La désinstallation retire l'application mais **laisse vos projets et vos réglages**. Pour tout effacer,
supprimez aussi le dossier de réglages ci-dessus.

## Vérifier que tout fonctionne

Sur l'écran d'accueil, cliquez sur **À propos et diagnostic** : STATPFE essaie réellement chacune des
bibliothèques incluses (calcul, lecture des fichiers Excel, graphiques, rapports Word et PDF…) et
indique si l'une d'elles ne fonctionne pas. En cas de problème, joignez une capture de cet écran.

## IA (facultative)

STATPFE fonctionne entièrement sans IA. Pour l'activer, ouvrez **IA** dans le menu de gauche d'un
projet ; l'application guide l'installation :

- **IA locale gratuite** : STATPFE vous envoie vers l'installateur officiel d'Ollama, puis télécharge
  pour vous un modèle adapté à la mémoire de votre ordinateur. Rien ne quitte votre ordinateur.
- **Claude (en ligne)** : STATPFE installe Claude Code avec la commande officielle d'Anthropic
  (après votre confirmation), vous aide à vous connecter à votre compte Claude, puis vous demande
  l'autorisation d'envoyer les résultats calculés (jamais vos données brutes). Un compte Claude est nécessaire.
