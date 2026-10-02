<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;

/**
 * Google Wallet settings: Issuer ID, service account, allowed origins.
 */
final class GoogleConfig
{
    /**
     * @param string[] $origins
     */
    public function __construct(
        public readonly string $issuerId,
        public readonly ServiceAccount $serviceAccount,
        public readonly array $origins = [],
        public readonly string $language = 'fr',
    ) {
    }

    public function assertValid(): void
    {
        if (!preg_match('/^\d{10,25}$/', $this->issuerId)) {
            throw new ConfigurationException('Google Wallet Issuer ID must be numeric.');
        }
    }
}
