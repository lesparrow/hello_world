<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Formula;

use Espo\Core\Formula\Parser\Ast\Attribute;
use Espo\Core\Formula\Parser\Ast\Node;
use Espo\Core\Formula\Parser\Ast\Value;
use Espo\Core\Formula\Parser\Ast\Variable;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\JoinRegistry;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\PathResolver;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\SchemaError;
use Espo\ORM\Query\Part\Expression;

/**
 * Compiles EspoCRM Formula AST into ORM expressions, which the ORM turns into SQL
 * with quoted literals. User input is never concatenated into SQL:
 * - field references go through PathResolver (metadata + ACL validated);
 * - function names come from a fixed whitelist;
 * - literals are passed as values and quoted by the database driver.
 *
 * Two modes:
 * - record:    evaluated per record, e.g. `amount - cost`, `ifThen(status == 'Won', amount, 0)`;
 * - aggregate: evaluated per group, e.g. `SUM(amount) - SUM(cost)`. Fields must be inside
 *              an aggregate function. Because each group (cell, subtotal, total) is computed by
 *              the database from records, ratios are always ratios of aggregates, never averages
 *              of ratios.
 */
class ExpressionCompiler
{
    public const MODE_RECORD = 'record';
    public const MODE_AGGREGATE = 'aggregate';

    public const AGGREGATE_FUNCTIONS = [
        'SUM' => 'SUM',
        'AVG' => 'AVG',
        'AVERAGE' => 'AVG',
        'MIN' => 'MIN',
        'MAX' => 'MAX',
        'COUNT' => 'COUNT',
        'COUNT_DISTINCT' => 'COUNT_DISTINCT',
        'COUNTDISTINCT' => 'COUNT_DISTINCT',
    ];

    /**
     * Formula function → [ORM function, min args, max args].
     */
    private const SIMPLE_FUNCTIONS = [
        'string\\concat' => ['CONCAT', 1, 50],
        'string\\lowerCase' => ['LOWER', 1, 1],
        'string\\upperCase' => ['UPPER', 1, 1],
        'string\\trim' => ['TRIM', 1, 1],
        'string\\length' => ['CHAR_LENGTH', 1, 1],
        'string\\replace' => ['REPLACE', 3, 3],
        'number\\abs' => ['ABS', 1, 1],
        'number\\floor' => ['FLOOR', 1, 1],
        'number\\ceil' => ['CEIL', 1, 1],
        'datetime\\year' => ['YEAR_NUMBER', 1, 1],
        'datetime\\month' => ['MONTH_NUMBER', 1, 1],
        'datetime\\date' => ['DAYOFMONTH', 1, 1],
        'datetime\\dayOfWeek' => ['DAYOFWEEK_NUMBER', 1, 1],
        'datetime\\hour' => ['HOUR_NUMBER', 1, 1],
        'datetime\\minute' => ['MINUTE_NUMBER', 1, 1],
        'comparison\\nullCoalescing' => ['COALESCE', 2, 2],
        'GREATEST' => ['GREATEST', 2, 20],
        'LEAST' => ['LEAST', 2, 20],
        'COALESCE' => ['COALESCE', 1, 20],
        'ABS' => ['ABS', 1, 1],
    ];

    private const OPERATORS = [
        'numeric\\summation' => 'ADD',
        'numeric\\multiplication' => 'MUL',
        'numeric\\modulo' => 'MOD',
        'comparison\\greaterThan' => 'GREATER_THAN',
        'comparison\\lessThan' => 'LESS_THAN',
        'comparison\\greaterThanOrEquals' => 'GREATER_THAN_OR_EQUAL',
        'comparison\\lessThanOrEquals' => 'LESS_THAN_OR_EQUAL',
        'logical\\and' => 'AND',
        'logical\\or' => 'OR',
    ];

    private const DIFF_UNITS = [
        'years' => 'TIMESTAMPDIFF_YEAR',
        'months' => 'TIMESTAMPDIFF_MONTH',
        'weeks' => 'TIMESTAMPDIFF_WEEK',
        'days' => 'TIMESTAMPDIFF_DAY',
        'hours' => 'TIMESTAMPDIFF_HOUR',
        'minutes' => 'TIMESTAMPDIFF_MINUTE',
        'seconds' => 'TIMESTAMPDIFF_SECOND',
    ];

    /** Set while compiling the inside of an aggregate function. */
    private bool $insideAggregate = false;
    private bool $hasAggregate = false;

    public function __construct(
        private FormulaParser $parser,
        private PathResolver $pathResolver,
    ) {}

    /**
     * Compile a record-level formula (dimension, condition, native measure expression).
     */
    public function compileRecord(string $formula, string $entityType, JoinRegistry $registry): Expression
    {
        $this->insideAggregate = false;

        return $this->compileNode($this->parser->parse($formula), self::MODE_RECORD, $entityType, $registry, null);
    }

    /**
     * Compile an aggregate formula. An optional record-level condition restricts all aggregates.
     */
    public function compileAggregate(
        string $formula,
        string $entityType,
        JoinRegistry $registry,
        ?Expression $condition = null
    ): Expression {

        $this->insideAggregate = false;
        $this->hasAggregate = false;

        $expression = $this->compileNode(
            $this->parser->parse($formula),
            self::MODE_AGGREGATE,
            $entityType,
            $registry,
            $condition
        );

        if (!$this->hasAggregate) {
            throw FormulaError::create(
                "An aggregate formula must use an aggregate function, e.g. SUM(amount) or COUNT(id)."
            );
        }

        return $expression;
    }

    /**
     * Build `AGGREGATION(expression)` for a native measure.
     */
    public function buildAggregate(string $aggregation, Expression $expression, ?Expression $condition): Expression
    {
        if ($condition) {
            $expression = Expression::if($condition, $expression, Expression::value(null));
        }

        return self::fn($aggregation, $expression);
    }

    private function compileNode(
        Node|Value|Attribute|Variable $node,
        string $mode,
        string $entityType,
        JoinRegistry $registry,
        ?Expression $condition
    ): Expression {

        if ($node instanceof Value) {
            return $this->compileValue($node->getValue());
        }

        if ($node instanceof Variable) {
            throw FormulaError::create("Variables are not supported.");
        }

        if ($node instanceof Attribute) {
            $path = $node->getName();

            if ($mode === self::MODE_AGGREGATE && !$this->insideAggregate) {
                throw FormulaError::create(
                    "Field '{$path}' must be used inside an aggregate function, e.g. SUM({$path})."
                );
            }

            try {
                return $this->pathResolver->resolve($entityType, $path, $registry)->expression;
            } catch (SchemaError $e) {
                throw FormulaError::create($e->getMessage());
            }
        }

        $type = $node->getType();
        $args = $node->getChildNodes();

        $compile = fn ($child) => $this->compileNode($child, $mode, $entityType, $registry, $condition);

        $upperType = strtoupper($type);

        // Spreadsheet-style COUNT(x) in a record formula: 1 when x is not empty, else 0.
        if ($upperType === 'COUNT' && ($mode === self::MODE_RECORD || $this->insideAggregate) && count($args) === 1) {
            $value = $compile($args[0]);

            return Expression::if(
                Expression::and(Expression::isNotNull($value), Expression::notEqual($value, Expression::value(''))),
                Expression::value(1),
                Expression::value(0)
            );
        }

        if (isset(self::AGGREGATE_FUNCTIONS[$upperType])) {
            return $this->compileAggregateFunction($upperType, $args, $mode, $entityType, $registry, $condition);
        }

        // Spreadsheet-style logical functions: AND(a, b, …), OR(a, b, …), NOT(a).
        if (in_array($upperType, ['AND', 'OR'], true) && $type === $upperType) {
            $this->assertArgCount($type, $args, 1, 50);

            return self::fn($upperType, ...array_map($compile, $args));
        }

        if ($type === 'NOT') {
            $this->assertArgCount($type, $args, 1, 1);

            return Expression::not($compile($args[0]));
        }

        if (isset(self::OPERATORS[$type])) {
            return self::fn(self::OPERATORS[$type], ...array_map($compile, $args));
        }

        switch ($type) {
            case 'numeric\\subtraction':
                // The parser represents unary minus as NULL - x.
                if ($args[0] instanceof Value && $args[0]->getValue() === null) {
                    return Expression::multiply(-1, $compile($args[1]));
                }

                return self::fn('SUB', ...array_map($compile, $args));

            case 'numeric\\division':
                // NULLIF avoids division-by-zero errors on all database platforms.
                return Expression::divide(
                    $compile($args[0]),
                    Expression::nullIf($compile($args[1]), Expression::value(0))
                );

            case 'comparison\\equals':
            case 'comparison\\notEquals':
                return $this->compileEquality($type === 'comparison\\equals', $args, $compile);

            case 'logical\\not':
                $this->assertArgCount($type, $args, 1, 1);

                return Expression::not($compile($args[0]));

            case 'ifThen':
            case 'ifThenElse':
            case 'IF':
            case 'if':
                $this->assertArgCount($type, $args, 2, 3);

                return Expression::if(
                    $compile($args[0]),
                    $compile($args[1]),
                    isset($args[2]) ? $compile($args[2]) : Expression::value(null)
                );

            case 'number\\round':
                $this->assertArgCount($type, $args, 1, 2);

                return Expression::round($compile($args[0]), isset($args[1]) ? (int) $this->literal($args[1]) : 0);

            case 'CONTAINS':
            case 'string\\contains':
                $this->assertArgCount($type, $args, 2, 2);
                $needle = $this->literal($args[1]);

                if (!is_string($needle)) {
                    throw FormulaError::create("string\\contains: the second argument must be a text literal.");
                }

                return Expression::like($compile($args[0]), '%' . $needle . '%');

            case 'datetime\\now':
                return Expression::now();

            case 'datetime\\today':
                return Expression::date(Expression::now());

            case 'datetime\\diff':
                $this->assertArgCount($type, $args, 2, 3);
                $unit = isset($args[2]) ? $this->literal($args[2]) : 'days';

                if (!is_string($unit) || !isset(self::DIFF_UNITS[$unit])) {
                    throw FormulaError::create(
                        "datetime\\diff: unit must be one of: " . implode(', ', array_keys(self::DIFF_UNITS)) . "."
                    );
                }

                // datetime\diff(a, b) = a - b
                return self::fn(self::DIFF_UNITS[$unit], $compile($args[1]), $compile($args[0]));

            case 'array\\includes':
                $this->assertArgCount($type, $args, 2, 2);
                $list = $args[0];

                if (!$list instanceof Node || $list->getType() !== 'list') {
                    throw FormulaError::create("array\\includes: the first argument must be list(...) of literals.");
                }

                $values = array_map(fn ($item) => $this->literal($item), $list->getChildNodes());

                if ($values === []) {
                    return Expression::value(false);
                }

                return Expression::in($compile($args[1]), $values);
        }

        if (isset(self::SIMPLE_FUNCTIONS[$type])) {
            [$function, $min, $max] = self::SIMPLE_FUNCTIONS[$type];
            $this->assertArgCount($type, $args, $min, $max);

            return self::fn($function, ...array_map($compile, $args));
        }

        throw FormulaError::create("Function '{$type}' is not supported in crosstab formulas.");
    }

    /**
     * @param array<int, Node|Value|Attribute|Variable> $args
     */
    private function compileAggregateFunction(
        string $name,
        array $args,
        string $mode,
        string $entityType,
        JoinRegistry $registry,
        ?Expression $condition
    ): Expression {

        if ($mode !== self::MODE_AGGREGATE) {
            throw FormulaError::create(
                "Aggregate function {$name} is not allowed here. Use an aggregate measure for aggregate formulas."
            );
        }

        if ($this->insideAggregate) {
            throw FormulaError::create("Aggregate functions can't be nested.");
        }

        $function = self::AGGREGATE_FUNCTIONS[$name];

        if (count($args) > 2 || (count($args) === 0 && $function !== 'COUNT')) {
            throw FormulaError::create("{$name} takes an expression and an optional condition.");
        }

        $this->insideAggregate = true;
        $this->hasAggregate = true;

        try {
            $value = $args === [] ?
                Expression::column('id') :
                $this->compileNode($args[0], $mode, $entityType, $registry, null);

            $localCondition = isset($args[1]) ?
                $this->compileNode($args[1], $mode, $entityType, $registry, null) :
                null;
        } finally {
            $this->insideAggregate = false;
        }

        $conditions = array_values(array_filter([$condition, $localCondition]));

        $combined = match (count($conditions)) {
            0 => null,
            1 => $conditions[0],
            default => Expression::and(...$conditions),
        };

        return $this->buildAggregate($function, $value, $combined);
    }

    /**
     * @param array<int, Node|Value|Attribute|Variable> $args
     */
    private function compileEquality(bool $equals, array $args, callable $compile): Expression
    {
        $this->assertArgCount('==', $args, 2, 2);

        foreach ([0, 1] as $i) {
            if ($args[$i] instanceof Value && $args[$i]->getValue() === null) {
                $other = $compile($args[1 - $i]);

                return $equals ? Expression::isNull($other) : Expression::isNotNull($other);
            }
        }

        return $equals ?
            Expression::equal($compile($args[0]), $compile($args[1])) :
            Expression::notEqual($compile($args[0]), $compile($args[1]));
    }

    private function compileValue(mixed $value): Expression
    {
        if (is_string($value)) {
            return Expression::value($this->sanitizeString($value));
        }

        if (is_int($value) || is_float($value) || is_bool($value) || $value === null) {
            return Expression::value($value);
        }

        throw FormulaError::create("Unsupported value.");
    }

    private function literal(Node|Value|Attribute|Variable $node): string|int|float|bool|null
    {
        if ($node instanceof Value) {
            $value = $node->getValue();

            if (is_string($value)) {
                return $this->sanitizeString($value);
            }

            if (is_scalar($value) || $value === null) {
                return $value;
            }
        }

        if (
            $node instanceof Node &&
            $node->getType() === 'numeric\\subtraction' &&
            $node->getChildNodes()[0] instanceof Value &&
            $node->getChildNodes()[0]->getValue() === null &&
            $node->getChildNodes()[1] instanceof Value &&
            is_numeric($node->getChildNodes()[1]->getValue())
        ) {
            return -$node->getChildNodes()[1]->getValue();
        }

        throw FormulaError::create("A literal value is expected.");
    }

    /**
     * String literals are quoted by the database driver. Backslashes and control characters are rejected
     * so that a literal can't break out of the ORM expression syntax.
     */
    private function sanitizeString(string $value): string
    {
        $value = str_replace(["\\'", '\\"'], ["'", '"'], $value);

        if (str_contains($value, '\\') || preg_match('/[\x00-\x1F]/', $value) || mb_strlen($value) > 500) {
            throw FormulaError::create("Invalid text literal.");
        }

        return $value;
    }

    /**
     * @param array<int, mixed> $args
     */
    private function assertArgCount(string $name, array $args, int $min, int $max): void
    {
        $count = count($args);

        if ($count < $min || $count > $max) {
            throw FormulaError::create("Wrong number of arguments for {$name}.");
        }
    }

    private static function fn(string $function, Expression ...$args): Expression
    {
        return Expression::create(
            $function . ':(' . implode(', ', array_map(fn (Expression $e) => $e->getValue(), $args)) . ')'
        );
    }
}
