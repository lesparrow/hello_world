<?php

namespace Espo\Modules\Crosstab\Tools\Crosstab;

use Espo\Core\Acl;
use Espo\Core\Acl\Table;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Select\SearchParams;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Core\Utils\Metadata;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\SelectBuilder as QueryBuilder;
use PDO;

/**
 * Builds a crosstab with a single GROUP BY query executed by the database,
 * instead of loading every record into the browser.
 */
class Service
{
    /** Max number of (row, column) cells returned. */
    private const MAX_CELLS = 20000;

    private const GROUPABLE_TYPES = [
        'enum', 'varchar', 'bool', 'link', 'int',
        'date', 'datetime', 'datetimeOptional',
    ];

    private const DATE_TYPES = ['date', 'datetime', 'datetimeOptional'];

    private const NUMERIC_TYPES = ['int', 'float', 'currency'];

    private const GRANULARITY_FUNCTIONS = [
        'year' => 'YEAR',
        'quarter' => 'QUARTER',
        'month' => 'MONTH',
        'day' => 'DATE',
    ];

    public function __construct(
        private Acl $acl,
        private Metadata $metadata,
        private EntityManager $entityManager,
        private SelectBuilderFactory $selectBuilderFactory
    ) {}

    public function run(Params $params): array
    {
        $entityType = $params->entityType;

        if (
            !$this->metadata->get(['scopes', $entityType, 'entity']) ||
            !$this->acl->checkScope($entityType, Table::ACTION_READ)
        ) {
            throw new Forbidden("No access to {$entityType}.");
        }

        $forbidden = $this->acl->getScopeForbiddenFieldList($entityType);

        $row = $this->groupExpression($entityType, $params->rowField, $params->rowGranularity, $forbidden);
        $column = $params->columnField ?
            $this->groupExpression($entityType, $params->columnField, $params->columnGranularity, $forbidden) :
            null;

        $value = $this->valueExpression($entityType, $params, $forbidden);

        $groups = array_filter([$row['expression'], $column['expression'] ?? null]);

        $rawCells = $this->fetch($params, $groups, $value, self::MAX_CELLS + 1);
        $truncated = count($rawCells) > self::MAX_CELLS;

        if ($truncated) {
            array_pop($rawCells);
        }

        $cells = [];

        foreach ($rawCells as $item) {
            $cells[] = [
                self::key($item['g0']),
                $column ? self::key($item['g1']) : '',
                self::number($item['v']),
            ];
        }

        [$rowTotals, $columnTotals, $grandTotal] = $this->totals($params, $row, $column, $value, $cells);

        return [
            'cells' => $cells,
            'rowTotals' => (object) $rowTotals,
            'columnTotals' => (object) $columnTotals,
            'grandTotal' => $grandTotal,
            'rowLabels' => (object) $this->linkLabels($row, array_keys($rowTotals)),
            'columnLabels' => (object) ($column ? $this->linkLabels($column, array_keys($columnTotals)) : []),
            'truncated' => $truncated,
        ];
    }

    /**
     * SUM and COUNT totals are additive, so they are computed from the cells.
     * AVG, MIN and MAX are not, so the database computes them (3 cheap queries).
     */
    private function totals(Params $params, array $row, ?array $column, string $value, array $cells): array
    {
        if (in_array($params->aggregate, ['COUNT', 'SUM'], true)) {
            $rowTotals = [];
            $columnTotals = [];
            $grandTotal = 0;

            foreach ($cells as [$r, $c, $v]) {
                $rowTotals[$r] = ($rowTotals[$r] ?? 0) + $v;
                $columnTotals[$c] = ($columnTotals[$c] ?? 0) + $v;
                $grandTotal += $v;
            }

            return [$rowTotals, $column ? $columnTotals : [], $grandTotal];
        }

        $rowTotals = [];

        foreach ($this->fetch($params, [$row['expression']], $value) as $item) {
            $rowTotals[self::key($item['g0'])] = self::number($item['v']);
        }

        $columnTotals = [];

        if ($column) {
            foreach ($this->fetch($params, [$column['expression']], $value) as $item) {
                $columnTotals[self::key($item['g0'])] = self::number($item['v']);
            }
        }

        $grand = $this->fetch($params, [], $value);

        return [$rowTotals, $columnTotals, self::number($grand[0]['v'] ?? null)];
    }

    /**
     * @param string[] $groups
     * @return array<int, array<string, mixed>>
     */
    private function fetch(Params $params, array $groups, string $value, ?int $limit = null): array
    {
        $searchParams = SearchParams::fromRaw([
            'where' => $params->where,
            'primaryFilter' => $params->primaryFilter,
        ]);

        $builder = $this->selectBuilderFactory
            ->create()
            ->from($params->entityType)
            ->withStrictAccessControl()
            ->withSearchParams($searchParams)
            ->buildQueryBuilder();

        $select = [[$value, 'v']];

        foreach ($groups as $i => $group) {
            $select[] = [$group, 'g' . $i];
        }

        $builder->select($select);

        if ($groups) {
            $builder->group($groups);
        }

        if ($limit) {
            $builder->limit(0, $limit);
        }

        return $this->execute($builder);
    }

    private function execute(QueryBuilder $builder): array
    {
        return $this->entityManager
            ->getQueryExecutor()
            ->execute($builder->build())
            ->fetchAll(PDO::FETCH_ASSOC);
    }

    /**
     * @return array{expression: string, foreignEntityType: ?string}
     */
    private function groupExpression(string $entityType, string $field, ?string $granularity, array $forbidden): array
    {
        $type = $this->fieldType($entityType, $field, $forbidden);

        if (!in_array($type, self::GROUPABLE_TYPES, true)) {
            throw new BadRequest("Field '{$field}' can't be used for grouping.");
        }

        if ($type === 'link') {
            return [
                'expression' => $field . 'Id',
                'foreignEntityType' => $this->metadata->get(['entityDefs', $entityType, 'links', $field, 'entity']),
            ];
        }

        if (in_array($type, self::DATE_TYPES, true)) {
            $function = self::GRANULARITY_FUNCTIONS[$granularity ?? 'month'];

            return ['expression' => "{$function}:({$field})", 'foreignEntityType' => null];
        }

        return ['expression' => $field, 'foreignEntityType' => null];
    }

    private function valueExpression(string $entityType, Params $params, array $forbidden): string
    {
        if ($params->aggregate === 'COUNT') {
            return 'COUNT:(id)';
        }

        $field = (string) $params->valueField;
        $type = $this->fieldType($entityType, $field, $forbidden);

        if (!in_array($type, self::NUMERIC_TYPES, true)) {
            throw new BadRequest("Field '{$field}' is not numeric.");
        }

        return "{$params->aggregate}:({$field})";
    }

    private function fieldType(string $entityType, string $field, array $forbidden): string
    {
        $defs = $this->metadata->get(['entityDefs', $entityType, 'fields', $field]);

        if (
            !$defs ||
            in_array($field, $forbidden, true) ||
            !empty($defs['disabled']) ||
            !empty($defs['notStorable'])
        ) {
            throw new BadRequest("Field '{$field}' is not available.");
        }

        return $defs['type'] ?? '';
    }

    /**
     * Resolves record names for link fields in one query.
     *
     * @param string[] $ids
     * @return array<string, string>
     */
    private function linkLabels(array $group, array $ids): array
    {
        $foreignEntityType = $group['foreignEntityType'];
        $ids = array_values(array_filter($ids, fn ($id) => $id !== ''));

        if (!$foreignEntityType || !$ids) {
            return [];
        }

        $defs = $this->entityManager->getDefs()->getEntity($foreignEntityType);

        if (!$defs->hasAttribute('name')) {
            return [];
        }

        $labels = [];

        $collection = $this->entityManager
            ->getRDBRepository($foreignEntityType)
            ->select(['id', 'name'])
            ->where(['id' => $ids])
            ->find();

        foreach ($collection as $entity) {
            $labels[$entity->getId()] = (string) $entity->get('name');
        }

        return $labels;
    }

    private static function key(mixed $value): string
    {
        if ($value === null) {
            return '';
        }

        if (is_bool($value)) {
            return $value ? '1' : '0';
        }

        return (string) $value;
    }

    private static function number(mixed $value): float|int
    {
        if (!is_numeric($value)) {
            return 0;
        }

        $number = $value + 0;

        return is_float($number) ? round($number, 4) : $number;
    }
}
