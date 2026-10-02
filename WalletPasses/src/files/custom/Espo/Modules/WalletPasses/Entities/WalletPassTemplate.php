<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Entities;

use Espo\Core\ORM\Entity;

class WalletPassTemplate extends Entity
{
    public const ENTITY_TYPE = 'WalletPassTemplate';

    /**
     * Attributes whose change requires every issued pass to be re-generated and pushed.
     */
    public const CONTENT_ATTRIBUTE_LIST = [
        'passType', 'organizationName', 'description', 'logoText', 'backgroundColor', 'foregroundColor',
        'labelColor', 'barcodeFormat', 'barcodeMessage', 'barcodeAltText', 'iconId', 'logoId', 'stripId',
        'backgroundId', 'thumbnailId', 'frontFields', 'backFields', 'relevantDate',
    ];

    public const IMAGE_FIELD_LIST = ['icon', 'logo', 'strip', 'background', 'thumbnail'];

    public function getName(): string
    {
        return (string) $this->get('name');
    }

    public function isActive(): bool
    {
        return (bool) $this->get('isActive');
    }

    public function getPassType(): string
    {
        return (string) ($this->get('passType') ?: 'generic');
    }

    public function getImageId(string $field): ?string
    {
        return $this->get($field . 'Id') ?: null;
    }

    /**
     * @return list<array<string, mixed>>
     */
    public function getFieldList(string $attribute): array
    {
        $list = $this->get($attribute);

        if (!is_array($list)) {
            return [];
        }

        return array_values(array_map(fn ($item) => (array) $item, $list));
    }
}
