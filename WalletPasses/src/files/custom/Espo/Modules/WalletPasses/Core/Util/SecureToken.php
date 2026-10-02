<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Util;

/**
 * Cryptographically secure identifiers.
 */
final class SecureToken
{
    /**
     * Apple requires at least 16 characters for authenticationToken. 32 bytes => 64 hex chars.
     */
    public static function authenticationToken(): string
    {
        return bin2hex(random_bytes(32));
    }

    /**
     * Unique, non-guessable serial number (Apple allows any string, Google any [A-Za-z0-9._-]).
     */
    public static function serialNumber(): string
    {
        return strtoupper(bin2hex(random_bytes(10)));
    }

    public static function equals(string $known, string $provided): bool
    {
        return $known !== '' && hash_equals($known, $provided);
    }
}
