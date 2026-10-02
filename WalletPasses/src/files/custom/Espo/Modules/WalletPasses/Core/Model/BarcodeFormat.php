<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Model;

/**
 * Barcode formats supported by both wallets.
 */
enum BarcodeFormat: string
{
    case QR = 'QR';
    case PDF417 = 'PDF417';
    case Aztec = 'Aztec';
    case Code128 = 'Code128';

    public static function fromStringOrDefault(?string $value): self
    {
        return self::tryFrom((string) $value) ?? self::QR;
    }

    public function apple(): string
    {
        return match ($this) {
            self::QR => 'PKBarcodeFormatQR',
            self::PDF417 => 'PKBarcodeFormatPDF417',
            self::Aztec => 'PKBarcodeFormatAztec',
            self::Code128 => 'PKBarcodeFormatCode128',
        };
    }

    public function google(): string
    {
        return match ($this) {
            self::QR => 'QR_CODE',
            self::PDF417 => 'PDF_417',
            self::Aztec => 'AZTEC',
            self::Code128 => 'CODE_128',
        };
    }

    /**
     * The legacy "barcode" key (iOS < 9) does not support Code 128.
     */
    public function supportedByLegacyAppleKey(): bool
    {
        return $this !== self::Code128;
    }
}
