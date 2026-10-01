<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Definition;

/**
 * A measure.
 *
 * - native:    AGGREGATION(record expression) [WHERE record condition]
 * - aggregate: a formula over aggregate functions, e.g. (SUM(amount) - SUM(cost)) / SUM(amount) * 100
 * - display:   a formula over other measures' keys, evaluated after aggregation, e.g. margin / revenue * 100
 */
class Measure
{
    public const KIND_NATIVE = 'native';
    public const KIND_AGGREGATE = 'aggregate';
    public const KIND_DISPLAY = 'display';

    public const AGGREGATION_LIST = ['COUNT', 'COUNT_DISTINCT', 'SUM', 'AVG', 'MIN', 'MAX'];

    public const FORMAT_LIST = ['number', 'integer', 'decimal', 'percent', 'currency', 'duration', 'date'];

    public const COMPARE_LIST = ['previous', 'previousYear'];

    /**
     * @param array{type: string, decimals: ?int, currency: ?string, prefix: string, suffix: string} $format
     */
    public function __construct(
        public readonly string $key,
        public readonly string $label,
        public readonly string $kind,
        public readonly ?string $aggregation,
        public readonly ?string $expression,
        public readonly ?string $condition,
        public readonly ?string $formula,
        public readonly array $format,
        public readonly bool $hidden,
        public readonly ?string $compare,
        /** 'percent' | 'difference' */
        public readonly string $compareMode,
    ) {}

    public function isAggregated(): bool
    {
        return $this->kind !== self::KIND_DISPLAY;
    }
}
