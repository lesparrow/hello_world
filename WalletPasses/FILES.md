# Liste des fichiers — WalletPasses 1.0.0

Chemins relatifs au dossier `WalletPasses/` du dépôt. Dans le ZIP, `src/` devient la racine du package (`manifest.json`, `files/`, `scripts/`) ;
à l'installation, `files/` est copié à la racine d'EspoCRM.

Le dossier `custom/Espo/Modules/WalletPasses/vendor/` (pkpass/pkpass, bacon/bacon-qr-code, dasprid/enum) est généré par `build.sh` et n'est pas versionné.
**193 fichiers** (hors FILES.md).


## Package — racine (3)

- `src/manifest.json`
- `src/scripts/AfterInstall.php`
- `src/scripts/BeforeUninstall.php`

## Package — backend (copié dans `custom/Espo/Modules/WalletPasses/`) (155)

- `src/files/custom/Espo/Modules/WalletPasses/Api/Admin/AdminGuard.php` → `custom/Espo/Modules/WalletPasses/Api/Admin/AdminGuard.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Admin/GetStatus.php` → `custom/Espo/Modules/WalletPasses/Api/Admin/GetStatus.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Admin/PostTest.php` → `custom/Espo/Modules/WalletPasses/Api/Admin/PostTest.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Admin/PostUpload.php` → `custom/Espo/Modules/WalletPasses/Api/Admin/PostUpload.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/GetPkpass.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/GetPkpass.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/GetPreview.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/GetPreview.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/GetTemplatePreview.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/GetTemplatePreview.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/PassLoader.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/PassLoader.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/PostLinks.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/PostLinks.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/PostPush.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/PostPush.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/Pass/PostScan.php` → `custom/Espo/Modules/WalletPasses/Api/Pass/PostScan.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/PublicLink/GetImage.php` → `custom/Espo/Modules/WalletPasses/Api/PublicLink/GetImage.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/PublicLink/GetQrCode.php` → `custom/Espo/Modules/WalletPasses/Api/PublicLink/GetQrCode.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/PublicLink/GetSmartLink.php` → `custom/Espo/Modules/WalletPasses/Api/PublicLink/GetSmartLink.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/ResponseFactory.php` → `custom/Espo/Modules/WalletPasses/Api/ResponseFactory.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/WebService/DeleteRegistration.php` → `custom/Espo/Modules/WalletPasses/Api/WebService/DeleteRegistration.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/WebService/GetPass.php` → `custom/Espo/Modules/WalletPasses/Api/WebService/GetPass.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/WebService/GetSerialNumbers.php` → `custom/Espo/Modules/WalletPasses/Api/WebService/GetSerialNumbers.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/WebService/HandlerFactory.php` → `custom/Espo/Modules/WalletPasses/Api/WebService/HandlerFactory.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/WebService/PostLog.php` → `custom/Espo/Modules/WalletPasses/Api/WebService/PostLog.php`
- `src/files/custom/Espo/Modules/WalletPasses/Api/WebService/PostRegistration.php` → `custom/Espo/Modules/WalletPasses/Api/WebService/PostRegistration.php`
- `src/files/custom/Espo/Modules/WalletPasses/Classes/Select/WalletPass/PrimaryFilters/Active.php` → `custom/Espo/Modules/WalletPasses/Classes/Select/WalletPass/PrimaryFilters/Active.php`
- `src/files/custom/Espo/Modules/WalletPasses/Classes/Select/WalletPass/PrimaryFilters/PushPending.php` → `custom/Espo/Modules/WalletPasses/Classes/Select/WalletPass/PrimaryFilters/PushPending.php`
- `src/files/custom/Espo/Modules/WalletPasses/Controllers/WalletDevice.php` → `custom/Espo/Modules/WalletPasses/Controllers/WalletDevice.php`
- `src/files/custom/Espo/Modules/WalletPasses/Controllers/WalletPass.php` → `custom/Espo/Modules/WalletPasses/Controllers/WalletPass.php`
- `src/files/custom/Espo/Modules/WalletPasses/Controllers/WalletPassLog.php` → `custom/Espo/Modules/WalletPasses/Controllers/WalletPassLog.php`
- `src/files/custom/Espo/Modules/WalletPasses/Controllers/WalletPassTemplate.php` → `custom/Espo/Modules/WalletPasses/Controllers/WalletPassTemplate.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/ApnsClient.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/ApnsClient.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/AppleConfig.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/AppleConfig.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/Certificate.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/Certificate.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/PassJsonBuilder.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/PassJsonBuilder.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/PkpassGenerator.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/PkpassGenerator.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/PushResult.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/PushResult.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/WebService/PassStore.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/WebService/PassStore.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/WebService/StoredPass.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/WebService/StoredPass.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/WebService/WebServiceHandler.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/WebService/WebServiceHandler.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Apple/WebService/WebServiceResult.php` → `custom/Espo/Modules/WalletPasses/Core/Apple/WebService/WebServiceResult.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Exception/ConfigurationException.php` → `custom/Espo/Modules/WalletPasses/Core/Exception/ConfigurationException.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Exception/WalletException.php` → `custom/Espo/Modules/WalletPasses/Core/Exception/WalletException.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/AccessTokenProvider.php` → `custom/Espo/Modules/WalletPasses/Core/Google/AccessTokenProvider.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/GoogleConfig.php` → `custom/Espo/Modules/WalletPasses/Core/Google/GoogleConfig.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/GoogleWalletService.php` → `custom/Espo/Modules/WalletPasses/Core/Google/GoogleWalletService.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/Jwt.php` → `custom/Espo/Modules/WalletPasses/Core/Google/Jwt.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/ObjectMapper.php` → `custom/Espo/Modules/WalletPasses/Core/Google/ObjectMapper.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/SaveLinkBuilder.php` → `custom/Espo/Modules/WalletPasses/Core/Google/SaveLinkBuilder.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/ServiceAccount.php` → `custom/Espo/Modules/WalletPasses/Core/Google/ServiceAccount.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Google/WalletApiClient.php` → `custom/Espo/Modules/WalletPasses/Core/Google/WalletApiClient.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Http/CurlHttpClient.php` → `custom/Espo/Modules/WalletPasses/Core/Http/CurlHttpClient.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Http/HttpClient.php` → `custom/Espo/Modules/WalletPasses/Core/Http/HttpClient.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Http/HttpResponse.php` → `custom/Espo/Modules/WalletPasses/Core/Http/HttpResponse.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Model/BarcodeFormat.php` → `custom/Espo/Modules/WalletPasses/Core/Model/BarcodeFormat.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Model/PassDefinition.php` → `custom/Espo/Modules/WalletPasses/Core/Model/PassDefinition.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Model/PassField.php` → `custom/Espo/Modules/WalletPasses/Core/Model/PassField.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Model/PassStatus.php` → `custom/Espo/Modules/WalletPasses/Core/Model/PassStatus.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Model/PassType.php` → `custom/Espo/Modules/WalletPasses/Core/Model/PassType.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Util/Color.php` → `custom/Espo/Modules/WalletPasses/Core/Util/Color.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Util/LinkSigner.php` → `custom/Espo/Modules/WalletPasses/Core/Util/LinkSigner.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Util/Placeholder.php` → `custom/Espo/Modules/WalletPasses/Core/Util/Placeholder.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Util/QrCode.php` → `custom/Espo/Modules/WalletPasses/Core/Util/QrCode.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Util/SecureToken.php` → `custom/Espo/Modules/WalletPasses/Core/Util/SecureToken.php`
- `src/files/custom/Espo/Modules/WalletPasses/Core/Util/UserAgent.php` → `custom/Espo/Modules/WalletPasses/Core/Util/UserAgent.php`
- `src/files/custom/Espo/Modules/WalletPasses/Entities/WalletDevice.php` → `custom/Espo/Modules/WalletPasses/Entities/WalletDevice.php`
- `src/files/custom/Espo/Modules/WalletPasses/Entities/WalletPass.php` → `custom/Espo/Modules/WalletPasses/Entities/WalletPass.php`
- `src/files/custom/Espo/Modules/WalletPasses/Entities/WalletPassLog.php` → `custom/Espo/Modules/WalletPasses/Entities/WalletPassLog.php`
- `src/files/custom/Espo/Modules/WalletPasses/Entities/WalletPassTemplate.php` → `custom/Espo/Modules/WalletPasses/Entities/WalletPassTemplate.php`
- `src/files/custom/Espo/Modules/WalletPasses/Hooks/WalletPass/Lifecycle.php` → `custom/Espo/Modules/WalletPasses/Hooks/WalletPass/Lifecycle.php`
- `src/files/custom/Espo/Modules/WalletPasses/Hooks/WalletPassTemplate/PropagateChanges.php` → `custom/Espo/Modules/WalletPasses/Hooks/WalletPassTemplate/PropagateChanges.php`
- `src/files/custom/Espo/Modules/WalletPasses/Jobs/ExpirePasses.php` → `custom/Espo/Modules/WalletPasses/Jobs/ExpirePasses.php`
- `src/files/custom/Espo/Modules/WalletPasses/Jobs/PushPendingUpdates.php` → `custom/Espo/Modules/WalletPasses/Jobs/PushPendingUpdates.php`
- `src/files/custom/Espo/Modules/WalletPasses/MassAction/SendPasses.php` → `custom/Espo/Modules/WalletPasses/MassAction/SendPasses.php`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/autoload.json` → `custom/Espo/Modules/WalletPasses/Resources/autoload.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Account.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Account.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Admin.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Admin.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Contact.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Contact.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Global.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Global.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Lead.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Lead.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Settings.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/Settings.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletDevice.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletDevice.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletPassLog.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletPassLog.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletPassTemplate.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/en_US/WalletPassTemplate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Account.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Account.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Admin.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Admin.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Contact.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Contact.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Global.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Global.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Lead.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Lead.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Settings.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/Settings.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletDevice.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletDevice.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletPassLog.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletPassLog.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletPassTemplate.json` → `custom/Espo/Modules/WalletPasses/Resources/i18n/fr_FR/WalletPassTemplate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/Settings/walletPassesSettings.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/Settings/walletPassesSettings.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/detail.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/detail.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/detailSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/detailSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/list.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/list.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/listSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletDevice/listSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/detail.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/detail.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/detailSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/detailSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/filters.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/filters.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/list.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/list.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/listSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/listSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/massUpdate.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPass/massUpdate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/detail.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/detail.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/detailSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/detailSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/filters.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/filters.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/list.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/list.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/listSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassLog/listSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/detail.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/detail.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/detailSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/detailSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/filters.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/filters.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/list.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/list.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/listSmall.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/listSmall.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/massUpdate.json` → `custom/Espo/Modules/WalletPasses/Resources/layouts/WalletPassTemplate/massUpdate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/app/adminPanel.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/app/adminPanel.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/app/client.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/app/client.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/app/config.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/app/config.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/app/scheduledJobs.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/app/scheduledJobs.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/Account.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/Account.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/Contact.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/Contact.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/Lead.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/Lead.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletDevice.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletDevice.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletPassLog.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletPassLog.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletPassTemplate.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/clientDefs/WalletPassTemplate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityAcl/WalletDevice.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityAcl/WalletDevice.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityAcl/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityAcl/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Account.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Account.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Contact.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Contact.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Lead.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Lead.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Settings.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/Settings.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletDevice.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletDevice.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletPassLog.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletPassLog.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletPassTemplate.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/entityDefs/WalletPassTemplate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/recordDefs/Account.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/recordDefs/Account.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/recordDefs/Contact.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/recordDefs/Contact.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/recordDefs/Lead.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/recordDefs/Lead.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletDevice.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletDevice.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletPassLog.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletPassLog.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletPassTemplate.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/scopes/WalletPassTemplate.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/metadata/selectDefs/WalletPass.json` → `custom/Espo/Modules/WalletPasses/Resources/metadata/selectDefs/WalletPass.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/module.json` → `custom/Espo/Modules/WalletPasses/Resources/module.json`
- `src/files/custom/Espo/Modules/WalletPasses/Resources/routes.json` → `custom/Espo/Modules/WalletPasses/Resources/routes.json`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/ConfigTester.php` → `custom/Espo/Modules/WalletPasses/Tools/ConfigTester.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/EspoPassStore.php` → `custom/Espo/Modules/WalletPasses/Tools/EspoPassStore.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/HttpClientFactory.php` → `custom/Espo/Modules/WalletPasses/Tools/HttpClientFactory.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/PassDefinitionFactory.php` → `custom/Espo/Modules/WalletPasses/Tools/PassDefinitionFactory.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/PassIssuer.php` → `custom/Espo/Modules/WalletPasses/Tools/PassIssuer.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/PassLinks.php` → `custom/Espo/Modules/WalletPasses/Tools/PassLinks.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/PassLogger.php` → `custom/Espo/Modules/WalletPasses/Tools/PassLogger.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/SecretStore.php` → `custom/Espo/Modules/WalletPasses/Tools/SecretStore.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/UpdateNotifier.php` → `custom/Espo/Modules/WalletPasses/Tools/UpdateNotifier.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/WalletPassService.php` → `custom/Espo/Modules/WalletPasses/Tools/WalletPassService.php`
- `src/files/custom/Espo/Modules/WalletPasses/Tools/WalletSettings.php` → `custom/Espo/Modules/WalletPasses/Tools/WalletSettings.php`

## Package — frontend (copié dans `client/custom/modules/wallet-passes/`) (16)

- `src/files/client/custom/modules/wallet-passes/css/wallet-passes.css` → `client/custom/modules/wallet-passes/css/wallet-passes.css`
- `src/files/client/custom/modules/wallet-passes/res/templates/fields/wallet-field-list/detail.tpl` → `client/custom/modules/wallet-passes/res/templates/fields/wallet-field-list/detail.tpl`
- `src/files/client/custom/modules/wallet-passes/res/templates/fields/wallet-field-list/edit.tpl` → `client/custom/modules/wallet-passes/res/templates/fields/wallet-field-list/edit.tpl`
- `src/files/client/custom/modules/wallet-passes/res/templates/fields/wallet-field-list/list.tpl` → `client/custom/modules/wallet-passes/res/templates/fields/wallet-field-list/list.tpl`
- `src/files/client/custom/modules/wallet-passes/src/handlers/send-passes.js` → `client/custom/modules/wallet-passes/src/handlers/send-passes.js`
- `src/files/client/custom/modules/wallet-passes/src/handlers/wallet-pass/detail-actions.js` → `client/custom/modules/wallet-passes/src/handlers/wallet-pass/detail-actions.js`
- `src/files/client/custom/modules/wallet-passes/src/preview-renderer.js` → `client/custom/modules/wallet-passes/src/preview-renderer.js`
- `src/files/client/custom/modules/wallet-passes/src/views/admin/fields/credential-upload.js` → `client/custom/modules/wallet-passes/src/views/admin/fields/credential-upload.js`
- `src/files/client/custom/modules/wallet-passes/src/views/admin/modals/test-result.js` → `client/custom/modules/wallet-passes/src/views/admin/modals/test-result.js`
- `src/files/client/custom/modules/wallet-passes/src/views/admin/settings.js` → `client/custom/modules/wallet-passes/src/views/admin/settings.js`
- `src/files/client/custom/modules/wallet-passes/src/views/fields/wallet-field-list.js` → `client/custom/modules/wallet-passes/src/views/fields/wallet-field-list.js`
- `src/files/client/custom/modules/wallet-passes/src/views/wallet-pass/modals/links.js` → `client/custom/modules/wallet-passes/src/views/wallet-pass/modals/links.js`
- `src/files/client/custom/modules/wallet-passes/src/views/wallet-pass/modals/send-passes.js` → `client/custom/modules/wallet-passes/src/views/wallet-pass/modals/send-passes.js`
- `src/files/client/custom/modules/wallet-passes/src/views/wallet-pass/panels/preview.js` → `client/custom/modules/wallet-passes/src/views/wallet-pass/panels/preview.js`
- `src/files/client/custom/modules/wallet-passes/src/views/wallet-pass/panels/related-passes.js` → `client/custom/modules/wallet-passes/src/views/wallet-pass/panels/related-passes.js`
- `src/files/client/custom/modules/wallet-passes/src/views/wallet-pass/panels/stats.js` → `client/custom/modules/wallet-passes/src/views/wallet-pass/panels/stats.js`

## Tests (11)

- `phpunit.xml.dist`
- `tests/Support/InMemoryPassStore.php`
- `tests/Support/PassFactory.php`
- `tests/Support/TestCertificates.php`
- `tests/Unit/Apple/ApnsClientTest.php`
- `tests/Unit/Apple/PassJsonBuilderTest.php`
- `tests/Unit/Apple/PkpassGeneratorTest.php`
- `tests/Unit/Apple/WebServiceHandlerTest.php`
- `tests/Unit/Google/GoogleWalletTest.php`
- `tests/Unit/Util/UtilTest.php`
- `tests/bootstrap.php`

## Outillage et documentation (8)

- `.gitignore`
- `.phpunit.result.cache`
- `DEBUGGING.md`
- `README.md`
- `build.sh`
- `composer.json`
- `composer.lock`
- `docker/docker-compose.yml`
