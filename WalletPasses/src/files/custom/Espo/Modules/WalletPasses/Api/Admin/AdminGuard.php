<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Admin;

use Espo\Core\Exceptions\Forbidden;
use Espo\Entities\User;

class AdminGuard
{
    public function __construct(private User $user)
    {
    }

    public function check(): void
    {
        if (!$this->user->isAdmin()) {
            throw new Forbidden();
        }
    }
}
