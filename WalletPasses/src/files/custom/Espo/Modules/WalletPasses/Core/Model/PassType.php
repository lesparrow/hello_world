<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Model;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;

/**
 * Pass types handled by the extension and their Apple / Google equivalents.
 */
enum PassType: string
{
    case Generic = 'generic';
    case Coupon = 'coupon';
    case EventTicket = 'eventTicket';
    case StoreCard = 'storeCard';
    case LoyaltyCard = 'loyaltyCard';

    public static function fromString(string $value): self
    {
        return self::tryFrom($value)
            ?? throw new WalletException(sprintf('Unsupported pass type "%s".', $value));
    }

    /**
     * Apple pass style key used in pass.json (loyalty cards are store cards for Apple).
     */
    public function appleStyle(): string
    {
        return match ($this) {
            self::Generic => 'generic',
            self::Coupon => 'coupon',
            self::EventTicket => 'eventTicket',
            self::StoreCard, self::LoyaltyCard => 'storeCard',
        };
    }

    /**
     * Google Wallet vertical: used to build REST resource names (genericClass, offerObject, …).
     */
    public function googleVertical(): string
    {
        return match ($this) {
            self::Generic => 'generic',
            self::Coupon => 'offer',
            self::EventTicket => 'eventTicket',
            self::StoreCard, self::LoyaltyCard => 'loyalty',
        };
    }
}
