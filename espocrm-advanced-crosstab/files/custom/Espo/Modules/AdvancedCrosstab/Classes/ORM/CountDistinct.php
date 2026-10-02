<?php

namespace Espo\Modules\AdvancedCrosstab\Classes\ORM;

use Espo\ORM\QueryComposer\Part\FunctionConverter;

/**
 * COUNT_DISTINCT:(expression) → COUNT(DISTINCT expression).
 * Arguments are already-composed SQL parts produced by the ORM.
 */
class CountDistinct implements FunctionConverter
{
    public function convert(string ...$argumentList): string
    {
        return 'COUNT(DISTINCT ' . implode(', ', $argumentList) . ')';
    }
}
