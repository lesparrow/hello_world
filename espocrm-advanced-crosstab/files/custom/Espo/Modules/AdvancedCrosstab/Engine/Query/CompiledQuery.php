<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Query;

use Espo\Modules\AdvancedCrosstab\Engine\Definition\Definition;
use Espo\ORM\Query\Part\Expression;
use Espo\ORM\Query\Select;

class CompiledQuery
{
    /**
     * @param CompiledDimension[] $rows
     * @param CompiledDimension[] $columns
     * @param array<string, Expression> $measureExpressions Aggregated measures by key.
     * @param array<string, ?Expression> $measureConditions Record-level conditions of native measures, by key.
     */
    public function __construct(
        public readonly Definition $definition,
        public readonly Select $baseQuery,
        public readonly array $rows,
        public readonly array $columns,
        public readonly array $measureExpressions,
        public readonly array $measureConditions,
    ) {}
}
