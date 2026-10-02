<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;

/**
 * Minimal RS256 JSON Web Token encoder (no third-party dependency).
 */
final class Jwt
{
    /**
     * @param array<string, mixed> $claims
     */
    public static function encodeRs256(array $claims, string $privateKeyPem, ?string $keyId = null): string
    {
        $header = ['alg' => 'RS256', 'typ' => 'JWT'];

        if ($keyId !== null) {
            $header['kid'] = $keyId;
        }

        $input = self::base64Url((string) json_encode($header)) . '.' .
            self::base64Url((string) json_encode($claims, JSON_UNESCAPED_SLASHES));

        $key = openssl_pkey_get_private($privateKeyPem);

        if ($key === false || !openssl_sign($input, $signature, $key, OPENSSL_ALGO_SHA256)) {
            throw new WalletException('Unable to sign JWT with the service account key.');
        }

        return $input . '.' . self::base64Url($signature);
    }

    public static function base64Url(string $data): string
    {
        return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
    }

    /**
     * @return array<string, mixed>
     */
    public static function decodePayload(string $jwt): array
    {
        $parts = explode('.', $jwt);

        if (count($parts) !== 3) {
            return [];
        }

        $json = base64_decode(strtr($parts[1], '-_', '+/'), true);

        return is_string($json) ? (json_decode($json, true) ?: []) : [];
    }
}
