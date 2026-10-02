<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Util;

use BaconQrCode\Renderer\GDLibRenderer;
use BaconQrCode\Writer;

/**
 * PNG QR code generation (bacon/bacon-qr-code, GD back-end — no Imagick required).
 */
final class QrCode
{
    public static function png(string $content, int $size = 320, int $margin = 2): string
    {
        $size = max(64, min($size, 2048));

        return (new Writer(new GDLibRenderer($size, $margin)))->writeString($content);
    }
}
