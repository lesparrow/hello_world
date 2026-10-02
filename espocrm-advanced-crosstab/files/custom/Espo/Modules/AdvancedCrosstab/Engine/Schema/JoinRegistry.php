<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\ORM\Query\Part\Join;
use Espo\ORM\Query\SelectBuilder;

/**
 * Keeps the LEFT JOINs needed by one query. Each relation path is joined once,
 * whatever the number of fields, measures and filters that use it.
 *
 * Also holds the crosstab's custom links (joins to any entity on any field pair), so that path resolution can
 * use them as the first segment of a path.
 */
class JoinRegistry
{
    /** @var array<string, array{alias: string, entityType: ?string, conditions: array<string|int, mixed>, join: ?Join}> */
    private array $joins = [];

    /** @var array<string, CustomJoin> */
    private array $customJoins = [];

    /** @var array<string, true> Custom joins being resolved (cycle detection). */
    private array $resolving = [];

    private int $aliasCounter = 0;

    public function __construct(private int $maxJoins) {}

    /**
     * @param CustomJoin[] $customJoins
     */
    public function withCustomJoins(array $customJoins): self
    {
        foreach ($customJoins as $customJoin) {
            $this->customJoins[$customJoin->name] = $customJoin;
        }

        return $this;
    }

    public function getCustomJoin(string $name): ?CustomJoin
    {
        return $this->customJoins[$name] ?? null;
    }

    /**
     * @return CustomJoin[]
     */
    public function getCustomJoins(): array
    {
        return array_values($this->customJoins);
    }

    public function startResolving(string $name): void
    {
        if (isset($this->resolving[$name])) {
            throw new SchemaError("Circular custom link: {$name}");
        }

        $this->resolving[$name] = true;
    }

    public function endResolving(string $name): void
    {
        unset($this->resolving[$name]);
    }

    public function has(string $linkPath): bool
    {
        return isset($this->joins[$linkPath]);
    }

    public function getAlias(string $linkPath): string
    {
        return $this->joins[$linkPath]['alias'];
    }

    /**
     * Join an entity table.
     *
     * @param array<string|int, mixed> $conditions
     */
    public function add(string $linkPath, string $entityType, array $conditions, string $alias): void
    {
        $this->checkLimit();

        $this->joins[$linkPath] = [
            'alias' => $alias,
            'entityType' => $entityType,
            'conditions' => $conditions,
            'join' => null,
        ];
    }

    /**
     * Join a prepared Join (e.g. a sub-query).
     */
    public function addJoin(string $key, Join $join, string $alias): void
    {
        $this->checkLimit();

        $this->joins[$key] = [
            'alias' => $alias,
            'entityType' => null,
            'conditions' => [],
            'join' => $join,
        ];
    }

    public function nextAlias(string $prefix = 'acxJ'): string
    {
        return $prefix . (++$this->aliasCounter);
    }

    public function applyTo(SelectBuilder $builder): void
    {
        // Insertion order guarantees that a join precedes the joins that depend on it.
        foreach ($this->joins as $join) {
            if ($join['join']) {
                $builder->leftJoin($join['join']);

                continue;
            }

            $builder->leftJoin($join['entityType'], $join['alias'], $join['conditions']);
        }
    }

    public function isEmpty(): bool
    {
        return $this->joins === [];
    }

    private function checkLimit(): void
    {
        if (count($this->joins) >= $this->maxJoins) {
            throw new SchemaError("Too many related entities in one crosstab.");
        }
    }
}
