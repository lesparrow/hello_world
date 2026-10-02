<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Query;

use Espo\Core\Acl;
use Espo\Core\Acl\Table;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Select\SearchParams;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Core\Select\Where\Item as WhereItem;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Utils\Language;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\Definition;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\Dimension;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\Measure;
use Espo\Modules\AdvancedCrosstab\Engine\Filter\FilterCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\DisplayEvaluator;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\ExpressionCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\FormulaError;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\JoinRegistry;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\PathResolver;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\SchemaError;
use Espo\Core\Utils\Metadata;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\Part\Condition;
use Espo\ORM\Query\Part\Expression;
use Espo\ORM\Query\Part\Join;

/**
 * Turns a Definition into a base query restricted by ACL and filters,
 * plus the expressions of every dimension and aggregated measure.
 */
class QueryCompiler
{
    private const GRANULARITY_FUNCTIONS = [
        'year' => 'YEAR_NUMBER',
        'quarter' => 'QUARTER',
        'quarterNumber' => 'QUARTER_NUMBER',
        'yearMonth' => 'MONTH',
        'month' => 'MONTH_NUMBER',
        'week' => 'WEEK_1',
        'day' => 'DATE',
        'dayOfWeek' => 'DAYOFWEEK_NUMBER',
    ];

    /** @var array<string, \Espo\Modules\AdvancedCrosstab\Engine\Schema\CustomJoin> */
    private array $customJoins = [];

    public function __construct(
        private Acl $acl,
        private SelectBuilderFactory $selectBuilderFactory,
        private PathResolver $pathResolver,
        private ExpressionCompiler $expressionCompiler,
        private FilterCompiler $filterCompiler,
        private DisplayEvaluator $displayEvaluator,
        private UserContext $userContext,
        private Language $language,
        private Limits $limits,
        private Metadata $metadata,
        private EntityManager $entityManager,
    ) {}

    /**
     * @param ?SearchParams $searchParams Only for record listing (drill-down): order, paging, select.
     * @throws Forbidden
     */
    public function compile(Definition $definition, ?SearchParams $searchParams = null): CompiledQuery
    {
        $entityType = $definition->entityType;

        if (!$this->acl->checkScope($entityType, Table::ACTION_READ)) {
            throw new Forbidden("No read access to {$entityType}.");
        }

        $registry = (new JoinRegistry($this->limits->maxJoins()))->withCustomJoins($definition->joins);

        $this->customJoins = [];

        foreach ($definition->joins as $customJoin) {
            $this->customJoins[$customJoin->name] = $customJoin;
        }

        foreach ($definition->joins as $customJoin) {
            $this->pathResolver->checkCustomJoinTarget($customJoin);
        }

        $rows = array_map(fn (Dimension $d) => $this->compileDimension($d, $entityType, $registry), $definition->rows);
        $columns = array_map(fn (Dimension $d) => $this->compileDimension($d, $entityType, $registry), $definition->columns);

        $measureExpressions = [];
        $measureConditions = [];
        $availableKeys = [];

        foreach ($definition->measures as $measure) {
            try {
                if ($measure->kind === Measure::KIND_DISPLAY) {
                    $this->displayEvaluator->validate((string) $measure->formula, $availableKeys);
                } else if ($measure->kind === Measure::KIND_RELATED) {
                    $measureConditions[$measure->key] = null;
                    $measureExpressions[$measure->key] = $this->compileRelatedMeasure($measure, $entityType, $registry);
                } else {
                    $condition = $measure->condition !== null ?
                        $this->expressionCompiler->compileRecord($measure->condition, $entityType, $registry) :
                        null;

                    $measureConditions[$measure->key] = $condition;
                    $measureExpressions[$measure->key] = $this->compileMeasure($measure, $entityType, $registry, $condition);
                }
            } catch (FormulaError|SchemaError $e) {
                throw FormulaError::create("{$measure->label}: {$e->getMessage()}");
            }

            $availableKeys[] = $measure->key;
        }

        $builder = $this->selectBuilderFactory
            ->create()
            ->from($entityType)
            ->forUser($this->userContext->getUser())
            ->withStrictAccessControl();

        if ($searchParams) {
            $builder->withSearchParams($searchParams);
        }

        // Filters coming from an EspoCRM list view (search panel), applied by EspoCRM's where converter
        // with its field permission checks (strict access control).
        if ($definition->listWhere) {
            $this->applyListWhere($builder, $definition->listWhere);
        }

        if ($definition->primaryFilter) {
            $builder->withPrimaryFilter($definition->primaryFilter);
        }

        try {
            $queryBuilder = $builder->buildQueryBuilder();
        } catch (\InvalidArgumentException) {
            throw new BadRequest("Invalid list filters.");
        }

        $where = $definition->filter ?
            $this->filterCompiler->compile($definition->filter, $entityType, $registry) :
            null;

        // Joins are added once every expression is compiled.
        $registry->applyTo($queryBuilder);

        if ($where) {
            $queryBuilder->where($where);
        }

        return new CompiledQuery(
            definition: $definition,
            baseQuery: $queryBuilder->build(),
            rows: $rows,
            columns: $columns,
            measureExpressions: $measureExpressions,
            measureConditions: $measureConditions,
        );
    }

    /**
     * A list view sends its text search, preset filter and bool filters (e.g. "Only my") as `textFilter` /
     * `primary` / `bool` items;
     * EspoCRM applies those through its filter classes, the rest through its where converter.
     *
     * @param array<int, mixed> $listWhere
     */
    private function applyListWhere(\Espo\Core\Select\SelectBuilder $builder, array $listWhere): void
    {
        $items = [];

        foreach ($listWhere as $item) {
            if (!is_array($item)) {
                throw new BadRequest("Invalid list filters.");
            }

            $type = $item['type'] ?? null;

            if ($type === 'primary') {
                if (!is_string($item['value'] ?? null) || !preg_match('/^[a-zA-Z][a-zA-Z0-9]*$/', $item['value'])) {
                    throw new BadRequest("Invalid list filters.");
                }

                $builder->withPrimaryFilter($item['value']);

                continue;
            }

            if ($type === 'textFilter') {
                if (is_string($item['value'] ?? null) && trim($item['value']) !== '') {
                    $builder->withTextFilter(mb_substr($item['value'], 0, 255));
                }

                continue;
            }

            if ($type === 'bool') {
                $list = array_values(array_filter((array) ($item['value'] ?? []), 'is_string'));

                if ($list) {
                    $builder->withBoolFilterList($list);
                }

                continue;
            }

            $items[] = $item;
        }

        if (!$items) {
            return;
        }

        try {
            $builder->withWhere(WhereItem::fromRawAndGroup($items));
        } catch (\InvalidArgumentException|\TypeError) {
            throw new BadRequest("Invalid list filters.");
        }
    }

    /**
     * Aggregation over the records of a to-many link (or a custom link), without duplicating data-source rows:
     *
     *   LEFT JOIN (SELECT key k, SUM(x) v FROM related WHERE <related ACL> [AND condition] GROUP BY key) r
     *        ON r.k = <data source record key>
     *
     * Each data-source record gets at most one row of r. The outer aggregate then combines these per-record values:
     * SUM / COUNT → SUM(r.v), MIN → MIN(r.v), MAX → MAX(r.v), AVG → SUM(r.s) / SUM(r.c).
     */
    private function compileRelatedMeasure(Measure $measure, string $entityType, JoinRegistry $registry): Expression
    {
        $link = (string) $measure->link;
        $customJoin = $registry->getCustomJoin($link);
        $middle = null;
        $parentTypeCondition = null;

        if ($customJoin) {
            if ($measure->from !== '') {
                throw new SchemaError("A custom link is always used from the data source.");
            }

            $this->pathResolver->checkCustomJoinTarget($customJoin);

            $target = $customJoin->entityType;
            $localKey = $this->pathResolver->resolveKey($entityType, $customJoin->getLocalPath(), $registry)->expression;
            $foreignKey = $this->pathResolver->getKeyAttribute($target, $customJoin->foreignField);
        } else {
            $ownerType = $measure->from === '' ?
                $entityType :
                $this->pathResolver->resolve($entityType, $measure->from . '.id', $registry)->entityType;

            if ($this->pathResolver->isFieldForbidden($ownerType, $link) || !$this->metadata->get(['entityDefs', $ownerType, 'links', $link])) {
                throw new SchemaError("Invalid related link: {$link}");
            }

            $relation = $this->entityManager->getDefs()->getEntity($ownerType)->getRelation($link);

            if (!$relation->hasForeignEntityType()) {
                throw new SchemaError("Invalid related link: {$link}");
            }

            $target = $relation->getForeignEntityType();
            $localKey = $this->pathResolver->resolve($entityType, ($measure->from === '' ? '' : $measure->from . '.') . 'id', $registry)->expression;

            if ($relation->isManyToMany()) {
                $middle = [
                    'entityType' => ucfirst($relation->getRelationshipName()),
                    'nearKey' => $relation->getMidKey(),
                    'farKey' => $relation->getForeignMidKey(),
                    'conditions' => $relation->getConditions(),
                ];
                $foreignKey = 'acxMid.' . $relation->getMidKey();
            } else if ($relation->isHasMany() || $relation->isHasChildren()) {
                $foreignKey = $relation->getForeignKey();

                if ($relation->isHasChildren()) {
                    $parentTypeCondition = [($relation->getParam('foreignType') ?? 'parentType') => $ownerType];
                }
            } else {
                throw new SchemaError("Not a one-to-many or many-to-many link: {$link}. Use its fields directly.");
            }
        }

        if (!$this->acl->checkScope($target, Table::ACTION_READ)) {
            throw new SchemaError("No access to related entity: {$link}");
        }

        // The related entity's own query, with its ACL, joins and formulas.
        $subRegistry = new JoinRegistry($this->limits->maxJoins());

        $value = $measure->expression !== null ?
            $this->expressionCompiler->compileRecord($measure->expression, $target, $subRegistry) :
            Expression::column('id');

        $condition = $measure->condition !== null ?
            $this->expressionCompiler->compileRecord($measure->condition, $target, $subRegistry) :
            null;

        $sub = $this->selectBuilderFactory
            ->create()
            ->from($target)
            ->forUser($this->userContext->getUser())
            ->withAccessControlFilter()
            ->buildQueryBuilder();

        if ($middle) {
            $conditions = [
                "acxMid.{$middle['farKey']}:" => 'id',
                'acxMid.deleted' => false,
            ];

            foreach ($middle['conditions'] as $key => $conditionValue) {
                $conditions["acxMid.{$key}"] = $conditionValue;
            }

            $sub->join($middle['entityType'], 'acxMid', $conditions);
        }

        $subRegistry->applyTo($sub);

        if ($condition) {
            $value = Expression::if($condition, $value, Expression::value(null));
        }

        $aggregation = (string) $measure->aggregation;

        $select = [[$foreignKey, 'k']];

        if ($aggregation === 'AVG') {
            $select[] = [Expression::sum($value)->getValue(), 's'];
            $select[] = [Expression::count($value)->getValue(), 'c'];
        } else {
            $select[] = [Expression::create("{$aggregation}:({$value->getValue()})")->getValue(), 'v'];
        }

        $sub->select($select)
            ->where(["{$foreignKey}!=" => null])
            ->group([$foreignKey])
            ->order([]);

        if ($parentTypeCondition) {
            $sub->where($parentTypeCondition);
        }

        $alias = $registry->nextAlias('acxR');

        $registry->addJoin(
            'related#' . $measure->key,
            Join::createWithSubQuery($sub->build(), $alias)
                ->withConditions(Condition::equal(Expression::column("{$alias}.k"), $localKey)),
            $alias
        );

        return match ($aggregation) {
            'AVG' => Expression::divide(
                Expression::sum(Expression::column("{$alias}.s")),
                Expression::nullIf(Expression::sum(Expression::column("{$alias}.c")), Expression::value(0))
            ),
            'MIN' => Expression::min(Expression::column("{$alias}.v")),
            'MAX' => Expression::max(Expression::column("{$alias}.v")),
            'COUNT' => Expression::coalesce(Expression::sum(Expression::column("{$alias}.v")), Expression::value(0)),
            default => Expression::sum(Expression::column("{$alias}.v")),
        };
    }

    private function compileMeasure(
        Measure $measure,
        string $entityType,
        JoinRegistry $registry,
        ?Expression $condition
    ): Expression {

        if ($measure->kind === Measure::KIND_AGGREGATE) {
            return $this->expressionCompiler->compileAggregate(
                (string) $measure->formula,
                $entityType,
                $registry,
                $condition
            );
        }

        $value = $measure->expression !== null ?
            $this->expressionCompiler->compileRecord($measure->expression, $entityType, $registry) :
            Expression::column('id');

        return $this->expressionCompiler->buildAggregate((string) $measure->aggregation, $value, $condition);
    }

    private function compileDimension(Dimension $dimension, string $entityType, JoinRegistry $registry): CompiledDimension
    {
        if ($dimension->type === Dimension::TYPE_FORMULA) {
            try {
                $expression = $this->expressionCompiler->compileRecord((string) $dimension->formula, $entityType, $registry);
            } catch (FormulaError|SchemaError $e) {
                throw FormulaError::create(($dimension->label ?? 'Dimension') . ": " . $e->getMessage());
            }

            return new CompiledDimension($dimension, $expression, null, null, $dimension->label ?? (string) $dimension->formula);
        }

        $field = $this->pathResolver->resolve($entityType, (string) $dimension->path, $registry);

        if (in_array($field->fieldType, ['text'], true)) {
            throw new SchemaError("A text field can't be used as a dimension: {$field->path}");
        }

        $expression = $field->expression;
        $granularity = null;

        if ($field->isDate()) {
            $granularity = $dimension->granularity ?? 'yearMonth';

            $offset = $this->userContext->getOffsetHours();

            if ($field->isDateTime() && $offset != 0.0) {
                $expression = Expression::convertTimezone($expression, $offset);
            }

            $expression = Expression::create(
                self::GRANULARITY_FUNCTIONS[$granularity] . ':(' . $expression->getValue() . ')'
            );
        }

        return new CompiledDimension(
            $dimension,
            $expression,
            $field,
            $granularity,
            $dimension->label ?? $this->buildPathLabel($entityType, (string) $dimension->path, $granularity)
        );
    }

    public function buildPathLabel(string $entityType, string $path, ?string $granularity = null): string
    {
        $parts = [];
        $current = $entityType;

        foreach (explode('.', $path) as $i => $segment) {
            $customJoin = $i === 0 ? ($this->customJoins[$segment] ?? null) : null;

            if ($customJoin) {
                $parts[] = $customJoin->label ?: $this->language->translateLabel($customJoin->entityType, 'scopeNames');
                $current = $customJoin->entityType;

                continue;
            }

            $parts[] = $this->language->translateLabel($segment, 'fields', $current);
            $current = $this->pathResolver->getManyToOneTarget($current, $segment) ?? $current;
        }

        $label = implode(' › ', $parts);

        if ($granularity) {
            $label .= ' (' . $this->language->translateLabel($granularity, 'granularities', 'AdvancedCrosstab') . ')';
        }

        return $label;
    }
}
