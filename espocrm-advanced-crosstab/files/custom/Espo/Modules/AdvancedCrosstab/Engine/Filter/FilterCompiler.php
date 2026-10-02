<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Filter;

use DateInterval;
use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Exceptions\BadRequest;
use Espo\Modules\AdvancedCrosstab\Engine\Formula\ExpressionCompiler;
use Espo\Modules\AdvancedCrosstab\Engine\Query\UserContext;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\JoinRegistry;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\PathResolver;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\ResolvedField;
use Espo\ORM\Query\Part\Condition;
use Espo\ORM\Query\Part\WhereItem;

/**
 * Compiles a normalized filter tree into an ORM where item.
 * Values are always bound through ORM comparisons (quoted by the driver), never inlined.
 *
 * Relative date ranges are computed in the user's time zone; datetime fields are compared
 * with UTC boundaries, date fields with plain dates.
 */
class FilterCompiler
{
    public function __construct(
        private PathResolver $pathResolver,
        private ExpressionCompiler $expressionCompiler,
        private UserContext $userContext,
    ) {}

    /**
     * @param array<string, mixed> $node
     */
    public function compile(array $node, string $entityType, JoinRegistry $registry): ?WhereItem
    {
        $type = $node['type'];

        if ($type === 'and' || $type === 'or' || $type === 'not') {
            $items = array_values(array_filter(array_map(
                fn ($item) => $this->compile($item, $entityType, $registry),
                $node['items']
            )));

            if ($items === []) {
                return null;
            }

            $group = $type === 'or' ? Condition::or(...$items) : Condition::and(...$items);

            return $type === 'not' ? Condition::not($group) : $group;
        }

        if ($type === 'formula') {
            return Condition::equal(
                $this->expressionCompiler->compileRecord($node['formula'], $entityType, $registry),
                true
            );
        }

        $field = $this->pathResolver->resolve($entityType, $node['path'], $registry);

        return $this->compileCondition($field, $node['operator'], $node['value']);
    }

    private function compileCondition(ResolvedField $field, string $operator, mixed $value): WhereItem
    {
        $e = $field->expression;

        if (in_array($operator, FilterOperators::DATE, true)) {
            if (!$field->isDate()) {
                throw new BadRequest("Date filter on a non-date field: {$field->path}");
            }

            return $this->compileDateCondition($field, $operator, $value);
        }

        switch ($operator) {
            case 'equals':
                return Condition::equal($e, $this->scalar($value));

            case 'notEquals':
                return Condition::or(Condition::notEqual($e, $this->scalar($value)), Condition::equal($e, null));

            case 'in':
                return Condition::in($e, $this->list($value));

            case 'notIn':
                return Condition::or(Condition::notIn($e, $this->list($value)), Condition::equal($e, null));

            case 'greaterThan':
                return Condition::greater($e, $this->scalar($value));

            case 'lessThan':
                return Condition::less($e, $this->scalar($value));

            case 'greaterThanOrEquals':
                return Condition::greaterOrEqual($e, $this->scalar($value));

            case 'lessThanOrEquals':
                return Condition::lessOrEqual($e, $this->scalar($value));

            case 'between':
                $list = $this->list($value);

                if (count($list) !== 2) {
                    throw new BadRequest("'Between' needs two values.");
                }

                return Condition::and(Condition::greaterOrEqual($e, $list[0]), Condition::lessOrEqual($e, $list[1]));

            case 'contains':
                return Condition::like($e, '%' . $this->text($value) . '%');

            case 'notContains':
                return Condition::or(Condition::notLike($e, '%' . $this->text($value) . '%'), Condition::equal($e, null));

            case 'startsWith':
                return Condition::like($e, $this->text($value) . '%');

            case 'endsWith':
                return Condition::like($e, '%' . $this->text($value));

            case 'isNull':
                return Condition::equal($e, null);

            case 'isNotNull':
                return Condition::notEqual($e, null);

            case 'isEmpty':
                return Condition::or(Condition::equal($e, null), Condition::equal($e, ''));

            case 'isNotEmpty':
                return Condition::and(Condition::notEqual($e, null), Condition::notEqual($e, ''));

            case 'isTrue':
                return Condition::equal($e, true);

            case 'isFalse':
                return Condition::or(Condition::equal($e, false), Condition::equal($e, null));
        }

        throw new BadRequest("Invalid filter operator.");
    }

    private function compileDateCondition(ResolvedField $field, string $operator, mixed $value): WhereItem
    {
        $tz = $this->userContext->getTimeZone();
        $today = new DateTimeImmutable('today', $tz);

        switch ($operator) {
            case 'on':
                $day = $this->date($value, $tz);

                return $this->range($field, $day, $day->modify('+1 day'));

            case 'notOn':
                $day = $this->date($value, $tz);

                return Condition::or(
                    Condition::not($this->range($field, $day, $day->modify('+1 day'))),
                    Condition::equal($field->expression, null)
                );

            case 'before':
                return $this->range($field, null, $this->date($value, $tz));

            case 'after':
                return $this->range($field, $this->date($value, $tz)->modify('+1 day'), null);

            case 'dateBetween':
                $list = $this->list($value);

                if (count($list) !== 2) {
                    throw new BadRequest("'Between' needs two dates.");
                }

                return $this->range($field, $this->date($list[0], $tz), $this->date($list[1], $tz)->modify('+1 day'));

            case 'today':
                return $this->range($field, $today, $today->modify('+1 day'));

            case 'yesterday':
                return $this->range($field, $today->modify('-1 day'), $today);

            case 'tomorrow':
                return $this->range($field, $today->modify('+1 day'), $today->modify('+2 days'));

            case 'currentWeek':
            case 'lastWeek':
            case 'nextWeek':
                $weekStart = $this->userContext->getWeekStart();
                $shift = ((int) $today->format('w') - $weekStart + 7) % 7;
                $start = $today->modify("-{$shift} days");
                $start = match ($operator) {
                    'lastWeek' => $start->modify('-7 days'),
                    'nextWeek' => $start->modify('+7 days'),
                    default => $start,
                };

                return $this->range($field, $start, $start->modify('+7 days'));

            case 'currentMonth':
            case 'lastMonth':
            case 'nextMonth':
                $start = $today->modify('first day of this month');
                $start = match ($operator) {
                    'lastMonth' => $start->modify('-1 month'),
                    'nextMonth' => $start->modify('+1 month'),
                    default => $start,
                };

                return $this->range($field, $start, $start->modify('+1 month'));

            case 'currentQuarter':
            case 'lastQuarter':
            case 'nextQuarter':
                $month = (int) $today->format('n');
                $quarterMonth = intdiv($month - 1, 3) * 3 + 1;
                $start = $today->setDate((int) $today->format('Y'), $quarterMonth, 1);
                $start = match ($operator) {
                    'lastQuarter' => $start->modify('-3 months'),
                    'nextQuarter' => $start->modify('+3 months'),
                    default => $start,
                };

                return $this->range($field, $start, $start->modify('+3 months'));

            case 'currentYear':
            case 'lastYear':
            case 'nextYear':
                $year = (int) $today->format('Y') + match ($operator) {
                    'lastYear' => -1,
                    'nextYear' => 1,
                    default => 0,
                };
                $start = $today->setDate($year, 1, 1);

                return $this->range($field, $start, $start->modify('+1 year'));

            case 'lastXDays':
                return $this->range($field, $today->sub($this->days($value))->modify('+1 day'), $today->modify('+1 day'));

            case 'nextXDays':
                return $this->range($field, $today, $today->add($this->days($value))->modify('+1 day'));

            case 'olderThanXDays':
                return $this->range($field, null, $today->sub($this->days($value)));

            case 'afterXDays':
                return $this->range($field, $today->add($this->days($value))->modify('+1 day'), null);
        }

        throw new BadRequest("Invalid date filter operator.");
    }

    /**
     * Half-open range [from, to) in the user's time zone.
     */
    private function range(ResolvedField $field, ?DateTimeImmutable $from, ?DateTimeImmutable $to): WhereItem
    {
        $items = [];

        if ($from) {
            $items[] = Condition::greaterOrEqual($field->expression, $this->format($field, $from));
        }

        if ($to) {
            $items[] = Condition::less($field->expression, $this->format($field, $to));
        }

        return count($items) === 1 ? $items[0] : Condition::and(...$items);
    }

    private function format(ResolvedField $field, DateTimeImmutable $date): string
    {
        if ($field->isDateTime()) {
            return $date->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s');
        }

        return $date->format('Y-m-d');
    }

    private function date(mixed $value, DateTimeZone $tz): DateTimeImmutable
    {
        if (!is_string($value) || !preg_match('/^\d{4}-\d{2}-\d{2}$/', $value)) {
            throw new BadRequest("Invalid date value.");
        }

        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $value, $tz);

        if (!$date) {
            throw new BadRequest("Invalid date value.");
        }

        return $date;
    }

    private function days(mixed $value): DateInterval
    {
        $days = (int) $value;

        if ($days < 0 || $days > 100000) {
            throw new BadRequest("Invalid number of days.");
        }

        return new DateInterval("P{$days}D");
    }

    private function scalar(mixed $value): string|int|float|bool
    {
        if (!is_scalar($value)) {
            throw new BadRequest("Invalid filter value.");
        }

        return $value;
    }

    private function text(mixed $value): string
    {
        if (!is_scalar($value) || (string) $value === '') {
            throw new BadRequest("Invalid filter value.");
        }

        return (string) $value;
    }

    /**
     * @return array<int, string|int|float|bool>
     */
    private function list(mixed $value): array
    {
        if (!is_array($value)) {
            throw new BadRequest("Invalid filter value.");
        }

        return array_values(array_filter($value, fn ($item) => is_scalar($item)));
    }
}
