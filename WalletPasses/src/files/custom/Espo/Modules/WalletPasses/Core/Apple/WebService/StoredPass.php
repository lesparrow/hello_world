<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple\WebService;

/**
 * Minimal view of a persisted pass needed by the Apple web service.
 */
final class StoredPass
{
    public function __construct(
        public readonly string $id,
        public readonly string $serialNumber,
        public readonly string $authenticationToken,
        public readonly int $updatedAt,
    ) {
    }
}
