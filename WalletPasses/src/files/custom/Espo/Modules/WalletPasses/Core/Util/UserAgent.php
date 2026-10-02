<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Util;

/**
 * Detects the wallet platform from a User-Agent (used by the smart link / QR code).
 */
final class UserAgent
{
    public const PLATFORM_APPLE = 'apple';
    public const PLATFORM_GOOGLE = 'google';
    public const PLATFORM_OTHER = 'other';

    public static function detectPlatform(?string $userAgent): string
    {
        $ua = strtolower((string) $userAgent);

        if ($ua === '') {
            return self::PLATFORM_OTHER;
        }

        if (preg_match('/iphone|ipad|ipod|watch os|watchos/', $ua)) {
            return self::PLATFORM_APPLE;
        }

        // Safari on macOS also opens .pkpass files natively.
        if (str_contains($ua, 'macintosh') && str_contains($ua, 'safari') && !str_contains($ua, 'chrome')) {
            return self::PLATFORM_APPLE;
        }

        if (str_contains($ua, 'android')) {
            return self::PLATFORM_GOOGLE;
        }

        return self::PLATFORM_OTHER;
    }
}
