define('advanced-crosstab:lib/operators', [], function () {

    const DATE_OPERATORS = [
        'on', 'notOn', 'before', 'after', 'dateBetween',
        'today', 'yesterday', 'tomorrow', 'currentWeek', 'lastWeek', 'nextWeek',
        'currentMonth', 'lastMonth', 'nextMonth', 'currentQuarter', 'lastQuarter', 'nextQuarter',
        'currentYear', 'lastYear', 'nextYear', 'lastXDays', 'nextXDays', 'olderThanXDays', 'afterXDays',
        'isNull', 'isNotNull',
    ];

    const NUMBER_OPERATORS = [
        'equals', 'notEquals', 'greaterThan', 'lessThan', 'greaterThanOrEquals', 'lessThanOrEquals',
        'between', 'isNull', 'isNotNull',
    ];

    const TEXT_OPERATORS = [
        'equals', 'notEquals', 'contains', 'notContains', 'startsWith', 'endsWith', 'in', 'notIn',
        'isEmpty', 'isNotEmpty',
    ];

    const ENUM_OPERATORS = ['in', 'notIn', 'equals', 'notEquals', 'isEmpty', 'isNotEmpty'];
    const LINK_OPERATORS = ['in', 'notIn', 'isNull', 'isNotNull'];
    const BOOL_OPERATORS = ['isTrue', 'isFalse'];

    /** Operators without a value. */
    const NO_VALUE = [
        'isNull', 'isNotNull', 'isEmpty', 'isNotEmpty', 'isTrue', 'isFalse',
        'today', 'yesterday', 'tomorrow', 'currentWeek', 'lastWeek', 'nextWeek',
        'currentMonth', 'lastMonth', 'nextMonth', 'currentQuarter', 'lastQuarter', 'nextQuarter',
        'currentYear', 'lastYear', 'nextYear',
    ];

    /** Operators with two values. */
    const RANGE = ['between', 'dateBetween'];

    /** Operators with a list value. */
    const LIST = ['in', 'notIn'];

    /** Operators with a number of days. */
    const DAYS = ['lastXDays', 'nextXDays', 'olderThanXDays', 'afterXDays'];

    return {
        forType(type) {
            if (['date', 'datetime', 'datetimeOptional'].includes(type)) {
                return DATE_OPERATORS;
            }

            if (['int', 'float', 'currency', 'autoincrement', 'duration', 'enumInt', 'enumFloat'].includes(type)) {
                return NUMBER_OPERATORS;
            }

            if (type === 'enum') {
                return ENUM_OPERATORS;
            }

            if (type === 'link' || type === 'id') {
                return LINK_OPERATORS;
            }

            if (type === 'bool') {
                return BOOL_OPERATORS;
            }

            return TEXT_OPERATORS;
        },

        hasNoValue: operator => NO_VALUE.includes(operator),
        isRange: operator => RANGE.includes(operator),
        isList: operator => LIST.includes(operator),
        isDays: operator => DAYS.includes(operator),
    };
});
