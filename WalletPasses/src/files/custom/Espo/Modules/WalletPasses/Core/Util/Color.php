<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Util;

/**
 * Color helpers: EspoCRM stores "#RRGGBB", Apple expects "rgb(r, g, b)".
 */
final class Color
{
    public static function normalizeHex(?string $value): ?string
    {
        if ($value === null) {
            return null;
        }

        $value = trim($value);

        if (preg_match('/^#?([0-9a-fA-F]{3})$/', $value, $m)) {
            $c = $m[1];
            $value = $c[0] . $c[0] . $c[1] . $c[1] . $c[2] . $c[2];
        }

        if (!preg_match('/^#?([0-9a-fA-F]{6})$/', $value, $m)) {
            return null;
        }

        return '#' . strtoupper($m[1]);
    }

    public static function hexToAppleRgb(?string $value): ?string
    {
        $hex = self::normalizeHex($value);

        if ($hex === null) {
            return null;
        }

        [$r, $g, $b] = sscanf($hex, '#%02x%02x%02x');

        return sprintf('rgb(%d, %d, %d)', $r, $g, $b);
    }
}
