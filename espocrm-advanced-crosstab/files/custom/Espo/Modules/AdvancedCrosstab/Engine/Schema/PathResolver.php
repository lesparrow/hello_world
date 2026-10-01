<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\Core\Acl;
use Espo\Core\Acl\Table;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Core\Utils\Metadata;
use Espo\Entities\User;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\Part\Expression;

/**
 * Resolves field paths such as `amount`, `account.industry` or `account.parent.industry`
 * into ORM expressions, using metadata only (no hard-coded entities).
 *
 * Security rules, applied at every level of the path:
 * - the user must have read access to each traversed entity type;
 * - each traversed link and the final field must not be forbidden by field-level ACL;
 * - when the user can't read all records of a traversed entity type, the join is restricted
 *   to the records the user can read (others behave as empty values);
 * - only many-to-one (belongsTo) links are traversed, so joins never multiply rows and
 *   aggregates stay correct.
 */
class PathResolver
{
    public const DIMENSION_TYPES = [
        'varchar', 'enum', 'bool', 'int', 'float', 'currency', 'date', 'datetime', 'datetimeOptional',
        'link', 'personName', 'url', 'autoincrement', 'number', 'text',
    ];

    /** @var array<string, string[]> */
    private array $forbiddenFieldCache = [];

    public function __construct(
        private Metadata $metadata,
        private Acl $acl,
        private User $user,
        private EntityManager $entityManager,
        private SelectBuilderFactory $selectBuilderFactory,
        private Limits $limits,
    ) {}

    /**
     * @throws SchemaError
     */
    public function resolve(string $rootEntityType, string $path, JoinRegistry $registry): ResolvedField
    {
        $segments = explode('.', $path);

        if (count($segments) - 1 > $this->limits->maxPathDepth()) {
            throw new SchemaError("Relationship path is too deep: {$path}");
        }

        $entityType = $rootEntityType;
        $alias = null;
        $linkPath = '';

        foreach (array_slice($segments, 0, -1) as $link) {
            $foreignEntityType = $this->getManyToOneTarget($entityType, $link);

            if (!$foreignEntityType || $this->isFieldForbidden($entityType, $link)) {
                throw SchemaError::invalidField($path);
            }

            if (!$this->acl->checkScope($foreignEntityType, Table::ACTION_READ)) {
                throw new SchemaError("No access to related entity: {$path}");
            }

            $linkPath = $linkPath === '' ? $link : "{$linkPath}.{$link}";

            if (!$registry->has($linkPath)) {
                $newAlias = $registry->nextAlias();

                $registry->add(
                    $linkPath,
                    $foreignEntityType,
                    $this->buildJoinConditions($newAlias, $alias, $link, $foreignEntityType),
                    $newAlias
                );
            }

            $alias = $registry->getAlias($linkPath);
            $entityType = $foreignEntityType;

        }

        $field = end($segments);

        return $this->resolveField($path, $entityType, $field, $alias);
    }

    /**
     * Fields usable from a given entity type. Used for validation messages and by the client.
     */
    public function isFieldForbidden(string $entityType, string $field): bool
    {
        if (!isset($this->forbiddenFieldCache[$entityType])) {
            $this->forbiddenFieldCache[$entityType] = $this->acl->getScopeForbiddenFieldList($entityType);
        }

        return in_array($field, $this->forbiddenFieldCache[$entityType], true);
    }

    public function getManyToOneTarget(string $entityType, string $link): ?string
    {
        $fieldType = $this->metadata->get(['entityDefs', $entityType, 'fields', $link, 'type']);
        $linkDefs = $this->metadata->get(['entityDefs', $entityType, 'links', $link]);

        if (
            $fieldType !== 'link' ||
            !is_array($linkDefs) ||
            ($linkDefs['type'] ?? null) !== 'belongsTo' ||
            $this->metadata->get(['entityDefs', $entityType, 'fields', $link, 'disabled'])
        ) {
            return null;
        }

        $foreignEntityType = $linkDefs['entity'] ?? null;

        if (!$foreignEntityType || !$this->metadata->get(['scopes', $foreignEntityType, 'entity'])) {
            return null;
        }

        return $foreignEntityType;
    }

    /**
     * @return array<string|int, mixed>
     */
    private function buildJoinConditions(
        string $alias,
        ?string $parentAlias,
        string $link,
        string $foreignEntityType
    ): array {

        $foreignKey = $parentAlias ? "{$parentAlias}.{$link}Id" : "{$link}Id";

        $conditions = [
            "{$alias}.id:" => $foreignKey,
            "{$alias}.deleted" => false,
        ];

        // Record-level security on the related entity.
        if ($this->acl->getLevel($foreignEntityType, Table::ACTION_READ) !== Table::LEVEL_ALL) {
            $subQuery = $this->selectBuilderFactory
                ->create()
                ->from($foreignEntityType)
                ->forUser($this->user)
                ->withAccessControlFilter()
                ->buildQueryBuilder()
                ->select(['id'])
                ->build();

            $conditions["{$alias}.id=s"] = $subQuery;
        }

        return $conditions;
    }

    private function resolveField(string $path, string $entityType, string $field, ?string $alias): ResolvedField
    {
        $prefix = $alias ? "{$alias}." : '';

        if ($field === 'id') {
            return new ResolvedField($path, Expression::column($prefix . 'id'), $entityType, 'id', 'id');
        }

        // A link ID attribute, e.g. `accountId`.
        if (
            str_ends_with($field, 'Id') &&
            !$this->metadata->get(['entityDefs', $entityType, 'fields', $field]) &&
            $this->metadata->get(['entityDefs', $entityType, 'fields', substr($field, 0, -2), 'type']) === 'link'
        ) {
            return $this->resolveField($path, $entityType, substr($field, 0, -2), $alias);
        }

        $defs = $this->metadata->get(['entityDefs', $entityType, 'fields', $field]);

        if (
            !is_array($defs) ||
            !empty($defs['disabled']) ||
            !empty($defs['notStorable']) ||
            !in_array($defs['type'] ?? null, self::DIMENSION_TYPES, true) ||
            $this->isFieldForbidden($entityType, $field)
        ) {
            throw SchemaError::invalidField($path);
        }

        $type = $defs['type'];

        if ($type === 'link') {
            $foreignEntityType = $this->getManyToOneTarget($entityType, $field);

            if (!$foreignEntityType) {
                throw SchemaError::invalidField($path);
            }

            return new ResolvedField(
                $path,
                Expression::column("{$prefix}{$field}Id"),
                $entityType,
                $field,
                $type,
                $foreignEntityType
            );
        }

        if ($type === 'personName') {
            // On the main entity the ORM knows how to select a person name; on a joined alias it doesn't.
            $expression = $alias ?
                Expression::trim(
                    Expression::concat(
                        Expression::ifNull(Expression::column("{$prefix}first{$this->ucField($field)}"), ''),
                        ' ',
                        Expression::ifNull(Expression::column("{$prefix}last{$this->ucField($field)}"), ''),
                    )
                ) :
                Expression::column($field);

            return new ResolvedField($path, $expression, $entityType, $field, $type);
        }

        $attributeDefs = $this->entityManager->getDefs()->getEntity($entityType);

        if (!$attributeDefs->hasAttribute($field)) {
            throw SchemaError::invalidField($path);
        }

        $attribute = $attributeDefs->getAttribute($field);

        // Only real columns can be read through a join.
        if ($alias && ($attribute->isNotStorable() || $attribute->getParam('select'))) {
            throw SchemaError::invalidField($path);
        }

        return new ResolvedField($path, Expression::column($prefix . $field), $entityType, $field, $type);
    }

    /**
     * `name` → `Name` (person name sub-fields are `firstName`, `lastName`).
     */
    private function ucField(string $field): string
    {
        return ucfirst($field);
    }
}
