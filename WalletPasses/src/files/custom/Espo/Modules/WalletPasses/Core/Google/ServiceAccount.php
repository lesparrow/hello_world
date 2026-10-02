<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;

/**
 * Parsed Google Cloud service account key (JSON).
 */
final class ServiceAccount
{
    public function __construct(
        public readonly string $clientEmail,
        public readonly string $privateKey,
        public readonly string $privateKeyId,
        public readonly string $tokenUri = 'https://oauth2.googleapis.com/token',
    ) {
    }

    public static function fromJson(string $json): self
    {
        $data = json_decode($json, true);

        if (!is_array($data) || ($data['type'] ?? null) !== 'service_account') {
            throw new ConfigurationException('The Google key file is not a service account JSON key.');
        }

        foreach (['client_email', 'private_key', 'private_key_id'] as $key) {
            if (empty($data[$key]) || !is_string($data[$key])) {
                throw new ConfigurationException(sprintf('Service account JSON: "%s" is missing.', $key));
            }
        }

        if (openssl_pkey_get_private($data['private_key']) === false) {
            throw new ConfigurationException('Service account JSON: private key is invalid.');
        }

        return new self(
            $data['client_email'],
            $data['private_key'],
            $data['private_key_id'],
            is_string($data['token_uri'] ?? null) ? $data['token_uri'] : 'https://oauth2.googleapis.com/token',
        );
    }
}
