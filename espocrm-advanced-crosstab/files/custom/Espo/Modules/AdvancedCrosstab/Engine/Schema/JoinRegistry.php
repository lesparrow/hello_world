<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\ORM\Query\SelectBuilder;

/**
 * Keeps the LEFT JOINs needed by one query. Each relation path is joined once,
 * whatever the number of fields, measures and filters that use it.
 */
class JoinRegistry
{
    /** @var array<string, array{alias: string, entityType: string, conditions: array<string|int, mixed>}> */
    private array $joins = [];

    public function __construct(private int $maxJoins) {}

    public function has(string $linkPath): bool
    {
        return isset($this->joins[$linkPath]);
    }

    public function getAlias(string $linkPath): string
    {
        return $this->joins[$linkPath]['alias'];
    }

    /**
     * @param array<string|int, mixed> $conditions
     */
    public function add(string $linkPath, string $entityType, array $conditions, string $alias): void
    {
        if (count($this->joins) >= $this->maxJoins) {
            throw new SchemaError("Too many related entities in one crosstab.");
        }

        $this->joins[$linkPath] = [
            'alias' => $alias,
            'entityType' => $entityType,
            'conditions' => $conditions,
        ];
    }

    public function nextAlias(): string
    {
        return 'acxJ' . (count($this->joins) + 1);
    }

    public function applyTo(SelectBuilder $builder): void
    {
        // Insertion order guarantees that a parent join precedes its children.
        foreach ($this->joins as $join) {
            $builder->leftJoin($join['entityType'], $join['alias'], $join['conditions']);
        }
    }

    public function isEmpty(): bool
    {
        return $this->joins === [];
    }
}
