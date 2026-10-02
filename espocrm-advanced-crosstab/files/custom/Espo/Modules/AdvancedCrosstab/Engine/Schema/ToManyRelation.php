<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\ORM\Query\Part\Expression;
use Espo\ORM\Query\SelectBuilder;

/**
 * A to-many relation seen from the related entity: its records are those of `entityType` whose `foreignKey`
 * equals `localKey` (an expression on the main query).
 *
 * - one-to-many: foreignKey = the link column on the related entity (`accountId`);
 * - many-to-many: the middle table is joined as `acxMid`, foreignKey = `acxMid.{nearKey}`;
 * - children (parent links): foreignKey = `parentId`, restricted to the owner's parent type;
 * - custom link: foreignKey = the key column of the target.
 */
class ToManyRelation
{
    /**
     * @param ?array{entityType: string, nearKey: string, farKey: string, conditions: array<string, mixed>} $middle
     * @param ?array<string, string> $parentTypeCondition
     */
    public function __construct(
        public readonly string $entityType,
        public readonly Expression $localKey,
        public readonly string $foreignKey,
        public readonly ?array $middle = null,
        public readonly ?array $parentTypeCondition = null,
    ) {}

    /**
     * Restrict a query on the related entity to the records of the relation (middle table, non-empty key, parent type).
     */
    public function applyTo(SelectBuilder $builder): void
    {
        if ($this->middle) {
            $conditions = [
                "acxMid.{$this->middle['farKey']}:" => 'id',
                'acxMid.deleted' => false,
            ];

            foreach ($this->middle['conditions'] as $key => $value) {
                $conditions["acxMid.{$key}"] = $value;
            }

            $builder->join($this->middle['entityType'], 'acxMid', $conditions);
        }

        $builder->where(["{$this->foreignKey}!=" => null]);

        if ($this->parentTypeCondition) {
            $builder->where($this->parentTypeCondition);
        }
    }
}
