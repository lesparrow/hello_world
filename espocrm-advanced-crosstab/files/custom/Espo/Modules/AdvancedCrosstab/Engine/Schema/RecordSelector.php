<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

/**
 * Picks ONE record among the records of a to-many relation, per record of the owner, by a user-defined rule.
 *
 *   Entity → Relation 1:N → Record Selector (e.g. LAST by closeDate) → fields
 *
 * The selector is usable as the first segment of field paths (`{name}.field`, `{name}.account.name`). All the fields
 * read through one selector come from the same selected record.
 *
 * - `link`: a one-to-many / many-to-many / children link of the owner, or the name of a custom link;
 * - `from`: path of the owner ('' = data source; a many-to-one path such as `account`);
 * - `rule`: FIRST / MIN / EARLIEST select the lowest value of `orderBy`, LAST / MAX / LATEST the highest value;
 *   EARLIEST / LATEST order by `createdAt` unless `orderBy` is given;
 * - `condition`: optional record formula restricting the candidates (e.g. `status == 'Held'`);
 * - ties are broken by record ID (lowest ID for ascending rules, highest for descending ones); records whose order
 *   value is empty are not candidates.
 */
class RecordSelector
{
    public const RULE_FIRST = 'FIRST';
    public const RULE_LAST = 'LAST';
    public const RULE_MIN = 'MIN';
    public const RULE_MAX = 'MAX';
    public const RULE_EARLIEST = 'EARLIEST';
    public const RULE_LATEST = 'LATEST';

    public const RULE_LIST = [
        self::RULE_FIRST,
        self::RULE_LAST,
        self::RULE_MIN,
        self::RULE_MAX,
        self::RULE_EARLIEST,
        self::RULE_LATEST,
    ];

    public function __construct(
        public readonly string $name,
        public readonly string $from,
        public readonly string $link,
        public readonly string $rule,
        public readonly ?string $orderBy = null,
        public readonly ?string $condition = null,
        public readonly ?string $label = null,
    ) {}

    public function isDescending(): bool
    {
        return in_array($this->rule, [self::RULE_LAST, self::RULE_MAX, self::RULE_LATEST], true);
    }

    public function getDirection(): string
    {
        return $this->isDescending() ? 'DESC' : 'ASC';
    }

    public function getOrderBy(): string
    {
        return $this->orderBy ?? 'createdAt';
    }
}
