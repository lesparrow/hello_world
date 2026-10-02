<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Query;

use Espo\Core\Select\SelectBuilderFactory;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\ExpressionCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\FormulaError;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\FormulaParser;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\JoinRegistry;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\PathResolver;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\RecordSelector;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\SchemaError;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\ToManyRelation;
use Espo\ORM\Query\Part\Condition;
use Espo\ORM\Query\Part\Expression;
use Espo\ORM\Query\Part\Join;
use Espo\ORM\Query\SelectBuilder;

/**
 * Joins the record picked by a record selector, once per query, so that every field read through the selector comes
 * from the SAME record:
 *
 *   LEFT JOIN (
 *       SELECT c.fk k, MAX(c.id) id                         -- tie-break on ID
 *       FROM <candidates> c
 *       JOIN (SELECT fk k, MAX(order) v FROM <candidates> GROUP BY fk) best
 *            ON best.k = c.fk AND best.v = c.order
 *       GROUP BY c.fk
 *   ) pick ON pick.k = <owner key>
 *   LEFT JOIN related sel ON sel.id = pick.id
 *
 * (MIN instead of MAX for ascending rules.) Candidates are the related records the user can read (ACL), with a
 * non-empty order value, matching the optional condition. Plain GROUP BY sub-queries are used rather than window
 * functions, so this works on every database EspoCRM supports. Each owner record gets at most one selected record:
 * data-source rows are never duplicated.
 */
class SelectorJoiner
{
    public function __construct(
        private PathResolver $pathResolver,
        private FormulaParser $formulaParser,
        private SelectBuilderFactory $selectBuilderFactory,
        private UserContext $userContext,
        private Limits $limits,
    ) {}

    /**
     * @return array{string, string} [alias, entityType]
     * @throws SchemaError
     */
    public function join(RecordSelector $selector, string $rootEntityType, JoinRegistry $registry): array
    {
        if ($registry->has($selector->name)) {
            return [$registry->getAlias($selector->name), $this->getEntityType($registry, $selector)];
        }

        $registry->startResolving('selector:' . $selector->name);

        try {
            $relation = $this->pathResolver->resolveToMany($rootEntityType, $selector->from, $selector->link, $registry);
        } finally {
            $registry->endResolving('selector:' . $selector->name);
        }

        $function = $selector->isDescending() ? 'MAX' : 'MIN';

        try {
            [$best, $bestOrder] = $this->buildCandidates($selector, $relation);
            [$pick, $pickOrder] = $this->buildCandidates($selector, $relation);
        } catch (FormulaError $e) {
            throw new SchemaError("{$this->getLabel($selector)}: {$e->getMessage()}");
        }

        $best
            ->select([
                [$relation->foreignKey, 'k'],
                [Expression::create("{$function}:({$bestOrder->getValue()})")->getValue(), 'v'],
            ])
            ->group([$relation->foreignKey])
            ->order([]);

        $pick
            ->join(
                Join::createWithSubQuery($best->build(), 'acxBest')->withConditions(
                    Condition::and(
                        Condition::equal(Expression::column('acxBest.k'), Expression::column($relation->foreignKey)),
                        Condition::equal(Expression::column('acxBest.v'), $pickOrder),
                    )
                )
            )
            ->select([
                [$relation->foreignKey, 'k'],
                [Expression::create("{$function}:(id)")->getValue(), 'id'],
            ])
            ->group([$relation->foreignKey])
            ->order([]);

        $pickAlias = $registry->nextAlias('acxP');

        $registry->addJoin(
            'selector#' . $selector->name,
            Join::createWithSubQuery($pick->build(), $pickAlias)
                ->withConditions(Condition::equal(Expression::column("{$pickAlias}.k"), $relation->localKey)),
            $pickAlias
        );

        $alias = $registry->nextAlias();

        $registry->add($selector->name, $relation->entityType, [
            "{$alias}.id:" => "{$pickAlias}.id",
            "{$alias}.deleted" => false,
        ], $alias);

        return [$alias, $relation->entityType];
    }

    /**
     * Records of the relation that can be selected, and the expression they are ordered by.
     *
     * @return array{SelectBuilder, Expression}
     */
    private function buildCandidates(RecordSelector $selector, ToManyRelation $relation): array
    {
        $target = $relation->entityType;
        $subRegistry = new JoinRegistry($this->limits->maxJoins());

        $order = $this->pathResolver->resolve($target, $selector->getOrderBy(), $subRegistry);

        if (in_array($order->fieldType, ['text', 'bool', 'personName'], true)) {
            throw new SchemaError("{$this->getLabel($selector)}: this field can't be used to order records.");
        }

        // A dedicated compiler: this can run while another formula is being compiled.
        $condition = $selector->condition !== null ?
            (new ExpressionCompiler($this->formulaParser, $this->pathResolver))
                ->compileRecord($selector->condition, $target, $subRegistry) :
            null;

        $builder = $this->selectBuilderFactory
            ->create()
            ->from($target)
            ->forUser($this->userContext->getUser())
            ->withAccessControlFilter()
            ->buildQueryBuilder();

        $relation->applyTo($builder);
        $subRegistry->applyTo($builder);

        $builder->where(Expression::isNotNull($order->expression));

        if ($condition) {
            $builder->where($condition);
        }

        return [$builder, $order->expression];
    }

    private function getEntityType(JoinRegistry $registry, RecordSelector $selector): string
    {
        return (string) $registry->getEntityType($selector->name);
    }

    private function getLabel(RecordSelector $selector): string
    {
        return $selector->label ?? $selector->name;
    }
}
