<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Entities;

use Espo\Core\ORM\Entity;

class WalletPass extends Entity
{
    public const ENTITY_TYPE = 'WalletPass';

    public const STATUS_ACTIVE = 'Active';
    public const STATUS_EXPIRED = 'Expired';
    public const STATUS_VOIDED = 'Voided';

    /**
     * Attributes rendered on the pass: changing one of them triggers re-generation + push.
     */
    public const CONTENT_ATTRIBUTE_LIST = [
        'templateId', 'holderName', 'barcodeValue', 'points', 'status', 'expiresAt',
    ];

    public function getSerialNumber(): string
    {
        return (string) $this->get('serialNumber');
    }

    public function getAuthenticationToken(): string
    {
        return (string) $this->get('authenticationToken');
    }

    public function getTemplateId(): ?string
    {
        return $this->get('templateId');
    }

    public function getStatus(): string
    {
        return (string) ($this->get('status') ?: self::STATUS_ACTIVE);
    }

    public function getGoogleObjectId(): ?string
    {
        return $this->get('googleObjectId') ?: null;
    }

    public function getContentUpdatedTimestamp(): int
    {
        $value = $this->get('contentUpdatedAt') ?: $this->get('modifiedAt') ?: $this->get('createdAt');

        return $value ? (int) strtotime($value . ' UTC') : 0;
    }
}
