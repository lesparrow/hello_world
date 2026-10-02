<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use DateTimeImmutable;
use Espo\Modules\WalletPasses\Core\Apple\Certificate;
use Espo\Modules\WalletPasses\Core\Google\GoogleWalletService;
use Throwable;

/**
 * "Test configuration" button: checks every prerequisite and returns a human readable report.
 */
class ConfigTester
{
    public function __construct(
        private WalletSettings $settings,
        private SecretStore $secretStore,
        private HttpClientFactory $httpClientFactory,
    ) {
    }

    /**
     * @return list<array{section: string, check: string, ok: bool, message: string}>
     */
    public function run(): array
    {
        $report = [];

        $add = function (string $section, string $check, bool $ok, string $message) use (&$report): void {
            $report[] = compact('section', 'check', 'ok', 'message');
        };

        $baseUrl = $this->settings->getPublicBaseUrl();
        $add(
            'General',
            'Public URL',
            str_starts_with($baseUrl, 'https://'),
            $baseUrl . (str_starts_with($baseUrl, 'https://') ? '' : ' — HTTPS is required by Apple & Google')
        );

        foreach (['openssl', 'zip', 'curl', 'gd'] as $ext) {
            $loaded = extension_loaded($ext);
            $add('General', "PHP extension $ext", $loaded, $loaded ? 'loaded' : 'missing');
        }

        if ($this->settings->isAppleEnabled()) {
            $this->testApple($add);
        } else {
            $add('Apple Wallet', 'Enabled', false, 'Disabled');
        }

        if ($this->settings->isGoogleEnabled()) {
            $this->testGoogle($add);
        } else {
            $add('Google Wallet', 'Enabled', false, 'Disabled');
        }

        return $report;
    }

    private function testApple(callable $add): void
    {
        try {
            $config = $this->settings->getAppleConfig();
            $add('Apple Wallet', 'Settings', true, "Team $config->teamIdentifier, $config->passTypeIdentifier");
        } catch (Throwable $e) {
            $add('Apple Wallet', 'Settings', false, $e->getMessage());

            return;
        }

        try {
            $pair = Certificate::readP12($config->p12Contents, $config->p12Password);
            $info = Certificate::describe($pair['cert']);
            $daysLeft = (int) floor(($info['validTo']->getTimestamp() - time()) / 86400);

            $add(
                'Apple Wallet',
                'Pass certificate',
                $daysLeft > 0,
                sprintf('%s — expires %s (%d days)', $info['subject'], $info['validTo']->format('Y-m-d'), $daysLeft)
            );

            if ($info['uid'] !== null) {
                $add(
                    'Apple Wallet',
                    'Certificate matches Pass Type ID',
                    $info['uid'] === $config->passTypeIdentifier,
                    'Certificate UID: ' . $info['uid']
                );
            }

            if (!openssl_x509_check_private_key($pair['cert'], $pair['pkey'])) {
                $add('Apple Wallet', 'Private key', false, 'The private key does not match the certificate.');
            }
        } catch (Throwable $e) {
            $add('Apple Wallet', 'Pass certificate', false, $e->getMessage());
        }

        if ($this->secretStore->has(SecretStore::APPLE_WWDR)) {
            try {
                $info = Certificate::describe((string) $this->secretStore->get(SecretStore::APPLE_WWDR));
                $add(
                    'Apple Wallet',
                    'WWDR certificate',
                    $info['validTo'] > new DateTimeImmutable(),
                    $info['subject'] . ' — expires ' . $info['validTo']->format('Y-m-d')
                );
            } catch (Throwable $e) {
                $add('Apple Wallet', 'WWDR certificate', false, $e->getMessage());
            }
        } else {
            $add('Apple Wallet', 'WWDR certificate', true, 'Not uploaded — bundled WWDR G4 (pkpass/pkpass) is used.');
        }

        $add(
            'Apple Wallet',
            'Web service URL',
            $config->webServiceUrl !== null,
            $config->webServiceUrl ?? 'Not HTTPS — passes will be issued without automatic updates.'
        );

        $add(
            'Apple Wallet',
            'HTTP/2 (APNs)',
            defined('CURL_HTTP_VERSION_2_0') &&
            (curl_version()['features'] & CURL_VERSION_HTTP2) !== 0,
            'cURL ' . curl_version()['version']
        );
    }

    private function testGoogle(callable $add): void
    {
        try {
            $config = $this->settings->getGoogleConfig();
            $add(
                'Google Wallet',
                'Settings',
                true,
                "Issuer $config->issuerId, " . $config->serviceAccount->clientEmail
            );
        } catch (Throwable $e) {
            $add('Google Wallet', 'Settings', false, $e->getMessage());

            return;
        }

        try {
            $service = new GoogleWalletService($config, $this->httpClientFactory->create());
            $add('Google Wallet', 'API access', true, $service->testConnection());
        } catch (Throwable $e) {
            $add('Google Wallet', 'API access', false, $e->getMessage());
        }
    }
}
