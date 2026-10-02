<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple;

final class PushResult
{
    public function __construct(
        public readonly string $pushToken,
        public readonly int $statusCode,
        public readonly ?string $reason = null,
    ) {
    }

    public function isSuccess(): bool
    {
        return $this->statusCode === 200;
    }

    /**
     * 410 Unregistered or 400 BadDeviceToken: the token must be discarded.
     */
    public function isTokenInvalid(): bool
    {
        return $this->statusCode === 410 ||
            ($this->statusCode === 400 && in_array($this->reason, ['BadDeviceToken', 'DeviceTokenNotForTopic'], true));
    }
}
