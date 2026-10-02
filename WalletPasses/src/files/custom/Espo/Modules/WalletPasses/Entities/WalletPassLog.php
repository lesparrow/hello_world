<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Entities;

use Espo\Core\ORM\Entity;

class WalletPassLog extends Entity
{
    public const ENTITY_TYPE = 'WalletPassLog';

    public const EVENT_CREATED = 'Created';
    public const EVENT_UPDATED = 'Updated';
    public const EVENT_DOWNLOADED = 'Downloaded';
    public const EVENT_PUSH_SENT = 'PushSent';
    public const EVENT_PUSH_FAILED = 'PushFailed';
    public const EVENT_DEVICE_REGISTERED = 'DeviceRegistered';
    public const EVENT_DEVICE_UNREGISTERED = 'DeviceUnregistered';
    public const EVENT_SCANNED = 'Scanned';
    public const EVENT_GOOGLE_SYNCED = 'GoogleSynced';
    public const EVENT_GOOGLE_ERROR = 'GoogleError';
    public const EVENT_UNAUTHORIZED = 'Unauthorized';
    public const EVENT_DEVICE_LOG = 'DeviceLog';
    public const EVENT_ERROR = 'Error';
}
