<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Pivot;

use Espo\Modules\AdvancedCrosstab\Engine\Definition\Definition;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\Measure;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\DisplayEvaluator;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Espo\Modules\AdvancedCrosstab\Engine\Query\CompiledDimension;
use Espo\Modules\AdvancedCrosstab\Engine\Query\CompiledQuery;
use Espo\Modules\AdvancedCrosstab\Engine\Query\QueryCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Query\UserContext;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\Part\Selection;
use PDO;

/**
 * Computes a crosstab entirely in the database.
 *
 * For R row and C column dimensions, the cells, subtotals and totals are the grouping sets
 * (rows[0..i], columns[0..j]). Each needed set is one GROUP BY query over the same ACL-restricted,
 * filtered base query, so every level — cell, subtotal, total — is aggregated from records.
 * This keeps non-additive measures (AVG, COUNT DISTINCT, ratios such as margin %) correct at every level.
 *
 * The browser receives only aggregated values.
 */
class PivotEngine
{
    private const TOTAL = '[]';

    private int $queryCount = 0;

    public function __construct(
        private QueryCompiler $queryCompiler,
        private EntityManager $entityManager,
        private DisplayEvaluator $displayEvaluator,
        private LabelResolver $labelResolver,
        private TreeBuilder $treeBuilder,
        private ResultCache $cache,
        private UserContext $userContext,
        private Limits $limits,
    ) {}

    /**
     * @return array<string, mixed>
     */
    public function run(Definition $definition, bool $useCache = true): array
    {
        $cacheKey = $this->cache->key($definition->raw, $this->userContext->getUser()->getId());

        if ($useCache && ($cached = $this->cache->get($cacheKey))) {
            $cached['fromCache'] = true;

            return $cached;
        }

        $start = microtime(true);
        $this->queryCount = 0;

        $compiled = $this->queryCompiler->compile($definition);

        $R = count($compiled->rows);
        $C = count($compiled->columns);

        $values = [];
        $truncated = false;

        $sets = $this->determineSets($definition, $R, $C);

        // The detail level first: when every measure is decomposable, the other levels are rolled up from it
        // in memory instead of scanning the table again.
        $truncated = $this->fetchSet($compiled, $R, $C, $values);

        $rollUp = !$truncated && $this->isDecomposable($definition);

        foreach ($sets as [$i, $j]) {
            if ($i === $R && $j === $C) {
                continue;
            }

            if ($rollUp) {
                $this->rollUp($definition, $values, $R, $C, $i, $j);

                continue;
            }

            $truncated = $this->fetchSet($compiled, $i, $j, $values) || $truncated;
        }

        $this->computeDisplayMeasures($definition, $values);

        // Header trees are built from the deepest level of each axis.
        $rowPaths = [];
        $columnPaths = [];

        foreach ($values as $rowId => $columnsData) {
            $rowPath = json_decode($rowId, true);

            if (count($rowPath) === $R) {
                $rowPaths[$rowId] = $rowPath;
            }

            foreach (array_keys($columnsData) as $columnId) {
                $columnPath = json_decode($columnId, true);

                if (count($columnPath) === $C) {
                    $columnPaths[$columnId] = $columnPath;
                }
            }
        }

        $rowLabels = $this->resolveLabels($compiled->rows, $rowPaths);
        $columnLabels = $this->resolveLabels($compiled->columns, $columnPaths);

        $this->treeBuilder->setLocale(str_replace('_', '-', $this->userContext->getLanguage()));

        $rowTree = $R ? $this->treeBuilder->build(
            array_values($rowPaths),
            $compiled->rows,
            $rowLabels,
            fn (array $path, string $measure) => $values[self::id($path)][self::TOTAL][$measure] ?? null
        ) : [];

        $columnTree = $C ? $this->treeBuilder->build(
            array_values($columnPaths),
            $compiled->columns,
            $columnLabels,
            fn (array $path, string $measure) => $values[self::TOTAL][self::id($path)][$measure] ?? null
        ) : [];

        $this->computeComparisons($compiled, $values, $rowPaths, $columnPaths);

        $valueColumns = [];

        foreach ($definition->measures as $measure) {
            if ($measure->hidden) {
                continue;
            }

            $valueColumns[] = ['measure' => $measure->key, 'variant' => 'value'];

            if ($measure->compare) {
                $valueColumns[] = ['measure' => $measure->key, 'variant' => 'compare'];
            }
        }

        $cells = $this->buildCells($values, $valueColumns, $rowTree, $columnTree);

        $result = [
            'entityType' => $definition->entityType,
            'rowDimensions' => array_map(fn ($d) => $this->describeDimension($d), $compiled->rows),
            'columnDimensions' => array_map(fn ($d) => $this->describeDimension($d), $compiled->columns),
            'measures' => array_map(fn (Measure $m) => [
                'key' => $m->key,
                'label' => $m->label,
                'kind' => $m->kind,
                'format' => $m->format,
                'hidden' => $m->hidden,
                'compare' => $m->compare,
                'compareMode' => $m->compareMode,
                'drillable' => $m->isAggregated(),
            ], $definition->measures),
            'valueColumns' => $valueColumns,
            'rows' => $rowTree,
            'columns' => $columnTree,
            'cells' => $cells,
            'options' => [
                'rowTotals' => $definition->rowTotals,
                'columnTotals' => $definition->columnTotals,
                'subtotals' => $definition->subtotals,
            ],
            'view' => is_array($definition->raw['options']['view'] ?? null) ? $definition->raw['options']['view'] : null,
            'truncated' => $truncated,
            'queryCount' => $this->queryCount,
            'durationMs' => (int) round((microtime(true) - $start) * 1000),
            'generatedAt' => gmdate('Y-m-d H:i:s'),
            'fromCache' => false,
        ];

        $this->cache->set($cacheKey, $result);

        return $result;
    }

    /**
     * Grouping sets to fetch: [row depth, column depth].
     *
     * @return array<int, array{int, int}>
     */
    private function determineSets(Definition $definition, int $R, int $C): array
    {
        $rowLevels = [$R];
        $columnLevels = [$C];

        if ($definition->columnTotals) {
            $rowLevels[] = 0;
        }

        if ($definition->rowTotals) {
            $columnLevels[] = 0;
        }

        if ($definition->subtotals) {
            $rowLevels = array_merge($rowLevels, range(1, max(1, $R - 1)));
            $columnLevels = array_merge($columnLevels, range(1, max(1, $C - 1)));
        }

        $rowLevels = array_unique(array_filter($rowLevels, fn ($l) => $l <= $R));
        $columnLevels = array_unique(array_filter($columnLevels, fn ($l) => $l <= $C));

        $sets = [];

        foreach ($rowLevels as $i) {
            foreach ($columnLevels as $j) {
                $sets["$i:$j"] = [$i, $j];
            }
        }

        // Sorting / Top N by measure needs the node's value at the opposite axis total.
        foreach ($definition->rows as $index => $dimension) {
            if ($dimension->sortBy === 'measure' || $dimension->limitType) {
                $sets[($index + 1) . ':0'] = [$index + 1, 0];
            }
        }

        foreach ($definition->columns as $index => $dimension) {
            if ($dimension->sortBy === 'measure' || $dimension->limitType) {
                $sets['0:' . ($index + 1)] = [0, $index + 1];
            }
        }

        // The grand total is needed for KPIs and percentages.
        $sets['0:0'] = [0, 0];

        return array_values($sets);
    }

    /**
     * SUM, COUNT, MIN and MAX of a group can be computed from the values of its sub-groups.
     * AVG, COUNT DISTINCT and aggregate formulas (ratios…) can't: they are always computed by the database.
     */
    private function isDecomposable(Definition $definition): bool
    {
        foreach ($definition->getAggregatedMeasures() as $measure) {
            if (
                $measure->kind !== Measure::KIND_NATIVE ||
                !in_array($measure->aggregation, ['SUM', 'COUNT', 'MIN', 'MAX'], true)
            ) {
                return false;
            }
        }

        return true;
    }

    private function rollUp(Definition $definition, array &$values, int $R, int $C, int $i, int $j): void
    {
        $measures = $definition->getAggregatedMeasures();
        $result = [];

        foreach ($values as $rowId => $columnsData) {
            $rowPath = json_decode($rowId, true);

            if (count($rowPath) !== $R) {
                continue;
            }

            $targetRowId = self::id(array_slice($rowPath, 0, $i));

            foreach ($columnsData as $columnId => $cell) {
                $columnPath = json_decode($columnId, true);

                if (count($columnPath) !== $C) {
                    continue;
                }

                $targetColumnId = self::id(array_slice($columnPath, 0, $j));
                $target = $result[$targetRowId][$targetColumnId] ?? [];

                foreach ($measures as $measure) {
                    $key = $measure->key;
                    $value = $cell[$key] ?? null;
                    $current = $target[$key] ?? null;

                    if (!array_key_exists($key, $target)) {
                        $target[$key] = $measure->aggregation === 'COUNT' ? 0 : null;
                        $current = $target[$key];
                    }

                    if ($value === null) {
                        continue;
                    }

                    $target[$key] = match ($measure->aggregation) {
                        'MIN' => $current === null ? $value : min($current, $value),
                        'MAX' => $current === null ? $value : max($current, $value),
                        default => ($current ?? 0) + $value,
                    };
                }

                $result[$targetRowId][$targetColumnId] = $target;
            }
        }

        foreach ($result as $rowId => $columnsData) {
            foreach ($columnsData as $columnId => $cell) {
                $values[$rowId][$columnId] = array_map(
                    fn ($v) => is_float($v) ? round($v, 6) : $v,
                    $cell
                );
            }
        }

        // An empty data set still has a grand total.
        if ($i === 0 && $j === 0 && !isset($values['[]']['[]'])) {
            foreach ($measures as $measure) {
                $values['[]']['[]'][$measure->key] = $measure->aggregation === 'COUNT' ? 0 : null;
            }
        }
    }

    /**
     * @return bool Whether the result was truncated.
     */
    private function fetchSet(CompiledQuery $compiled, int $i, int $j, array &$values): bool
    {
        /** @var CompiledDimension[] $dimensions */
        $dimensions = array_merge(array_slice($compiled->rows, 0, $i), array_slice($compiled->columns, 0, $j));

        $select = [];
        $group = [];

        foreach ($dimensions as $index => $dimension) {
            $select[] = Selection::create($dimension->expression, 'd' . $index);
            $group[] = $dimension->expression;
        }

        $measureKeys = array_keys($compiled->measureExpressions);

        foreach ($measureKeys as $index => $key) {
            $select[] = Selection::create($compiled->measureExpressions[$key], 'm' . $index);
        }

        $builder = $this->entityManager
            ->getQueryBuilder()
            ->select()
            ->clone($compiled->baseQuery)
            ->select($select)
            ->order([]);

        $maxCells = $this->limits->maxCells();

        if ($group) {
            $builder->group($group)->limit(0, $maxCells + 1);
        }

        $rows = $this->entityManager
            ->getQueryExecutor()
            ->execute($builder->build())
            ->fetchAll(PDO::FETCH_ASSOC);

        $this->queryCount++;

        $truncated = count($rows) > $maxCells;

        if ($truncated) {
            array_pop($rows);
        }

        foreach ($rows as $row) {
            $rowPath = [];
            $columnPath = [];

            for ($a = 0; $a < $i; $a++) {
                $rowPath[] = self::key($row['d' . $a]);
            }

            for ($b = 0; $b < $j; $b++) {
                $columnPath[] = self::key($row['d' . ($i + $b)]);
            }

            $cell = [];

            foreach ($measureKeys as $index => $key) {
                $cell[$key] = self::number($row['m' . $index]);
            }

            $values[self::id($rowPath)][self::id($columnPath)] = $cell;
        }

        return $truncated;
    }

    private function computeDisplayMeasures(Definition $definition, array &$values): void
    {
        $displayMeasures = array_filter($definition->measures, fn (Measure $m) => !$m->isAggregated());

        if (!$displayMeasures) {
            return;
        }

        foreach ($values as $rowId => $columnsData) {
            foreach ($columnsData as $columnId => $cell) {
                foreach ($displayMeasures as $measure) {
                    $cell[$measure->key] = $this->displayEvaluator->evaluate((string) $measure->formula, $cell);
                }

                $values[$rowId][$columnId] = $cell;
            }
        }
    }

    /**
     * Period-over-period comparison along the last date dimension of the columns (or else of the rows):
     * `previous` compares with the previous period (MoM, QoQ…), `previousYear` with the same period one
     * year earlier (YoY).
     */
    private function computeComparisons(CompiledQuery $compiled, array &$values, array $rowPaths, array $columnPaths): void
    {
        $measures = array_filter($compiled->definition->measures, fn (Measure $m) => $m->compare !== null);

        if (!$measures) {
            return;
        }

        $axis = null;
        $index = null;

        foreach (['columns', 'rows'] as $candidate) {
            foreach (array_reverse($compiled->$candidate, true) as $i => $dimension) {
                if ($dimension->granularity !== null) {
                    $axis = $candidate;
                    $index = $i;

                    break 2;
                }
            }
        }

        if ($axis === null) {
            return;
        }

        $dimension = $compiled->{$axis}[$index];

        // Ordered sibling keys at the date level, per parent prefix.
        $siblings = [];

        foreach ($axis === 'columns' ? $columnPaths : $rowPaths as $path) {
            $siblings[self::id(array_slice($path, 0, $index))][$path[$index]] = true;
        }

        foreach ($siblings as $prefix => $keys) {
            $list = array_map('strval', array_keys($keys));
            usort($list, fn ($a, $b) => $this->treeBuilder->compareNatural($dimension, $a, $b, []));
            $siblings[$prefix] = $list;
        }

        $original = $values;

        foreach ($original as $rowId => $columnsData) {
            foreach ($columnsData as $columnId => $cell) {
                $path = json_decode($axis === 'columns' ? $columnId : $rowId, true);

                if (count($path) <= $index) {
                    continue;
                }

                foreach ($measures as $measure) {
                    $previousKey = $this->previousKey(
                        $measure->compare,
                        $dimension->granularity,
                        (string) $path[$index],
                        $siblings[self::id(array_slice($path, 0, $index))] ?? []
                    );

                    $comparison = null;

                    if ($previousKey !== null) {
                        $previousPath = $path;
                        $previousPath[$index] = $previousKey;
                        $previousId = self::id($previousPath);

                        $previous = $axis === 'columns' ?
                            ($original[$rowId][$previousId][$measure->key] ?? null) :
                            ($original[$previousId][$columnId][$measure->key] ?? null);

                        $current = $cell[$measure->key] ?? null;

                        if ($current !== null && $previous !== null) {
                            if ($measure->compareMode === 'difference') {
                                $comparison = $current - $previous;
                            } else if ($previous != 0) {
                                $comparison = round(($current - $previous) / abs($previous) * 100, 4);
                            }
                        }
                    }

                    $values[$rowId][$columnId][$measure->key . '__cmp'] = $comparison;
                }
            }
        }
    }

    private function previousKey(string $compare, string $granularity, string $key, array $siblings): ?string
    {
        if ($key === '') {
            return null;
        }

        if ($compare === 'previous') {
            $position = array_search($key, $siblings, true);

            return $position ? $siblings[$position - 1] : null;
        }

        if (!preg_match('/^(\d{4})(.*)$/', $key, $m)) {
            return null;
        }

        // Cyclic granularities (month number, day of week…) have no year.
        if (!in_array($granularity, ['year', 'quarter', 'yearMonth', 'week', 'day'], true)) {
            return null;
        }

        return ((int) $m[1] - 1) . $m[2];
    }

    /**
     * Keeps only cells belonging to visible header nodes, as arrays aligned with valueColumns.
     */
    private function buildCells(array $values, array $valueColumns, array $rowTree, array $columnTree): array
    {
        $rowIds = array_flip($this->collectIds($rowTree, []));
        $columnIds = array_flip($this->collectIds($columnTree, []));

        $rowIds[self::TOTAL] = true;
        $columnIds[self::TOTAL] = true;

        $cells = [];

        foreach ($values as $rowId => $columnsData) {
            if (!isset($rowIds[$rowId])) {
                continue;
            }

            foreach ($columnsData as $columnId => $cell) {
                if (!isset($columnIds[$columnId])) {
                    continue;
                }

                $cells[$rowId][$columnId] = array_map(
                    fn ($column) => $cell[$column['measure'] . ($column['variant'] === 'compare' ? '__cmp' : '')] ?? null,
                    $valueColumns
                );
            }
        }

        return $cells;
    }

    /**
     * @return string[]
     */
    private function collectIds(array $nodes, array $prefix): array
    {
        $ids = [];

        foreach ($nodes as $node) {
            $path = array_merge($prefix, [$node['k']]);
            $ids[] = self::id($path);

            if (!empty($node['c'])) {
                $ids = array_merge($ids, $this->collectIds($node['c'], $path));
            }
        }

        return $ids;
    }

    /**
     * @param CompiledDimension[] $dimensions
     * @return array<int, array<string, string>>
     */
    private function resolveLabels(array $dimensions, array $paths): array
    {
        $labels = [];

        foreach ($dimensions as $index => $dimension) {
            $keys = array_unique(array_map(fn ($path) => (string) $path[$index], $paths));
            $labels[$index] = $this->labelResolver->resolve($dimension, array_values($keys));
        }

        return $labels;
    }

    private function describeDimension(CompiledDimension $dimension): array
    {
        return [
            'id' => $dimension->dimension->id,
            'label' => $dimension->label,
            'type' => $dimension->dimension->type,
            'path' => $dimension->dimension->path,
            'granularity' => $dimension->granularity,
            'fieldType' => $dimension->field?->fieldType,
        ];
    }

    public static function id(array $path): string
    {
        return json_encode(array_map('strval', array_values($path)), JSON_UNESCAPED_UNICODE) ?: '[]';
    }

    public static function key(mixed $value): string
    {
        if ($value === null) {
            return '';
        }

        if (is_bool($value)) {
            return $value ? '1' : '0';
        }

        return (string) $value;
    }

    public static function number(mixed $value): int|float|null
    {
        if ($value === null || !is_numeric($value)) {
            return null;
        }

        $number = $value + 0;

        return is_float($number) ? round($number, 6) : $number;
    }
}
