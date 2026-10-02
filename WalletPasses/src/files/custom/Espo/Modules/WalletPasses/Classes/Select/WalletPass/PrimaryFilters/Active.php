<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Classes\Select\WalletPass\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\ORM\Query\SelectBuilder;

class Active implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['status' => WalletPass::STATUS_ACTIVE]);
    }
}
