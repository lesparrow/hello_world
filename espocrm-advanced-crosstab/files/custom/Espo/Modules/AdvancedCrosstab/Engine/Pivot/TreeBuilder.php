<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Pivot;

use Collator;
use Espo\Core\Utils\Metadata;
use Espo\Modules\AdvancedCrosstab\Engine\Query\CompiledDimension;

/**
 * Builds the hierarchical row/column headers: grouping, natural ordering, sorting by label or measure,
 * Top/Bottom N and ranks, independently at every level.
 */
class TreeBuilder
{
    private ?Collator $collator = null;

    public function __construct(private Metadata $metadata) {}

    public function setLocale(string $locale): void
    {
        $this->collator = class_exists(Collator::class) ? new Collator($locale) : null;
    }

    /**
     * @param string[][] $paths Full-depth key paths.
     * @param CompiledDimension[] $dimensions
     * @param array<int, array<string, string>> $labels Labels per dimension index.
     * @param callable(string[] $path, string $measure): (int|float|null) $valueGetter Value of a node at the
     *     opposite axis total.
     * @return array<int, array<string, mixed>>
     */
    public function build(array $paths, array $dimensions, array $labels, callable $valueGetter): array
    {
        return $this->buildLevel($paths, [], 0, $dimensions, $labels, $valueGetter);
    }

    /**
     * @return array<int, array<string, mixed>>
     */
    private function buildLevel(
        array $paths,
        array $prefix,
        int $level,
        array $dimensions,
        array $labels,
        callable $valueGetter
    ): array {

        if ($level >= count($dimensions)) {
            return [];
        }

        $dimension = $dimensions[$level];
        $config = $dimension->dimension;

        $groups = [];

        foreach ($paths as $path) {
            $groups[$path[$level]][] = $path;
        }

        $keys = array_map('strval', array_keys($groups));

        usort($keys, fn ($a, $b) => $this->compareNatural($dimension, $a, $b, $labels[$level] ?? []));

        $value = fn (string $key, ?string $measure) =>
            $measure === null ? null : $valueGetter(array_merge($prefix, [$key]), $measure);

        $ranks = [];

        if ($config->limitType) {
            $direction = $config->limitType === 'top' ? -1 : 1;

            usort($keys, fn ($a, $b) =>
                $direction * self::compareNumbers($value($a, $config->limitMeasure), $value($b, $config->limitMeasure))
            );

            $keys = array_slice($keys, 0, $config->limitCount);

            foreach ($keys as $i => $key) {
                $ranks[$key] = $i + 1;
            }
        }

        if ($config->sortBy === 'label') {
            usort($keys, fn ($a, $b) => $this->compareText($labels[$level][$a] ?? $a, $labels[$level][$b] ?? $b));
        } else if ($config->sortBy === 'measure') {
            usort($keys, fn ($a, $b) =>
                -1 * self::compareNumbers($value($a, $config->sortMeasure), $value($b, $config->sortMeasure))
            );

            if (!$config->limitType) {
                foreach ($keys as $i => $key) {
                    $ranks[$key] = $i + 1;
                }
            }
        } else if ($config->limitType) {
            usort($keys, fn ($a, $b) => $this->compareNatural($dimension, $a, $b, $labels[$level] ?? []));
        }

        // Descending natural/label order, or ascending measure order.
        if (
            ($config->sortBy !== 'measure' && $config->sortDirection === 'desc') ||
            ($config->sortBy === 'measure' && $config->sortDirection === 'asc')
        ) {
            $keys = array_reverse($keys);
        }

        $nodes = [];

        foreach ($keys as $key) {
            $node = [
                'k' => $key,
                'l' => $labels[$level][$key] ?? $key,
            ];

            if (isset($ranks[$key])) {
                $node['r'] = $ranks[$key];
            }

            $children = $this->buildLevel(
                $groups[$key],
                array_merge($prefix, [$key]),
                $level + 1,
                $dimensions,
                $labels,
                $valueGetter
            );

            if ($children !== []) {
                $node['c'] = $children;
            }

            $nodes[] = $node;
        }

        return $nodes;
    }

    /**
     * Chronological for dates, option order for enums, numeric for numbers, alphabetical otherwise.
     * Empty values go last.
     */
    public function compareNatural(CompiledDimension $dimension, string $a, string $b, array $labels): int
    {
        if ($a === $b) {
            return 0;
        }

        if ($a === '') {
            return 1;
        }

        if ($b === '') {
            return -1;
        }

        if (in_array($dimension->granularity, ['week', 'quarter'], true)) {
            return self::compareParts($a, $b);
        }

        if ($dimension->granularity !== null) {
            return is_numeric($a) && is_numeric($b) ? $a <=> $b : strcmp($a, $b);
        }

        $field = $dimension->field;

        if ($field && $field->fieldType === 'enum') {
            $options = $this->metadata->get(['entityDefs', $field->entityType, 'fields', $field->field, 'options']) ?? [];
            $ia = array_search($a, $options, true);
            $ib = array_search($b, $options, true);

            if ($ia !== false && $ib !== false) {
                return $ia <=> $ib;
            }
        }

        if (is_numeric($a) && is_numeric($b)) {
            return $a + 0 <=> $b + 0;
        }

        return $this->compareText($labels[$a] ?? $a, $labels[$b] ?? $b);
    }

    private function compareText(string $a, string $b): int
    {
        if ($this->collator) {
            return (int) $this->collator->compare($a, $b);
        }

        return strnatcasecmp($a, $b);
    }

    private static function compareParts(string $a, string $b): int
    {
        $pa = array_map('intval', preg_split('/[_\/]/', $a) ?: []);
        $pb = array_map('intval', preg_split('/[_\/]/', $b) ?: []);

        return $pa <=> $pb;
    }

    /**
     * NULLs sort as the lowest values.
     */
    public static function compareNumbers(int|float|null $a, int|float|null $b): int
    {
        if ($a === $b) {
            return 0;
        }

        if ($a === null) {
            return -1;
        }

        if ($b === null) {
            return 1;
        }

        return $a <=> $b;
    }
}
