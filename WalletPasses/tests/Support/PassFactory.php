<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Support;

use DateTimeImmutable;
use Espo\Modules\WalletPasses\Core\Model\BarcodeFormat;
use Espo\Modules\WalletPasses\Core\Model\PassDefinition;
use Espo\Modules\WalletPasses\Core\Model\PassField;
use Espo\Modules\WalletPasses\Core\Model\PassStatus;
use Espo\Modules\WalletPasses\Core\Model\PassType;

final class PassFactory
{
    /**
     * @param array<string, mixed> $overrides
     */
    public static function create(array $overrides = []): PassDefinition
    {
        $png = self::png();

        $args = array_merge([
            'templateId' => 'tpl1',
            'passType' => PassType::LoyaltyCard,
            'serialNumber' => 'SERIAL123',
            'authenticationToken' => str_repeat('a', 64),
            'organizationName' => 'ACME',
            'description' => 'ACME loyalty card',
            'logoText' => 'ACME',
            'backgroundColor' => '#1E3A5F',
            'foregroundColor' => '#FFFFFF',
            'labelColor' => '#C8D3E0',
            'barcodeFormat' => BarcodeFormat::QR,
            'barcodeMessage' => 'SERIAL123',
            'barcodeAltText' => 'SERIAL123',
            'fields' => [
                new PassField('points', 'Points', '120', PassField::SECTION_PRIMARY),
                new PassField('name', 'Member', 'Jane Doe', PassField::SECTION_SECONDARY, 'right'),
                new PassField('name', 'Duplicate key', 'x', PassField::SECTION_AUXILIARY),
                new PassField('terms', 'Terms', 'No cash value', PassField::SECTION_BACK),
            ],
            'status' => PassStatus::Active,
            'expiresAt' => new DateTimeImmutable('2030-01-01T00:00:00+00:00'),
            'relevantDate' => null,
            'updatedAt' => new DateTimeImmutable('2026-01-01T10:00:00+00:00'),
            'holderName' => 'Jane Doe',
            'images' => ['icon' => $png, 'logo' => $png],
            'imageUrls' => ['logo' => 'https://crm.example.com/logo.png'],
        ], $overrides);

        return new PassDefinition(...$args);
    }

    public static function png(): string
    {
        $image = imagecreatetruecolor(4, 4);
        ob_start();
        imagepng($image);

        return (string) ob_get_clean();
    }
}
