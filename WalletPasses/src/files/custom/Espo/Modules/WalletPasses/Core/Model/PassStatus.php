<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Model;

enum PassStatus: string
{
    case Active = 'Active';
    case Expired = 'Expired';
    case Voided = 'Voided';

    public static function fromStringOrDefault(?string $value): self
    {
        return self::tryFrom((string) $value) ?? self::Active;
    }

    public function googleState(): string
    {
        return match ($this) {
            self::Active => 'ACTIVE',
            self::Expired => 'EXPIRED',
            self::Voided => 'INACTIVE',
        };
    }
}
