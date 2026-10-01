<?php

namespace Espo\Modules\AdvancedCrosstab\Tools;

use Espo\Core\Acl;
use Espo\Core\Acl\Table;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Core\FieldProcessing\ListLoadProcessor;
use Espo\Core\FieldProcessing\Loader\Params as LoaderParams;
use Espo\Core\Record\Collection as RecordCollection;
use Espo\Core\Record\ServiceContainer;
use Espo\Core\Select\SearchParams;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\Definition;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\DefinitionParser;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\DisplayEvaluator;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\ExpressionCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\FormulaError;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Espo\Modules\AdvancedCrosstab\Engine\Pivot\PivotEngine;
use Espo\Modules\AdvancedCrosstab\Engine\Query\CompiledDimension;
use Espo\Modules\AdvancedCrosstab\Engine\Query\QueryCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Query\UserContext;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\JoinRegistry;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\SchemaError;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\Part\Condition;
use Espo\ORM\Query\Part\Expression;
use Espo\ORM\Query\Part\Selection;
use Espo\ORM\Query\Part\WhereItem;
use PDO;
use stdClass;

class ReportService
{
    public const ENTITY_TYPE = 'AdvancedCrosstab';

    public function __construct(
        private Acl $acl,
        private EntityManager $entityManager,
        private DefinitionParser $definitionParser,
        private PivotEngine $pivotEngine,
        private QueryCompiler $queryCompiler,
        private ExpressionCompiler $expressionCompiler,
        private DisplayEvaluator $displayEvaluator,
        private SelectBuilderFactory $selectBuilderFactory,
        private ServiceContainer $recordServiceContainer,
        private ListLoadProcessor $listLoadProcessor,
        private UserContext $userContext,
        private Limits $limits,
    ) {}

    /**
     * A saved crosstab (read access to the report required) or an ad-hoc definition.
     * In both cases the data is always restricted by the ACL of the current user, never the author's.
     *
     * @throws Forbidden
     * @throws NotFound
     * @throws BadRequest
     */
    public function getDefinition(?string $id, mixed $rawDefinition): Definition
    {
        if (!$this->acl->checkScope(self::ENTITY_TYPE, Table::ACTION_READ)) {
            throw new Forbidden("No access to Advanced Crosstab.");
        }

        if ($rawDefinition !== null) {
            if (!$rawDefinition instanceof stdClass && !is_array($rawDefinition)) {
                throw new BadRequest("Bad definition.");
            }

            return $this->definitionParser->parse($rawDefinition);
        }

        if (!$id) {
            throw new BadRequest("No ID or definition.");
        }

        $entity = $this->entityManager->getEntityById(self::ENTITY_TYPE, $id);

        if (!$entity) {
            throw new NotFound();
        }

        if (!$this->acl->checkEntityRead($entity)) {
            throw new Forbidden();
        }

        return $this->definitionParser->parse($entity->get('definition') ?? new stdClass());
    }

    public function run(Definition $definition, bool $useCache = true): array
    {
        return $this->pivotEngine->run($definition, $useCache);
    }

    /**
     * Validates a formula and returns a preview computed with the user's ACL.
     *
     * @return array{valid: bool, error?: string, preview?: mixed}
     */
    public function validateFormula(stdClass $data): array
    {
        if (!$this->acl->checkScope(self::ENTITY_TYPE, Table::ACTION_READ)) {
            throw new Forbidden();
        }

        $entityType = $data->entityType ?? null;
        $formula = $data->formula ?? null;
        $kind = $data->kind ?? 'record';

        if (!is_string($entityType) || !$this->acl->checkScope($entityType, Table::ACTION_READ)) {
            throw new Forbidden();
        }

        if (!is_string($formula) || trim($formula) === '') {
            return ['valid' => false, 'error' => 'Formula is empty.'];
        }

        if (strlen($formula) > $this->limits->maxFormulaLength()) {
            return ['valid' => false, 'error' => 'Formula is too long.'];
        }

        try {
            if ($kind === 'display') {
                $keys = array_values(array_filter((array) ($data->measureKeys ?? []), 'is_string'));
                $this->displayEvaluator->validate($formula, $keys);

                return ['valid' => true];
            }

            $registry = new JoinRegistry($this->limits->maxJoins());

            if ($kind === 'aggregate') {
                $expression = $this->expressionCompiler->compileAggregate($formula, $entityType, $registry);

                $rows = $this->previewQuery($entityType, $registry, [Selection::create($expression, 'v')], null, 1);

                return ['valid' => true, 'preview' => ['value' => PivotEngine::number($rows[0]['v'] ?? null)]];
            }

            $expression = $this->expressionCompiler->compileRecord($formula, $entityType, $registry);

            if ($kind === 'condition') {
                $rows = $this->previewQuery(
                    $entityType,
                    $registry,
                    [Selection::create(Expression::count(Expression::column('id')), 'v')],
                    Condition::equal($expression, true),
                    1
                );

                return ['valid' => true, 'preview' => ['count' => (int) ($rows[0]['v'] ?? 0)]];
            }

            $rows = $this->previewQuery($entityType, $registry, [Selection::create($expression, 'v')], null, 5);

            return ['valid' => true, 'preview' => ['values' => array_map(fn ($row) => $row['v'], $rows)]];
        } catch (FormulaError|SchemaError $e) {
            return ['valid' => false, 'error' => $e->getMessage()];
        } catch (BadRequest $e) {
            return ['valid' => false, 'error' => $e->getMessage() ?: 'Invalid formula.'];
        } catch (\PDOException) {
            return ['valid' => false, 'error' => 'The formula could not be evaluated by the database (check value types).'];
        }
    }

    /**
     * Records behind one crosstab cell, listed with EspoCRM's standard list API format.
     *
     * The cell is identified by its row/column key paths. The same expressions as for grouping are used,
     * so the records are exactly those aggregated in the cell (formula and date dimensions included).
     */
    public function drillDown(stdClass $payload, SearchParams $searchParams): RecordCollection
    {
        $definition = $this->getDefinition($payload->id ?? null, $payload->definition ?? null);

        $rowPath = $this->parseKeyPath($payload->rowPath ?? [], count($definition->rows));
        $columnPath = $this->parseKeyPath($payload->columnPath ?? [], count($definition->columns));

        $maxSize = min($searchParams->getMaxSize() ?? 20, $this->limits->drillDownMaxSize());

        $recordService = $this->recordServiceContainer->get($definition->entityType);

        $searchParams = $recordService->prepareSearchParams(
            $searchParams->withMaxSize($maxSize)
        );

        $compiled = $this->queryCompiler->compile($definition, $searchParams);

        $builder = $this->entityManager->getQueryBuilder()->select()->clone($compiled->baseQuery);

        foreach ($rowPath as $i => $key) {
            $builder->where($this->cellCondition($compiled->rows[$i], $key));
        }

        foreach ($columnPath as $i => $key) {
            $builder->where($this->cellCondition($compiled->columns[$i], $key));
        }

        $measureKey = $payload->measure ?? null;

        if (is_string($measureKey) && ($compiled->measureConditions[$measureKey] ?? null)) {
            $builder->where(Condition::equal($compiled->measureConditions[$measureKey], true));
        }

        $query = $builder->build();

        $repository = $this->entityManager->getRDBRepository($definition->entityType);

        $collection = $repository->clone($query)->find();

        $loaderParams = LoaderParams::create()->withSelect($searchParams->getSelect());

        foreach ($collection as $entity) {
            $this->listLoadProcessor->process($entity, $loaderParams);
            $recordService->prepareEntityForOutput($entity);
        }

        $total = $repository->clone($query)->count();

        return RecordCollection::create($collection, $total);
    }

    private function cellCondition(CompiledDimension $dimension, string $key): WhereItem
    {
        $expression = $dimension->expression;

        if ($key === '') {
            return $dimension->isTextual() ?
                Condition::or(Condition::equal($expression, null), Condition::equal($expression, '')) :
                Condition::equal($expression, null);
        }

        return Condition::equal($expression, $key);
    }

    /**
     * @return string[]
     */
    private function parseKeyPath(mixed $path, int $max): array
    {
        if (!is_array($path) || count($path) > $max) {
            throw new BadRequest("Bad cell path.");
        }

        return array_map(function ($key) {
            if (!is_scalar($key) && $key !== null) {
                throw new BadRequest("Bad cell key.");
            }

            return (string) $key;
        }, array_values($path));
    }

    /**
     * @param Selection[] $select
     */
    private function previewQuery(
        string $entityType,
        JoinRegistry $registry,
        array $select,
        ?WhereItem $where,
        int $limit
    ): array {

        $builder = $this->selectBuilderFactory
            ->create()
            ->from($entityType)
            ->forUser($this->userContext->getUser())
            ->withStrictAccessControl()
            ->buildQueryBuilder();

        $registry->applyTo($builder);

        $builder->select($select)->order([])->limit(0, $limit);

        if ($where) {
            $builder->where($where);
        }

        return $this->entityManager
            ->getQueryExecutor()
            ->execute($builder->build())
            ->fetchAll(PDO::FETCH_ASSOC);
    }
}
