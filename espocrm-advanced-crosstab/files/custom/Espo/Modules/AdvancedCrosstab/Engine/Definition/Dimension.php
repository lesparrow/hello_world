<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Definition;

/**
 * A row or column dimension: an entity field (possibly through relations) or a record formula.
 */
class Dimension
{
    public const TYPE_FIELD = 'field';
    public const TYPE_FORMULA = 'formula';

    public const GRANULARITY_LIST = [
        'year', 'quarter', 'quarterNumber', 'yearMonth', 'month', 'week', 'day', 'dayOfWeek',
    ];

    public function __construct(
        public readonly string $id,
        public readonly string $type,
        public readonly ?string $path,
        public readonly ?string $formula,
        public readonly ?string $granularity,
        public readonly ?string $label,
        /** 'natural' | 'label' | 'measure' */
        public readonly string $sortBy,
        public readonly ?string $sortMeasure,
        /** 'asc' | 'desc' */
        public readonly string $sortDirection,
        /** null | 'top' | 'bottom' */
        public readonly ?string $limitType,
        public readonly int $limitCount,
        public readonly ?string $limitMeasure,
    ) {}
}
