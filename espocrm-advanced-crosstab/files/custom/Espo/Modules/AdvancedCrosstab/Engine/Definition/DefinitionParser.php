<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Definition;

use Espo\Core\Utils\Metadata;
use Espo\Modules\AdvancedCrosstab\Engine\Filter\FilterOperators;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use stdClass;

/**
 * Validates a raw (user supplied) definition and builds a Definition.
 * Only structure is validated here; fields, formulas and access are validated by the compilers.
 */
class DefinitionParser
{
    private const PATH_REGEX = '/^[a-zA-Z][a-zA-Z0-9]*(\.[a-zA-Z][a-zA-Z0-9]*)*$/';
    private const KEY_REGEX = '/^[a-zA-Z_][a-zA-Z0-9_]{0,49}$/';
    private const ID_REGEX = '/^[a-zA-Z0-9_\-]{1,40}$/';
    private const RESERVED_KEYS = ['id', 'null', 'true', 'false'];

    private int $filterItemCount = 0;

    public function __construct(
        private Metadata $metadata,
        private Limits $limits,
    ) {}

    /**
     * @throws DefinitionError
     */
    public function parse(stdClass|array $raw): Definition
    {
        $data = self::toArray($raw);
        $this->filterItemCount = 0;

        $entityType = $data['entityType'] ?? null;

        if (
            !is_string($entityType) ||
            !preg_match('/^[A-Z][a-zA-Z0-9]*$/', $entityType) ||
            !$this->metadata->get(['scopes', $entityType, 'entity']) ||
            $this->metadata->get(['scopes', $entityType, 'disabled'])
        ) {
            throw DefinitionError::create("Invalid data source.");
        }

        $rows = $this->parseDimensions($data['rows'] ?? [], 'r', $this->limits->maxRowDimensions());
        $columns = $this->parseDimensions($data['columns'] ?? [], 'c', $this->limits->maxColumnDimensions());

        $ids = array_map(fn (Dimension $d) => $d->id, array_merge($rows, $columns));

        if (count($ids) !== count(array_unique($ids))) {
            throw DefinitionError::create("Duplicate dimension ID.");
        }

        $measures = $this->parseMeasures($data['measures'] ?? []);

        $this->validateMeasureReferences($rows, $columns, $measures);

        $filter = isset($data['filter']) && $data['filter'] !== null ?
            $this->parseFilterNode($data['filter'], 0) :
            null;

        $primaryFilter = $data['primaryFilter'] ?? null;

        if ($primaryFilter !== null && $primaryFilter !== '') {
            if (!is_string($primaryFilter) || !preg_match('/^[a-zA-Z][a-zA-Z0-9]*$/', $primaryFilter)) {
                throw DefinitionError::create("Invalid primary filter.");
            }
        } else {
            $primaryFilter = null;
        }

        $listWhere = $data['listWhere'] ?? null;

        if ($listWhere !== null) {
            if (!is_array($listWhere) || !array_is_list($listWhere) || strlen((string) json_encode($listWhere)) > 50000) {
                throw DefinitionError::create("Invalid list filters.");
            }

            $listWhere = $listWhere ?: null;
        }

        $options = is_array($data['options'] ?? null) ? $data['options'] : [];

        return new Definition(
            entityType: $entityType,
            rows: $rows,
            columns: $columns,
            measures: $measures,
            filter: $filter,
            primaryFilter: $primaryFilter,
            rowTotals: ($options['rowTotals'] ?? true) !== false,
            columnTotals: ($options['columnTotals'] ?? true) !== false,
            subtotals: ($options['subtotals'] ?? true) !== false,
            raw: $data,
            listWhere: $listWhere,
        );
    }

    /**
     * @return Dimension[]
     */
    private function parseDimensions(mixed $list, string $prefix, int $max): array
    {
        if (!is_array($list) || !array_is_list($list)) {
            throw DefinitionError::create("Invalid dimension list.");
        }

        if (count($list) > $max) {
            throw DefinitionError::create("Too many dimensions. The maximum is {$max}.");
        }

        $result = [];

        foreach ($list as $i => $item) {
            if (!is_array($item)) {
                throw DefinitionError::create("Invalid dimension.");
            }

            $id = $item['id'] ?? ($prefix . $i);

            if (!is_string($id) || !preg_match(self::ID_REGEX, $id)) {
                throw DefinitionError::create("Invalid dimension ID.");
            }

            $type = $item['type'] ?? Dimension::TYPE_FIELD;

            if (!in_array($type, [Dimension::TYPE_FIELD, Dimension::TYPE_FORMULA], true)) {
                throw DefinitionError::create("Invalid dimension type.");
            }

            $path = null;
            $formula = null;

            if ($type === Dimension::TYPE_FIELD) {
                $path = $this->parsePath($item['path'] ?? null);
            } else {
                $formula = $this->parseFormulaString($item['formula'] ?? null, true);
            }

            $granularity = $item['granularity'] ?? null;

            if ($granularity !== null && !in_array($granularity, Dimension::GRANULARITY_LIST, true)) {
                throw DefinitionError::create("Invalid date granularity.");
            }

            $sort = is_array($item['sort'] ?? null) ? $item['sort'] : [];
            $sortBy = $sort['by'] ?? 'natural';

            if (!in_array($sortBy, ['natural', 'label', 'measure'], true)) {
                throw DefinitionError::create("Invalid sort.");
            }

            $sortDirection = ($sort['direction'] ?? 'asc') === 'desc' ? 'desc' : 'asc';
            $sortMeasure = $sortBy === 'measure' ? $this->parseKey($sort['measure'] ?? null) : null;

            $limit = is_array($item['limit'] ?? null) ? $item['limit'] : [];
            $limitType = $limit['type'] ?? null;

            if ($limitType !== null && !in_array($limitType, ['top', 'bottom'], true)) {
                throw DefinitionError::create("Invalid Top/Bottom N.");
            }

            $limitCount = (int) ($limit['count'] ?? 10);

            if ($limitType && ($limitCount < 1 || $limitCount > 10000)) {
                throw DefinitionError::create("Invalid Top/Bottom N count.");
            }

            $limitMeasure = $limitType ? $this->parseKey($limit['measure'] ?? null) : null;

            $result[] = new Dimension(
                id: $id,
                type: $type,
                path: $path,
                formula: $formula,
                granularity: $granularity,
                label: $this->parseLabel($item['label'] ?? null),
                sortBy: $sortBy,
                sortMeasure: $sortMeasure,
                sortDirection: $sortDirection,
                limitType: $limitType,
                limitCount: $limitCount,
                limitMeasure: $limitMeasure,
            );
        }

        return $result;
    }

    /**
     * @return Measure[]
     */
    private function parseMeasures(mixed $list): array
    {
        if (!is_array($list) || !array_is_list($list) || $list === []) {
            throw DefinitionError::create("At least one measure is required.");
        }

        if (count($list) > $this->limits->maxMeasures()) {
            throw DefinitionError::create("Too many measures.");
        }

        $result = [];
        $keys = [];

        foreach ($list as $item) {
            if (!is_array($item)) {
                throw DefinitionError::create("Invalid measure.");
            }

            $key = $this->parseKey($item['key'] ?? null);

            if (in_array(strtolower($key), self::RESERVED_KEYS, true) || in_array($key, $keys, true)) {
                throw DefinitionError::create("Invalid or duplicate measure key: {$key}.");
            }

            $keys[] = $key;

            $kind = $item['kind'] ?? Measure::KIND_NATIVE;

            if (!in_array($kind, [Measure::KIND_NATIVE, Measure::KIND_AGGREGATE, Measure::KIND_DISPLAY], true)) {
                throw DefinitionError::create("Invalid measure type.");
            }

            $aggregation = null;
            $expression = null;
            $formula = null;

            if ($kind === Measure::KIND_NATIVE) {
                $aggregation = strtoupper((string) ($item['aggregation'] ?? 'COUNT'));

                if (!in_array($aggregation, Measure::AGGREGATION_LIST, true)) {
                    throw DefinitionError::create("Invalid aggregation.");
                }

                $expression = $this->parseFormulaString($item['expression'] ?? null, $aggregation !== 'COUNT');
            } else {
                $formula = $this->parseFormulaString($item['formula'] ?? null, true);
            }

            $condition = $kind === Measure::KIND_DISPLAY ?
                null :
                $this->parseFormulaString($item['condition'] ?? null, false);

            $compare = $item['compare'] ?? null;

            if ($compare !== null && !in_array($compare, Measure::COMPARE_LIST, true)) {
                throw DefinitionError::create("Invalid comparison.");
            }

            $result[] = new Measure(
                key: $key,
                label: $this->parseLabel($item['label'] ?? null) ?? $key,
                kind: $kind,
                aggregation: $aggregation,
                expression: $expression,
                condition: $condition,
                formula: $formula,
                format: $this->parseFormat($item['format'] ?? []),
                hidden: !empty($item['hidden']),
                compare: $compare,
                compareMode: ($item['compareMode'] ?? 'percent') === 'difference' ? 'difference' : 'percent',
            );
        }

        if (!array_filter($result, fn (Measure $m) => !$m->hidden)) {
            throw DefinitionError::create("At least one measure must be visible.");
        }

        return $result;
    }

    /**
     * @param Dimension[] $rows
     * @param Dimension[] $columns
     * @param Measure[] $measures
     */
    private function validateMeasureReferences(array $rows, array $columns, array $measures): void
    {
        $keys = array_map(fn (Measure $m) => $m->key, $measures);

        foreach (array_merge($rows, $columns) as $dimension) {
            foreach ([$dimension->sortMeasure, $dimension->limitMeasure] as $key) {
                if ($key !== null && !in_array($key, $keys, true)) {
                    throw DefinitionError::create("Unknown measure: {$key}.");
                }
            }
        }
    }

    private function parseFormat(mixed $raw): array
    {
        $raw = is_array($raw) ? $raw : [];
        $type = $raw['type'] ?? 'number';

        if (!in_array($type, Measure::FORMAT_LIST, true)) {
            $type = 'number';
        }

        $decimals = $raw['decimals'] ?? null;
        $decimals = $decimals === null || $decimals === '' ? null : max(0, min(10, (int) $decimals));

        $currency = $raw['currency'] ?? null;

        if ($currency !== null && (!is_string($currency) || !preg_match('/^[A-Z]{3}$/', $currency))) {
            $currency = null;
        }

        return [
            'type' => $type,
            'decimals' => $decimals,
            'currency' => $currency,
            'prefix' => mb_substr((string) ($raw['prefix'] ?? ''), 0, 20),
            'suffix' => mb_substr((string) ($raw['suffix'] ?? ''), 0, 20),
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private function parseFilterNode(mixed $node, int $depth): array
    {
        if (!is_array($node)) {
            throw DefinitionError::create("Invalid filter.");
        }

        if (++$this->filterItemCount > $this->limits->maxFilterItems()) {
            throw DefinitionError::create("Too many filter conditions.");
        }

        if ($depth > 6) {
            throw DefinitionError::create("Filter nesting is too deep.");
        }

        $type = $node['type'] ?? null;

        if ($type === 'and' || $type === 'or' || $type === 'not') {
            $items = $node['items'] ?? [];

            if (!is_array($items) || !array_is_list($items)) {
                throw DefinitionError::create("Invalid filter group.");
            }

            return [
                'type' => $type,
                'items' => array_map(fn ($item) => $this->parseFilterNode($item, $depth + 1), $items),
            ];
        }

        if ($type === 'formula') {
            return [
                'type' => 'formula',
                'formula' => $this->parseFormulaString($node['formula'] ?? null, true),
            ];
        }

        if ($type !== 'condition') {
            throw DefinitionError::create("Invalid filter type.");
        }

        $operator = $node['operator'] ?? null;

        if (!is_string($operator) || !FilterOperators::isValid($operator)) {
            throw DefinitionError::create("Invalid filter operator.");
        }

        return [
            'type' => 'condition',
            'path' => $this->parsePath($node['path'] ?? null),
            'operator' => $operator,
            'value' => $this->parseFilterValue($node['value'] ?? null),
        ];
    }

    private function parseFilterValue(mixed $value): mixed
    {
        if ($value === null || is_scalar($value)) {
            return is_string($value) ? mb_substr($value, 0, 1000) : $value;
        }

        if (is_array($value) && array_is_list($value) && count($value) <= 1000) {
            foreach ($value as $item) {
                if (!is_scalar($item) && $item !== null) {
                    throw DefinitionError::create("Invalid filter value.");
                }
            }

            return $value;
        }

        throw DefinitionError::create("Invalid filter value.");
    }

    private function parsePath(mixed $path): string
    {
        if (!is_string($path) || !preg_match(self::PATH_REGEX, $path)) {
            throw DefinitionError::create("Invalid field: " . (is_string($path) ? $path : ''));
        }

        if (substr_count($path, '.') > $this->limits->maxPathDepth()) {
            throw DefinitionError::create("Relationship path is too deep: {$path}");
        }

        return $path;
    }

    private function parseFormulaString(mixed $value, bool $required): ?string
    {
        if ($value === null || (is_string($value) && trim($value) === '')) {
            if ($required) {
                throw DefinitionError::create("Formula is required.");
            }

            return null;
        }

        if (!is_string($value) || strlen($value) > $this->limits->maxFormulaLength()) {
            throw DefinitionError::create("Invalid formula.");
        }

        return trim($value);
    }

    private function parseKey(mixed $key): string
    {
        if (!is_string($key) || !preg_match(self::KEY_REGEX, $key)) {
            throw DefinitionError::create("Invalid measure key: " . (is_string($key) ? $key : ''));
        }

        return $key;
    }

    private function parseLabel(mixed $label): ?string
    {
        if ($label === null || $label === '') {
            return null;
        }

        return mb_substr((string) $label, 0, 150);
    }

    private static function toArray(stdClass|array $raw): array
    {
        return json_decode(json_encode($raw), true) ?? [];
    }
}
