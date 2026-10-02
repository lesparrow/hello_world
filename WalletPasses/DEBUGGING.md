# Guide de débogage — WalletPasses

## 0. Où regarder

| Source | Contenu |
|---|---|
| **Administration → Paramètres Wallet → Tester la configuration** | certificat (expiration, UID, clé privée), WWDR, HTTPS, HTTP/2, accès API Google |
| **Journal des passes** (`WalletPassLog`) | Created, Updated, Downloaded, PushSent/PushFailed, DeviceRegistered/Unregistered, Scanned, GoogleSynced/GoogleError, **Unauthorized**, DeviceLog (erreurs remontées par l'iPhone) |
| `data/logs/espo-AAAA-MM-JJ.log` | lignes `WalletPasses [...]` (erreurs, 401, échecs push) |
| Fiche du pass | `pushPending`, `contentUpdatedAt`, `googleSyncError`, appareils enregistrés |
| iPhone | Mac + câble → app **Console** → filtrer sur le processus `passd` (erreurs de signature, de téléchargement, de web service) |
| iPhone (réglage dev) | *Réglages → Développeur → PassKit Testing → « Allow HTTP Services »* (tests sans HTTPS uniquement) et *Additional Logging* |

Test rapide du `.pkpass` hors iPhone :

```bash
unzip -o pass.pkpass -d /tmp/p && cat /tmp/p/pass.json | python3 -m json.tool
# Vérifier la signature détachée avec le WWDR :
openssl cms -verify -binary -inform DER -in /tmp/p/signature -content /tmp/p/manifest.json \
  -CAfile AppleWWDRCAG4.pem -purpose any -out /dev/null
```

---

## 1. Certificat invalide

### « Unable to read the .p12 certificate … mac verify failure »
Mauvais mot de passe, ou le `.p12` ne contient pas la clé privée.
- Ré-exporter depuis le Trousseau dans *Mes certificats* : le certificat **déplié avec sa clé** (deux éléments
  sélectionnés).
- Vérifier : `openssl pkcs12 -in pass.p12 -nokeys -info` (demande le mot de passe).

### « … digital envelope routines::unsupported » (OpenSSL 3)
Les `.p12` exportés par macOS utilisent RC2-40, que le fournisseur par défaut d'OpenSSL 3 désactive.
- L'extension tente `openssl pkcs12 -legacy` (CLI) puis **ré-exporte le p12 en AES** au téléversement. Si `proc_open`
  est désactivé, convertir soi-même :
  ```bash
  openssl pkcs12 -legacy -in pass.p12 -nodes -out tmp.pem
  openssl pkcs12 -export -in tmp.pem -out pass-modern.p12
  rm tmp.pem
  ```

### Le pass ne s'ouvre pas sur l'iPhone (« Impossible d'ajouter le pass »)
| Cause | Vérification |
|---|---|
| `passTypeIdentifier` ≠ UID du certificat | *Tester la configuration* → ligne « Certificate matches Pass Type ID » |
| `teamIdentifier` faux | le Team ID doit être celui du compte qui a créé le Pass Type ID |
| Certificat expiré | validité 1 an → renouveler et re-téléverser (les passes déjà installés continuent de fonctionner, mais leurs mises à jour échouent) |
| WWDR absent ou mauvais | utiliser **WWDR G4** ; l'ancien WWDR (G1) a expiré en 2023 |
| Pas d'`icon.png` | ajouter une icône au modèle (le logo sert de repli) |
| Image non PNG ou trop lourde | PNG < 2 Mo (les JPEG sont convertis automatiquement) |
| MIME incorrect (proxy, CDN) | la réponse doit être `Content-Type: application/vnd.apple.pkpass` |

---

## 2. Push refusé (APNs)

Le journal indique `PushFailed` avec `APNs <code> <raison>` ; `lastPushStatus` est visible sur chaque appareil.

| Code / raison | Signification | Correctif |
|---|---|---|
| `0 Couldn't connect…` / `Timeout` | sortie réseau bloquée | ouvrir `api.push.apple.com:443` (TCP) depuis le serveur ; proxy sortant ? |
| `0 … HTTP/2` | cURL sans nghttp2 | *Tester la configuration* → « HTTP/2 (APNs) » ; installer `libcurl` avec HTTP/2 |
| `403 BadCertificate` / `BadCertificateEnvironment` | certificat refusé | utiliser le certificat **du Pass Type ID** (pas un certificat d'app) ; Wallet ne fonctionne **qu'en production** (`api.push.apple.com`) |
| `400 DeviceTokenNotForTopic` / `TopicDisallowed` | topic ≠ Pass Type ID | le Pass Type ID des paramètres doit correspondre au certificat |
| `400 InvalidPushType` | en-tête refusé | essayer `apns-push-type: background` dans les paramètres (par défaut : aucun) |
| `410 Unregistered` / `400 BadDeviceToken` | le pass a été supprimé du téléphone | l'appareil est retiré automatiquement (normal) |
| `429` / `5xx` | limitation / indisponibilité Apple | le job « push pending updates » réessaie toutes les 5 min |

> `pass.update` n'est **pas** un type de push APNs. Une notification Wallet est un `POST /3/device/<token>`
> avec le payload `{}` et `apns-topic = <Pass Type ID>`.

**L'iPhone reçoit le push mais le pass ne change pas** :
- `GET …/registrations/{passType}?passesUpdatedSince=…` doit lister le numéro de série. Vérifier que
  `contentUpdatedAt` a bien changé (seuls les champs de **contenu** déclenchent une mise à jour).
- Le `GET …/passes/…` suivant doit renvoyer 200 avec un `.pkpass` valide. Consulter `Downloaded` / `Error` dans le
  journal.

---

## 3. Erreur 401 du web service Apple

Chaque 401 est journalisé (`Unauthorized`, avec le motif) dans `WalletPassLog` et `data/logs`.

### « missing or malformed Authorization header »
L'en-tête `Authorization: ApplePass <token>` n'atteint pas PHP.
- **Apache + PHP-FPM** : ajouter dans le VirtualHost ou le `.htaccess` :
  ```apache
  CGIPassAuth On
  # ou
  SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1
  ```
- **Nginx + PHP-FPM** :
  ```nginx
  fastcgi_param HTTP_AUTHORIZATION $http_authorization;
  ```
- Un **reverse proxy / WAF** (Cloudflare Access, basic auth devant le CRM…) qui consomme ou réécrit `Authorization`
  doit laisser passer `/api/v1/WalletService/`.

Test :
```bash
curl -i -H "Authorization: ApplePass <token>" \
  https://crm.example.com/api/v1/WalletService/v1/passes/pass.com.example.loyalty/<SERIAL>
# 200 attendu ; le jeton figure dans pass.json (authenticationToken) du .pkpass téléchargé
```

### « invalid authentication token »
- Le pass installé sur le téléphone date d'avant une **ré-émission** ou d'une **restauration de base** : le jeton ne
  correspond plus. Renvoyer le pass (lien Wallet) à l'utilisateur.
- Numéro de série inconnu (pass supprimé dans le CRM) → même réponse 401, voulue pour empêcher l'énumération.
  Utiliser plutôt le statut **Annulé**.

### 404 au lieu de 401
Le `passTypeIdentifier` de l'URL ne correspond pas au Pass Type ID configuré, ou Apple Wallet est désactivé.

### L'appareil ne s'enregistre jamais (pas de `DeviceRegistered`)
- `webServiceURL` absent du `pass.json` : l'URL publique n'est pas en **HTTPS**. *Tester la configuration* affiche
  alors « Web service URL: Not HTTPS ».
- Certificat TLS invalide ou auto-signé : l'iPhone refuse silencieusement.
- Chemin incorrect : `webServiceURL` doit être `https://<crm>/api/v1/WalletService`, sans `/v1` final (Apple
  l'ajoute).
- Réécriture d'URL : `/api/v1/*` doit être routé vers `public/api/v1/index.php` (config EspoCRM standard).

---

## 4. Google Wallet

| Message | Cause | Correctif |
|---|---|---|
| `invalid_grant: account not found` / `Invalid JWT Signature` | clé JSON supprimée ou révoquée, horloge du serveur décalée | régénérer la clé ; synchroniser NTP |
| `403 … permission` | compte de service non invité dans la Pay & Wallet Console | *Users* → inviter l'e-mail `…@….iam.gserviceaccount.com` |
| `404 … issuer` | Issuer ID faux | copier l'ID depuis la console |
| `Google loyalty passes require a logo …` | logo absent ou URL non HTTPS | ajouter un logo au modèle ; l'URL publique doit être en HTTPS et joignable par Google |
| Le bouton Google n'ajoute rien / « Something went wrong » | origine non autorisée ou compte non testeur en mode démo | ajouter le domaine dans *Origines autorisées* ; ajouter l'utilisateur comme testeur ou passer en production |
| Images absentes sur le pass Google | `…/WalletService/image/…` non joignable publiquement | tester l'URL depuis l'extérieur (pare-feu, authentification devant le CRM) |

`googleSyncError` (fiche du pass) contient la dernière erreur renvoyée par Google.

---

## 5. Divers

- **Le lien intelligent renvoie « Lien invalide »** : la signature HMAC ne correspond pas. Le secret est dans
  `data/wallet-passes/link-secret.enc` ; s'il a été supprimé ou si le `cryptKey` EspoCRM a changé, les anciens liens
  sont invalides. Régénérez-les avec « Liens Wallet » ou l'action de masse.
- **« Wallet secret … can't be decrypted (cryptKey changed?) »** : `cryptKey` de `data/config-internal.php` modifié
  après le téléversement. Re-téléverser les certificats.
- **Le job ne tourne pas** : vérifier le cron système (`* * * * * php /chemin/cron.php`) et *Administration → Jobs
  planifiés* (statut *Active*).
- **Aperçu vide** : vider le cache EspoCRM et le cache du navigateur après une mise à jour de l'extension.
