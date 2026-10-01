<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Formula;

use Espo\Core\Formula\Parser\Ast\Attribute;
use Espo\Core\Formula\Parser\Ast\Node;
use Espo\Core\Formula\Parser\Ast\Value;
use Espo\Core\Formula\Parser\Ast\Variable;

/**
 * Evaluates display formulas, e.g. `margin / revenue * 100`, where identifiers are keys of other measures.
 * Runs in PHP on already aggregated values (one evaluation per cell), never touches the database.
 * NULL propagates through arithmetic; division by zero yields NULL.
 */
class DisplayEvaluator
{
    private const FUNCTIONS = [
        'ifThen', 'ifThenElse', 'IF', 'if', 'number\\round', 'number\\abs', 'number\\floor', 'number\\ceil',
        'comparison\\nullCoalescing', 'logical\\and', 'logical\\or', 'logical\\not',
        'numeric\\summation', 'numeric\\subtraction', 'numeric\\multiplication', 'numeric\\division',
        'numeric\\modulo', 'comparison\\equals', 'comparison\\notEquals', 'comparison\\greaterThan',
        'comparison\\lessThan', 'comparison\\greaterThanOrEquals', 'comparison\\lessThanOrEquals',
    ];

    public function __construct(private FormulaParser $parser) {}

    /**
     * @param string[] $availableKeys Keys of measures that may be referenced.
     * @return string[] Referenced keys.
     * @throws FormulaError
     */
    public function validate(string $formula, array $availableKeys): array
    {
        $keys = [];

        $this->walk($this->parser->parse($formula), function ($node) use ($availableKeys, &$keys) {
            if ($node instanceof Attribute) {
                if (!in_array($node->getName(), $availableKeys, true)) {
                    throw FormulaError::create("Unknown measure: {$node->getName()}");
                }

                $keys[] = $node->getName();
            }

            if ($node instanceof Variable) {
                throw FormulaError::create("Variables are not supported.");
            }

            if ($node instanceof Node && !in_array($node->getType(), self::FUNCTIONS, true)) {
                throw FormulaError::create("Function '{$node->getType()}' is not supported in display formulas.");
            }
        });

        return array_values(array_unique($keys));
    }

    /**
     * @param array<string, int|float|null> $values
     */
    public function evaluate(string $formula, array $values): int|float|null
    {
        $result = $this->evaluateNode($this->parser->parse($formula), $values);

        if (is_bool($result)) {
            return $result ? 1 : 0;
        }

        return is_int($result) || is_float($result) ? $result : null;
    }

    private function evaluateNode(Node|Value|Attribute|Variable $node, array $values): mixed
    {
        if ($node instanceof Value) {
            return $node->getValue();
        }

        if ($node instanceof Attribute) {
            return $values[$node->getName()] ?? null;
        }

        if (!$node instanceof Node) {
            return null;
        }

        $args = $node->getChildNodes();
        $eval = fn (int $i) => isset($args[$i]) ? $this->evaluateNode($args[$i], $values) : null;

        switch ($node->getType()) {
            case 'numeric\\summation':
                return self::arithmetic($eval(0), $eval(1), fn ($a, $b) => $a + $b);

            case 'numeric\\subtraction':
                $first = $eval(0);

                if ($args[0] instanceof Value && $first === null) {
                    $second = $eval(1);

                    return is_numeric($second) ? -$second : null;
                }

                return self::arithmetic($first, $eval(1), fn ($a, $b) => $a - $b);

            case 'numeric\\multiplication':
                return self::arithmetic($eval(0), $eval(1), fn ($a, $b) => $a * $b);

            case 'numeric\\division':
                return self::arithmetic($eval(0), $eval(1), fn ($a, $b) => $b == 0 ? null : $a / $b);

            case 'numeric\\modulo':
                return self::arithmetic($eval(0), $eval(1), fn ($a, $b) => $b == 0 ? null : fmod($a, $b));

            case 'comparison\\equals':
                return $eval(0) == $eval(1);

            case 'comparison\\notEquals':
                return $eval(0) != $eval(1);

            case 'comparison\\greaterThan':
                return self::compare($eval(0), $eval(1), fn ($a, $b) => $a > $b);

            case 'comparison\\lessThan':
                return self::compare($eval(0), $eval(1), fn ($a, $b) => $a < $b);

            case 'comparison\\greaterThanOrEquals':
                return self::compare($eval(0), $eval(1), fn ($a, $b) => $a >= $b);

            case 'comparison\\lessThanOrEquals':
                return self::compare($eval(0), $eval(1), fn ($a, $b) => $a <= $b);

            case 'logical\\and':
                foreach (array_keys($args) as $i) {
                    if (!$eval($i)) {
                        return false;
                    }
                }

                return true;

            case 'logical\\or':
                foreach (array_keys($args) as $i) {
                    if ($eval($i)) {
                        return true;
                    }
                }

                return false;

            case 'logical\\not':
                return !$eval(0);

            case 'comparison\\nullCoalescing':
                return $eval(0) ?? $eval(1);

            case 'ifThen':
            case 'ifThenElse':
            case 'IF':
            case 'if':
                return $eval(0) ? $eval(1) : $eval(2);

            case 'number\\round':
                $value = $eval(0);

                return is_numeric($value) ? round((float) $value, (int) ($eval(1) ?? 0)) : null;

            case 'number\\abs':
                $value = $eval(0);

                return is_numeric($value) ? abs($value) : null;

            case 'number\\floor':
                $value = $eval(0);

                return is_numeric($value) ? floor((float) $value) : null;

            case 'number\\ceil':
                $value = $eval(0);

                return is_numeric($value) ? ceil((float) $value) : null;
        }

        return null;
    }

    private static function arithmetic(mixed $a, mixed $b, callable $operation): int|float|null
    {
        if (!is_numeric($a) || !is_numeric($b)) {
            return null;
        }

        return $operation($a + 0, $b + 0);
    }

    private static function compare(mixed $a, mixed $b, callable $operation): ?bool
    {
        if ($a === null || $b === null) {
            return null;
        }

        return $operation($a, $b);
    }

    private function walk(Node|Value|Attribute|Variable $node, callable $callback): void
    {
        $callback($node);

        if ($node instanceof Node) {
            foreach ($node->getChildNodes() as $child) {
                $this->walk($child, $callback);
            }
        }
    }
}
