# WalletPasses — Passes Apple Wallet & Google Wallet pour EspoCRM

Extension EspoCRM (8.x / 9.x, PHP ≥ 8.1) de création et de gestion de **cartes numériques** (fidélité, coupons,
billets, cartes génériques) compatibles **Apple Wallet** et **Google Wallet**.

- Modèles de pass (`WalletPassTemplate`) : couleurs, images, code-barres, champs avant/arrière dynamiques.
- Passes émis (`WalletPass`) liés à un Contact / Compte / Prospect, numéro de série et jeton générés.
- Génération `.pkpass` signée (Apple) et lien « Save to Google Wallet » (JWT signé).
- **Web service Apple Wallet v1** complet (enregistrement d'appareils, mises à jour, journal), **push APNs** et job
  cron de rattrapage.
- Lien intelligent + **QR code** : l'iPhone reçoit le `.pkpass`, Android est redirigé vers Google Wallet, les autres
  appareils voient une page de choix.
- Action de masse « Envoyer des passes Wallet » (Contacts / Comptes / Prospects) avec envoi d'e-mail optionnel.
- Journal (`WalletPassLog`), statistiques (appareils, scans), endpoint de scan, ACL par rôles, i18n `fr_FR` / `en_US`.

> Testé sur EspoCRM **9.1.8** (PHP 8.3, MariaDB 11) : installation, mise à jour (ré-installation), API, web service
> Apple, jobs cron, interface (Chromium headless). 37 tests unitaires PHPUnit.

---

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Ce que vous devez fournir](#2-ce-que-vous-devez-fournir)
3. [Installation](#3-installation)
4. [Configuration pas à pas](#4-configuration-pas-à-pas)
5. [Utilisation](#5-utilisation)
6. [API](#6-api)
7. [Architecture et choix techniques](#7-architecture-et-choix-techniques)
8. [Sécurité](#8-sécurité)
9. [Développement : tests et build](#9-développement--tests-et-build)
10. [Désinstallation](#10-désinstallation)
11. [Liste des fichiers](#11-liste-des-fichiers)

Le guide de débogage est dans [DEBUGGING.md](DEBUGGING.md).

---

## 1. Prérequis

| Élément | Exigence |
|---|---|
| EspoCRM | ≥ 8.0 (testé 9.1.8) |
| PHP | ≥ 8.1, extensions `openssl`, `zip`, `curl` (avec **HTTP/2** pour APNs), `gd`, `json`, `mbstring` |
| Réseau sortant | `api.push.apple.com:443` (APNs), `oauth2.googleapis.com:443`, `walletobjects.googleapis.com:443` |
| URL publique | **HTTPS** avec certificat valide (Apple refuse un `webServiceURL` HTTP ; Google charge les images en HTTPS) |
| Cron EspoCRM | actif (`cron.php` toutes les minutes) pour les jobs de rattrapage |
| Apple | Compte **Apple Developer Program** payant |
| Google | Compte **Google Pay & Wallet Console** (issuer) + projet **Google Cloud** |

Aucune dépendance Composer à installer sur le serveur : les bibliothèques sont embarquées dans le ZIP.

## 2. Ce que vous devez fournir

Aucune de ces valeurs n'est inventée ni codée en dur. Elles se saisissent dans **Administration → Wallet Passes →
Paramètres Wallet** :

| Valeur | Où la trouver |
|---|---|
| **Team ID** Apple (10 caractères) | developer.apple.com → *Membership details* |
| **Pass Type ID** (`pass.com.votre-domaine.xxx`) | *Certificates, Identifiers & Profiles → Identifiers → Pass Type IDs* (à créer) |
| **Certificat du Pass Type ID (.p12)** + mot de passe | voir § 4.1 |
| Certificat **Apple WWDR G4** (optionnel) | https://www.apple.com/certificateauthority/ (sinon le G4 fourni par la bibliothèque est utilisé) |
| **Issuer ID** Google Wallet | pay.google.com/business/console → *Google Wallet API* |
| **Clé JSON du compte de service** Google | Google Cloud Console → *IAM → Comptes de service* |
| **Origines autorisées** | les domaines HTTPS qui afficheront le bouton « Ajouter à Google Wallet » |
| **URL publique** du CRM | ex. `https://crm.votre-domaine.fr` |

## 3. Installation

### 3.1 Depuis l'interface

1. **Administration → Extensions → Choisir un fichier** → `WalletPasses-1.0.0.zip` → **Installer**.
2. Vider le cache si demandé (*Administration → Vider le cache*) et recharger la page.

### 3.2 En ligne de commande

```bash
php command.php extension --file=/chemin/WalletPasses-1.0.0.zip
```

### 3.3 Ce que fait l'installation (`scripts/AfterInstall.php`)

- création des tables `wallet_pass_template`, `wallet_pass`, `wallet_pass_log`, `wallet_device`,
  `wallet_registration` (rebuild EspoCRM) ;
- création du dossier protégé `data/wallet-passes/` (chmod 700 + `.htaccess` « deny ») ;
- création des **jobs planifiés** « Wallet Passes: push pending updates » (*/5 min) et « expire passes » (horaire) ;
- ajout de l'onglet **Pass Wallet** à la navigation et valeurs par défaut des paramètres ;
- vidage du cache.

### 3.4 Instance de développement Docker

```bash
cd WalletPasses
./build.sh                                     # produit build/WalletPasses-1.0.0.zip
docker compose -f docker/docker-compose.yml up -d
# attendre ~1 min l'initialisation, puis :
docker compose -f docker/docker-compose.yml exec espocrm \
  php command.php extension --file=/ext/WalletPasses-1.0.0.zip
# http://localhost:8080  (admin / admin123)

# HTTPS public pour tester un vrai iPhone (tunnel Cloudflare éphémère) :
docker compose -f docker/docker-compose.yml --profile tunnel up -d tunnel
docker compose -f docker/docker-compose.yml logs tunnel | grep trycloudflare.com
# → saisir l'URL https://xxxx.trycloudflare.com dans « URL publique de base »
```

## 4. Configuration pas à pas

### 4.1 Apple Wallet

1. **Créer le Pass Type ID** : developer.apple.com → *Identifiers* → **+** → *Pass Type IDs* → description +
   identifiant `pass.com.votre-domaine.fidelite`.
2. **Créer le certificat** : sélectionner le Pass Type ID → *Create Certificate*.
   - Sur un Mac : *Trousseau d'accès → Assistant de certification → Demander un certificat à une autorité* → CSR
     enregistré sur le disque → l'envoyer → télécharger `pass.cer` → double-cliquer.
   - Dans le Trousseau, catégorie *Mes certificats*, clic droit sur « Pass Type ID: pass.com… » → **Exporter** →
     format `.p12` avec un mot de passe. Le certificat **et** sa clé privée doivent être exportés ensemble.
   - Sans Mac (OpenSSL) :
     ```bash
     openssl req -new -newkey rsa:2048 -nodes -keyout pass.key -out pass.csr -subj "/CN=WalletPasses"
     # envoyer pass.csr sur developer.apple.com, télécharger pass.cer, puis :
     openssl x509 -inform DER -in pass.cer -out pass.pem
     openssl pkcs12 -export -inkey pass.key -in pass.pem -out pass.p12 -passout pass:VOTRE_MOT_DE_PASSE
     ```
3. Dans **Paramètres Wallet** :
   - cocher **Apple Wallet activé** ;
   - **Team ID** et **Pass Type ID** ;
   - **Certificat du pass (.p12)** : choisir le fichier, saisir le mot de passe → **Téléverser**. Le fichier est
     vérifié (mot de passe, clé privée correspondante), ré-exporté en chiffrement moderne (compatible OpenSSL 3) puis
     stocké chiffré ;
   - **Certificat WWDR** (optionnel) : `AppleWWDRCAG4.cer` ;
   - **URL du web service** : laisser vide (= `<URL publique>/api/v1/WalletService`) ;
   - **En-tête apns-push-type** : laisser « aucun » (recommandé pour les mises à jour Wallet).
4. **Enregistrer**, puis **Tester la configuration** : la vérification inclut l'expiration du certificat, la
   correspondance UID ↔ Pass Type ID, la clé privée, HTTP/2 et l'URL HTTPS.

### 4.2 Google Wallet

1. **Issuer** : https://pay.google.com/business/console → *Google Wallet API* → noter l'**Issuer ID**.
2. **Google Cloud** : créer un projet → *API et services* → activer **Google Wallet API**.
3. **Compte de service** : *IAM → Comptes de service → Créer* (aucun rôle GCP requis) → onglet *Clés* →
   **Ajouter une clé JSON** → télécharger.
4. Dans la **Pay & Wallet Console** → *Users* → **inviter l'adresse e-mail du compte de service** (rôle
   *Developer*/*Admin*). Sans cette étape, l'API répond 403.
5. Dans **Paramètres Wallet** : cocher **Google Wallet activé**, saisir l'**Issuer ID**, téléverser la **clé JSON**,
   ajouter les **origines autorisées** (`https://crm.votre-domaine.fr`), langue (`fr`) → **Enregistrer** →
   **Tester la configuration**.

> Tant que le compte issuer est en mode **démo**, seuls les comptes Google ajoutés comme testeurs peuvent enregistrer
> les passes. Demandez l'accès « publishing » dans la console pour la production.

### 4.3 Général

- **URL publique de base** : URL HTTPS publique d'EspoCRM (par défaut : *Site URL*). Elle est utilisée dans les liens,
  les QR codes, le `webServiceURL` Apple et les images publiques Google.
- **Conservation du journal** : nombre de jours de `WalletPassLog` conservés (0 = illimité).
- **Rôles** : *Administration → Rôles* → accorder `Wallet Pass Template`, `Wallet Pass`, `Wallet Pass Log`,
  `Wallet Device` selon les profils. Sans rôle, un utilisateur n'a **aucun** accès.

## 5. Utilisation

### 5.1 Créer un modèle

*Modèles de pass Wallet → Créer* :

| Champ | Remarque |
|---|---|
| Type de pass | `generic`, `coupon`, `eventTicket`, `storeCard`, `loyaltyCard` (Apple : storeCard ; Google : loyalty) |
| Organisation, Description | obligatoires (Apple) |
| Couleurs | fond, valeurs (`foregroundColor`), libellés (`labelColor`) |
| Images | **Icône** (obligatoire chez Apple, sinon le logo est utilisé), logo, strip, fond (billets), vignette. PNG conseillé (les JPEG sont convertis) |
| Code-barres | format QR / PDF417 / Aztec / Code 128 ; contenu dynamique (défaut `{pass.serialNumber}`) |
| Champs avant | répétables : section (header/primary/secondary/auxiliary), clé, libellé, valeur, alignement |
| Champs arrière | répétables (section *back*) |
| Validité | date d'expiration par défaut **ou** durée en jours |

L'**aperçu** (panneau latéral) se met à jour en direct pendant l'édition.

**Variables** utilisables dans les valeurs, le code-barres et le texte du logo :

```
{pass.serialNumber} {pass.holderName} {pass.points} {pass.expiresAt} {pass.issuedAt} {pass.name}
{contact.firstName} {contact.lastName} {contact.name} {contact.emailAddress} {contact.<attribut>}
{account.name} {account.<attribut>}   {lead.<attribut>}   {template.organizationName}
```

Exemple de carte de fidélité :

| Section | Clé | Libellé | Valeur |
|---|---|---|---|
| primary | points | Points | `{pass.points}` |
| secondary | member | Membre | `{contact.firstName} {contact.lastName}` |
| auxiliary | expires | Valable jusqu'au | `{pass.expiresAt}` |
| back | terms | Conditions | `Carte nominative, sans valeur monétaire.` |

### 5.2 Émettre un pass

- **Unitaire** : *Pass Wallet → Créer* (ou panneau *Pass Wallet* d'un Contact). Le numéro de série, le jeton
  d'authentification, les dates, le nom du porteur et le lien Wallet sont générés automatiquement.
- **En masse** : liste des **Contacts** (ou Comptes / Prospects) → cocher → *Actions* → **Envoyer des passes Wallet**
  → choisir le modèle, éventuellement un **modèle d'e-mail**, et l'option « ignorer les fiches ayant déjà un pass
  actif ».

Exemple de **modèle d'e-mail** (HTML) :

```html
<p>Bonjour {Contact.firstName},</p>
<p>Votre carte de fidélité est prête :
   <a href="{WalletPass.walletLink}">l'ajouter à mon téléphone</a></p>
<p><img src="{WalletPass.walletQrCodeUrl}" width="200" alt="QR code"></p>
```

Pour une **campagne / Mass Email** EspoCRM classique, utilisez `{Contact.walletPassLink}`. Ce champ du Contact est
renseigné par l'action de masse avec le lien du dernier pass émis.

### 5.3 Distribuer

Sur la fiche d'un pass :

- **Liens Wallet** : lien intelligent + QR code (téléchargeable en PNG), lien Apple, lien Google Save-to-Wallet ;
- menu **⋯** : *Télécharger .pkpass*, *Copier le lien Google Wallet*, *Pousser la mise à jour aux appareils*.

Le **lien intelligent** (`…/api/v1/WalletService/go/{serial}?s=…`) est public et signé (HMAC). Il détecte la
plateforme au moment du scan : iPhone/iPad/Safari macOS → `.pkpass`, Android → Google Wallet, autres → page de choix
avec les deux boutons et le QR code.

### 5.4 Mettre à jour un pass

Toute modification du **contenu** (modèle, porteur, valeur du code-barres, points, statut, expiration) :

1. met à jour `contentUpdatedAt` et passe `pushPending` à vrai ;
2. envoie immédiatement un **push APNs** à chaque appareil enregistré (l'iPhone rappelle ensuite le web service et
   télécharge la nouvelle version) et **patche l'objet Google** (Google met à jour les téléphones) ;
3. en cas d'échec, le job **« push pending updates »** (toutes les 5 min) réessaie.

La modification d'un **modèle** marque tous ses passes non annulés : le job les pousse par lots de 200.
Pour révoquer un pass, passez son statut à **Annulé** (Apple : `voided`, Google : `INACTIVE`) plutôt que de le
supprimer. Le job horaire passe automatiquement les passes échus en **Expiré**.

### 5.5 Scans

Une application de caisse ou de contrôle peut enregistrer un scan avec l'API (utilisateur avec droit *édition* sur
Wallet Pass) :

```bash
curl -X POST https://crm.example.com/api/v1/WalletPasses/scan \
  -H "X-Api-Key: <clé API d'un utilisateur API>" -H "Content-Type: application/json" \
  -d '{"code":"C23D075FCEF5EB99CD6F"}'
# → {"id":"…","status":"Active","valid":true,"scanCount":3,"points":250,…}
```

## 6. API

### 6.1 Web service Apple Wallet (public, conforme à la spécification v1)

`webServiceURL` = `https://<crm>/api/v1/WalletService`. Apple ajoute lui-même le préfixe `/v1/…` :

| Méthode | Chemin (après `/api/v1/WalletService`) | Auth | Réponses |
|---|---|---|---|
| GET | `/v1/passes/{passTypeIdentifier}/{serialNumber}` | `ApplePass <token>` | 200 `.pkpass` + `Last-Modified`, 304, 401 |
| POST | `/v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}` body `{"pushToken":"…"}` | `ApplePass <token>` | 201 créé, 200 existant, 400, 401 |
| GET | `/v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}?passesUpdatedSince=<tag>` | aucune (spec Apple) | 200 `{"serialNumbers":[…],"lastUpdated":"…"}`, 204 |
| DELETE | `/v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}` | `ApplePass <token>` | 200, 401 |
| POST | `/v1/log` body `{"logs":["…"]}` | aucune | 200 |

Le cahier des charges proposait `/register/…` : ce chemin n'est pas celui qu'appelle Wallet. Les chemins ci-dessus
sont ceux de la spécification Apple. Les jetons sont comparés en temps constant (`hash_equals`). Un numéro de série
inconnu et un jeton faux renvoient tous deux 401, pour empêcher l'énumération des numéros.

### 6.2 Liens publics signés

| Chemin | Rôle |
|---|---|
| `GET /WalletService/go/{serial}?s=…[&p=apple\|google]` | lien intelligent (QR code) |
| `GET /WalletService/qr/{serial}?s=…[&size=320]` | QR code PNG (e-mails, impression) |
| `GET /WalletService/image/{templateId}/{image}?v=…&s=…` | images du modèle pour Google (URLs publiques exigées par Google) |

### 6.3 API authentifiée (ACL EspoCRM)

| Méthode | Chemin | Droit |
|---|---|---|
| POST | `/WalletPasses/pass/{id}/links` | lecture du pass |
| GET | `/WalletPasses/pass/{id}/pkpass` | lecture |
| GET | `/WalletPasses/pass/{id}/preview` | lecture |
| POST | `/WalletPasses/pass/{id}/push` | édition |
| GET | `/WalletPasses/template/{id}/preview` | lecture du modèle |
| POST | `/WalletPasses/scan` | édition (scope) |
| POST | `/MassAction` `{"entityType":"Contact","action":"walletSendPasses","params":{"ids":[…]},"data":{"templateId":"…","emailTemplateId":null,"skipExisting":true}}` | création WalletPass |
| GET/POST | `/WalletPasses/settings/status`, `/settings/upload/{appleP12\|appleWwdr\|googleServiceAccount}`, `/settings/test` | **administrateur** |

## 7. Architecture et choix techniques

```
Core/        PHP pur, sans dépendance EspoCRM, testé unitairement
  Apple/     PassJsonBuilder, PkpassGenerator (pkpass/pkpass), Certificate, ApnsClient, WebService/*
  Google/    ServiceAccount, Jwt (RS256), AccessTokenProvider, WalletApiClient (REST), ObjectMapper, SaveLinkBuilder
  Model/     PassDefinition, PassField, PassType, BarcodeFormat, PassStatus
  Util/      Color, Placeholder, LinkSigner, SecureToken, UserAgent, QrCode
Tools/       adaptateurs EspoCRM : SecretStore, WalletSettings, PassDefinitionFactory, WalletPassService,
             UpdateNotifier, EspoPassStore, PassIssuer, PassLinks, PassLogger, ConfigTester
Api/         actions de route (WebService/*, PublicLink/*, Pass/*, Admin/*)
Hooks/       WalletPass\Lifecycle (série, jeton, push), WalletPassTemplate\PropagateChanges
Jobs/        PushPendingUpdates, ExpirePasses
MassAction/  SendPasses
```

**Bibliothèques tierces (stratégie de vendoring) :**

| Besoin | Choix | Justification |
|---|---|---|
| `.pkpass` | **pkpass/pkpass** ^2.5 (ex-`tschoffelen/php-pkpass`) | MIT, aucune dépendance, manifeste + signature PKCS#7 détachée + ZIP, WWDR G4 fourni |
| Google Wallet | **client REST interne** (JWT RS256 via `openssl`, cURL) | `google/apiclient` pèse ~40 Mo et apporte guzzle / psr7 qu'**EspoCRM embarque déjà** (`guzzlehttp/psr7`, `league/oauth2-client`) dans ses propres versions : risque de conflit d'autoload. L'API Wallet est du JSON simple : ~300 lignes couvertes par des tests |
| QR code PNG | **bacon/bacon-qr-code** ^3 (rendu GD) | pas d'Imagick requis ; absent du vendor EspoCRM (pas de conflit) |
| APNs | **cURL HTTP/2** natif | aucune lib nécessaire, authentification par le certificat du Pass Type ID |

Les bibliothèques sont installées par Composer **au build** (`build.sh`, `build-config/composer.json` + lock) dans
`custom/Espo/Modules/WalletPasses/vendor/` et chargées par `Resources/autoload.json` (`autoloadFileList`). Le
serveur cible n'a besoin ni de Composer ni d'Internet pendant l'installation.

**Core non modifié** : tout est dans le module `custom/Espo/Modules/WalletPasses` et
`client/custom/modules/wallet-passes`. Les entités, champs, layouts, routes, hooks et jobs sont déclarés par
métadonnées.

## 8. Sécurité

- **Secrets** (p12, mot de passe, WWDR, JSON Google, secret HMAC) stockés dans `data/wallet-passes/*.enc`, chiffrés
  en **AES-256-GCM** avec une clé dérivée du `cryptKey` EspoCRM, chmod 600, hors web root, jamais dans
  `data/config.php` ni exposés par l'API *Settings*. Les champs de configuration non secrets sont déclarés
  `level: admin`.
- `authenticationToken` : 64 caractères hexadécimaux aléatoires (`random_bytes`), champ `internal`, jamais renvoyé
  par l'API REST.
- Liens publics signés HMAC-SHA256. Images publiques limitées aux pièces jointes réellement liées au modèle.
- Seules les routes `WalletService/*` sont publiques (`noAuth`) ; toutes les autres passent par l'ACL EspoCRM ;
  les paramètres sont réservés aux **administrateurs**.
- Validation stricte des entrées (motifs des identifiants, tailles, JSON), journalisation des 401 et erreurs dans
  `data/logs` et `WalletPassLog`.
- Les jetons APNs invalides (410 / BadDeviceToken) suppriment automatiquement l'appareil.

## 9. Développement : tests et build

```bash
cd WalletPasses
composer install                  # dépendances + phpunit + phpcs (dev)
vendor/bin/phpunit                # 37 tests : signature .pkpass (vérif. CMS + falsification), web service, Google JWT…
vendor/bin/phpcs --standard=PSR12 src/files/custom src/scripts tests
./build.sh                        # tests + vendoring + lint + ZIP  →  build/WalletPasses-1.0.0.zip
./build.sh --skip-tests           # ZIP uniquement
```

Les tests génèrent à la volée une fausse autorité « WWDR », un certificat « Pass Type ID » et un compte de service.
Aucun certificat réel n'est versionné.

## 10. Désinstallation

*Administration → Extensions → Désinstaller*. `scripts/BeforeUninstall.php` supprime les jobs planifiés et les
entrées de navigation. **Les données sont conservées** (tables `wallet_*`, `data/wallet-passes/`), afin qu'une
réinstallation retrouve les passes déjà distribués. Pour une purge complète :

```sql
DROP TABLE wallet_registration, wallet_device, wallet_pass_log, wallet_pass, wallet_pass_template;
```
```bash
rm -rf data/wallet-passes
```

## 11. Liste des fichiers

Voir [FILES.md](FILES.md) (chemins complets de chaque fichier du projet et du package).
