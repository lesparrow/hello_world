<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Formula;

use Espo\Core\Formula\Exceptions\SyntaxError;
use Espo\Core\Formula\Parser;
use Espo\Core\Formula\Parser\Ast\Attribute;
use Espo\Core\Formula\Parser\Ast\Node;
use Espo\Core\Formula\Parser\Ast\Value;
use Espo\Core\Formula\Parser\Ast\Variable;
use Throwable;

/**
 * Parses formulas with the EspoCRM Formula parser.
 *
 * A few conveniences are normalized before parsing (outside string literals only):
 * - `AND`, `OR` (any case) → `&&`, `||`;
 * - `COUNT(DISTINCT x)` → `COUNT_DISTINCT(x)`;
 * - bracketed field references `[amount]`, `[account.industry]` → `amount`, `account.industry`
 *   (the syntax of spreadsheet-style pivot tools).
 */
class FormulaParser
{
    /** @var array<string, Node|Value|Attribute|Variable> */
    private array $cache = [];

    public function parse(string $formula): Node|Value|Attribute|Variable
    {
        if (isset($this->cache[$formula])) {
            return $this->cache[$formula];
        }

        $normalized = $this->normalize($formula);

        try {
            $node = (new Parser())->parse($normalized);
        } catch (SyntaxError $e) {
            throw FormulaError::create("Invalid formula syntax: " . $e->getMessage());
        } catch (Throwable) {
            throw FormulaError::create("Invalid formula syntax.");
        }

        if ($node instanceof Node && in_array($node->getType(), ['bundle', 'assign', 'variable'], true)) {
            throw FormulaError::create("Statements, assignments and variables are not supported. Use a single expression.");
        }

        return $this->cache[$formula] = $node;
    }

    private function normalize(string $formula): string
    {
        $result = '';
        $length = strlen($formula);
        $quote = null;
        $buffer = '';

        for ($i = 0; $i < $length; $i++) {
            $char = $formula[$i];

            if ($quote !== null) {
                $result .= $char;

                if ($char === '\\' && $i + 1 < $length) {
                    $result .= $formula[++$i];

                    continue;
                }

                if ($char === $quote) {
                    $quote = null;
                }

                continue;
            }

            if ($char === '"' || $char === "'") {
                $result .= $this->normalizeCode($buffer);
                $buffer = '';
                $quote = $char;
                $result .= $char;

                continue;
            }

            $buffer .= $char;
        }

        if ($quote !== null) {
            throw FormulaError::create("Invalid formula syntax: unclosed string.");
        }

        return $result . $this->normalizeCode($buffer);
    }

    private function normalizeCode(string $code): string
    {
        $code = preg_replace('/\[\s*([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z][a-zA-Z0-9_]*)*)\s*\]/', '$1', $code) ?? $code;
        $code = preg_replace('/\bCOUNT\s*\(\s*DISTINCT\s+/i', 'COUNT_DISTINCT(', $code) ?? $code;
        $code = preg_replace('/\s+AND\s+/i', ' && ', $code) ?? $code;

        return preg_replace('/\s+OR\s+/i', ' || ', $code) ?? $code;
    }
}
