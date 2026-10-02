<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Classes\Select\WalletPass\PrimaryFilters;

use Espo\Core\Select\Primary\Filter;
use Espo\ORM\Query\SelectBuilder;

class PushPending implements Filter
{
    public function apply(SelectBuilder $queryBuilder): void
    {
        $queryBuilder->where(['pushPending' => true]);
    }
}
