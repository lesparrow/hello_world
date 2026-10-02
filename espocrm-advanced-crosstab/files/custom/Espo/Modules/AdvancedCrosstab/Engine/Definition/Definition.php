<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Definition;

/**
 * A validated crosstab definition. Built only by DefinitionParser.
 */
class Definition
{
    /**
     * @param Dimension[] $rows
     * @param Dimension[] $columns
     * @param Measure[] $measures
     * @param ?array<string, mixed> $filter A normalized filter tree.
     */
    public function __construct(
        public readonly string $entityType,
        public readonly array $rows,
        public readonly array $columns,
        public readonly array $measures,
        public readonly ?array $filter,
        public readonly ?string $primaryFilter,
        public readonly bool $rowTotals,
        public readonly bool $columnTotals,
        public readonly bool $subtotals,
        /** @var array<string, mixed> Raw definition, used for caching. */
        public readonly array $raw,
        /** @var ?array<int, array<string, mixed>> EspoCRM where items, e.g. the filters of a list view. */
        public readonly ?array $listWhere = null,
        /** @var \Espo\Modules\AdvancedCrosstab\Engine\Schema\CustomJoin[] Custom links to any entity. */
        public readonly array $joins = [],
    ) {}

    public function getMeasure(string $key): ?Measure
    {
        foreach ($this->measures as $measure) {
            if ($measure->key === $key) {
                return $measure;
            }
        }

        return null;
    }

    /**
     * @return Measure[]
     */
    public function getAggregatedMeasures(): array
    {
        return array_values(array_filter($this->measures, fn (Measure $m) => $m->isAggregated()));
    }

    public function getDimension(string $id): ?Dimension
    {
        foreach (array_merge($this->rows, $this->columns) as $dimension) {
            if ($dimension->id === $id) {
                return $dimension;
            }
        }

        return null;
    }
}
