<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Entities;

use Espo\Core\ORM\Entity;

class WalletDevice extends Entity
{
    public const ENTITY_TYPE = 'WalletDevice';

    public function getDeviceLibraryIdentifier(): string
    {
        return (string) $this->get('deviceLibraryIdentifier');
    }

    public function getPushToken(): ?string
    {
        return $this->get('pushToken') ?: null;
    }
}
