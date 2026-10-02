<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Definition;

/**
 * A measure.
 *
 * - native:    AGGREGATION(record expression) [WHERE record condition]
 * - aggregate: a formula over aggregate functions, e.g. (SUM(amount) - SUM(cost)) / SUM(amount) * 100
 * - display:   a formula over other measures' keys, evaluated after aggregation, e.g. margin / revenue * 100
 * - related:   aggregation over the records of a one-to-many / many-to-many link or a custom link
 *              (e.g. per account: SUM of its opportunities' amount), pre-aggregated per record so nothing is
 *              counted twice
 */
class Measure
{
    public const KIND_NATIVE = 'native';
    public const KIND_AGGREGATE = 'aggregate';
    public const KIND_DISPLAY = 'display';
    public const KIND_RELATED = 'related';

    public const RELATED_AGGREGATION_LIST = ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX'];

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
        /** Related measures: link name (to-many link of the entity at `from`, or a custom link name). */
        public readonly ?string $link = null,
        /** Related measures: path of the entity owning the link ('' = data source). */
        public readonly string $from = '',
    ) {}

    public function isAggregated(): bool
    {
        return $this->kind !== self::KIND_DISPLAY;
    }
}
