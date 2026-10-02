<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Utils\Config;
use Espo\Modules\WalletPasses\Core\Apple\AppleConfig;
use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;
use Espo\Modules\WalletPasses\Core\Google\GoogleConfig;
use Espo\Modules\WalletPasses\Core\Google\ServiceAccount;
use Espo\Modules\WalletPasses\Core\Util\LinkSigner;

/**
 * Single entry point to the extension settings (EspoCRM config + encrypted SecretStore).
 */
class WalletSettings
{
    private ?string $wwdrTempFile = null;

    public function __construct(
        private Config $config,
        private SecretStore $secretStore,
    ) {
    }

    public function __destruct()
    {
        if ($this->wwdrTempFile !== null) {
            @unlink($this->wwdrTempFile);
        }
    }

    public function isAppleEnabled(): bool
    {
        return (bool) $this->config->get('walletAppleEnabled');
    }

    public function isGoogleEnabled(): bool
    {
        return (bool) $this->config->get('walletGoogleEnabled');
    }

    public function isApplePushEnabled(): bool
    {
        return $this->isAppleEnabled() && $this->config->get('walletApplePushEnabled', true);
    }

    public function getPassTypeIdentifier(): string
    {
        return trim((string) $this->config->get('walletApplePassTypeId'));
    }

    /**
     * Public base URL of the CRM (must be reachable by Apple/Google and by the end users' phones).
     */
    public function getPublicBaseUrl(): string
    {
        $url = (string) ($this->config->get('walletPublicBaseUrl') ?: $this->config->get('siteUrl'));

        return rtrim($url, '/');
    }

    /**
     * webServiceURL written into pass.json. Apple appends "/v1/…" itself.
     */
    public function getWebServiceUrl(): string
    {
        $url = (string) $this->config->get('walletAppleWebServiceUrl');

        return $url !== '' ? rtrim($url, '/') : $this->getPublicBaseUrl() . '/api/v1/WalletService';
    }

    public function getAppleConfig(): AppleConfig
    {
        if (!$this->isAppleEnabled()) {
            throw new ConfigurationException('Apple Wallet is disabled in the Wallet settings.');
        }

        $p12 = $this->secretStore->get(SecretStore::APPLE_P12);

        if ($p12 === null) {
            throw new ConfigurationException('Apple pass certificate (.p12) has not been uploaded.');
        }

        if ($this->wwdrTempFile === null && $this->secretStore->has(SecretStore::APPLE_WWDR)) {
            $this->wwdrTempFile = $this->secretStore->exportToTempFile(SecretStore::APPLE_WWDR);
        }

        $webServiceUrl = $this->getWebServiceUrl();

        $config = new AppleConfig(
            teamIdentifier: trim((string) $this->config->get('walletAppleTeamId')),
            passTypeIdentifier: $this->getPassTypeIdentifier(),
            p12Contents: $p12,
            p12Password: (string) $this->secretStore->get(SecretStore::APPLE_P12_PASSWORD),
            wwdrPemPath: $this->wwdrTempFile,
            // Wallet refuses non-HTTPS web services: omit it (no updates) rather than break the pass.
            webServiceUrl: str_starts_with($webServiceUrl, 'https://') ? $webServiceUrl : null,
            apnsPushType: $this->config->get('walletApplePushType') ?: null,
        );

        $config->assertValid();

        return $config;
    }

    public function getGoogleConfig(): GoogleConfig
    {
        if (!$this->isGoogleEnabled()) {
            throw new ConfigurationException('Google Wallet is disabled in the Wallet settings.');
        }

        $json = $this->secretStore->get(SecretStore::GOOGLE_SERVICE_ACCOUNT);

        if ($json === null) {
            throw new ConfigurationException('Google service account JSON key has not been uploaded.');
        }

        $origins = array_values(array_filter(
            (array) ($this->config->get('walletGoogleOrigins') ?? []),
            fn ($o) => is_string($o) && $o !== ''
        ));

        if ($origins === []) {
            $origins = [$this->getPublicBaseUrl()];
        }

        $config = new GoogleConfig(
            issuerId: trim((string) $this->config->get('walletGoogleIssuerId')),
            serviceAccount: ServiceAccount::fromJson($json),
            origins: $origins,
            language: (string) ($this->config->get('walletGoogleLanguage') ?: 'fr'),
        );

        $config->assertValid();

        return $config;
    }

    public function getLinkSigner(): LinkSigner
    {
        return new LinkSigner($this->secretStore->getLinkSecret());
    }

    public function getLogRetentionDays(): int
    {
        return (int) $this->config->get('walletLogRetentionDays', 180);
    }
}
