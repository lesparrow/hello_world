<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Model;

use DateTimeImmutable;

/**
 * Everything needed to render a pass for Apple or Google, fully resolved
 * (template + pass instance + placeholders). Independent of EspoCRM.
 */
final class PassDefinition
{
    /**
     * @param PassField[] $fields
     * @param array<string, string> $images Binary PNG contents keyed by Apple image name
     *   (icon, logo, strip, background, thumbnail).
     * @param array<string, string> $imageUrls Public HTTPS URLs keyed by image name (used by Google).
     */
    public function __construct(
        public readonly string $templateId,
        public readonly PassType $passType,
        public readonly string $serialNumber,
        public readonly string $authenticationToken,
        public readonly string $organizationName,
        public readonly string $description,
        public readonly ?string $logoText,
        public readonly ?string $backgroundColor,
        public readonly ?string $foregroundColor,
        public readonly ?string $labelColor,
        public readonly BarcodeFormat $barcodeFormat,
        public readonly string $barcodeMessage,
        public readonly ?string $barcodeAltText,
        public readonly array $fields,
        public readonly PassStatus $status,
        public readonly ?DateTimeImmutable $expiresAt,
        public readonly ?DateTimeImmutable $relevantDate,
        public readonly DateTimeImmutable $updatedAt,
        public readonly ?string $holderName = null,
        public readonly array $images = [],
        public readonly array $imageUrls = [],
    ) {
    }

    /**
     * @return PassField[]
     */
    public function fieldsInSection(string $section): array
    {
        return array_values(array_filter($this->fields, fn (PassField $f) => $f->section === $section));
    }
}
