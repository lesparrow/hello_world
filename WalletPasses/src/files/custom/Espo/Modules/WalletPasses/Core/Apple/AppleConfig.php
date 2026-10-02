<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple;

use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;

/**
 * Apple Wallet credentials and identifiers. Values come from the admin settings — never hard-coded.
 */
final class AppleConfig
{
    public function __construct(
        public readonly string $teamIdentifier,
        public readonly string $passTypeIdentifier,
        public readonly string $p12Contents,
        public readonly string $p12Password,
        public readonly ?string $wwdrPemPath = null,
        public readonly ?string $webServiceUrl = null,
        public readonly string $apnsHost = 'https://api.push.apple.com',
        public readonly ?string $apnsPushType = null,
    ) {
    }

    public function assertValid(): void
    {
        if (!preg_match('/^[A-Z0-9]{10}$/', $this->teamIdentifier)) {
            throw new ConfigurationException('Apple Team ID must be 10 upper-case alphanumeric characters.');
        }

        if (!str_starts_with($this->passTypeIdentifier, 'pass.')) {
            throw new ConfigurationException('Apple Pass Type ID must start with "pass.".');
        }

        if ($this->p12Contents === '') {
            throw new ConfigurationException('Apple pass certificate (.p12) is not uploaded.');
        }

        if ($this->webServiceUrl !== null && !str_starts_with($this->webServiceUrl, 'https://')) {
            throw new ConfigurationException('Apple requires an HTTPS webServiceURL.');
        }
    }
}
