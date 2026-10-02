<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Filter;

class FilterOperators
{
    public const VALUE = [
        'equals', 'notEquals', 'in', 'notIn',
        'greaterThan', 'lessThan', 'greaterThanOrEquals', 'lessThanOrEquals', 'between',
        'contains', 'notContains', 'startsWith', 'endsWith',
        'isNull', 'isNotNull', 'isEmpty', 'isNotEmpty', 'isTrue', 'isFalse',
    ];

    public const DATE = [
        'on', 'notOn', 'before', 'after', 'dateBetween',
        'today', 'yesterday', 'tomorrow',
        'currentWeek', 'lastWeek', 'nextWeek',
        'currentMonth', 'lastMonth', 'nextMonth',
        'currentQuarter', 'lastQuarter', 'nextQuarter',
        'currentYear', 'lastYear', 'nextYear',
        'lastXDays', 'nextXDays', 'olderThanXDays', 'afterXDays',
    ];

    public static function isValid(string $operator): bool
    {
        return in_array($operator, self::VALUE, true) || in_array($operator, self::DATE, true);
    }
}
