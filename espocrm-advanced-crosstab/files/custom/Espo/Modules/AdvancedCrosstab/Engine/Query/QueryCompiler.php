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
use Espo\ORM\Query\Part\Expression;

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

        $registry = new JoinRegistry($this->limits->maxJoins());

        $rows = array_map(fn (Dimension $d) => $this->compileDimension($d, $entityType, $registry), $definition->rows);
        $columns = array_map(fn (Dimension $d) => $this->compileDimension($d, $entityType, $registry), $definition->columns);

        $measureExpressions = [];
        $measureConditions = [];
        $availableKeys = [];

        foreach ($definition->measures as $measure) {
            try {
                if ($measure->kind === Measure::KIND_DISPLAY) {
                    $this->displayEvaluator->validate((string) $measure->formula, $availableKeys);
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

        foreach (explode('.', $path) as $segment) {
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
