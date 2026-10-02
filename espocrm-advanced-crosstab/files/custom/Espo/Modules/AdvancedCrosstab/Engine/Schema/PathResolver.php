<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\Core\Acl;
use Espo\Core\Acl\Table;
use Espo\Core\Select\SelectBuilderFactory;
use Espo\Core\Utils\Metadata;
use Espo\Entities\User;
use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Espo\ORM\EntityManager;
use Espo\ORM\Query\Part\Condition;
use Espo\ORM\Query\Part\Expression;
use Espo\ORM\Query\Part\Join;

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
        'link', 'personName', 'url', 'autoincrement', 'number', 'text', 'duration', 'enumInt', 'enumFloat',
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
        $links = array_slice($segments, 0, -1);

        // A record selector (one record picked among related records) as the first segment.
        if ($links && ($selector = $registry->getSelector($links[0]))) {
            [$alias, $entityType] = $registry->ensureSelector($selector);
            $linkPath = $selector->name;
            array_shift($links);
        } else if ($links && ($customJoin = $registry->getCustomJoin($links[0]))) {
            // A custom link (join to any entity) as the first segment.
            [$alias, $entityType] = $this->ensureCustomJoin($rootEntityType, $customJoin, $registry);
            $linkPath = $customJoin->name;
            array_shift($links);
        }

        foreach ($links as $link) {
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
                $foreignKey = $alias ? "{$alias}.{$link}Id" : "{$link}Id";

                $registry->add(
                    $linkPath,
                    $foreignEntityType,
                    $this->buildJoinConditions($newAlias, $foreignKey, $foreignEntityType, $registry, $linkPath),
                    $newAlias
                );
            }

            $alias = $registry->getAlias($linkPath);
            $entityType = $foreignEntityType;

        }

        $field = end($segments);

        return $this->resolveField($path, $entityType, $field, $alias);
    }

    public const KEY_TYPES = ['id', 'link', 'varchar', 'enum', 'int', 'autoincrement', 'number', 'url'];

    /**
     * Joins the target of a custom link (once) and returns [alias, entityType].
     *
     * - joined on `id`: LEFT JOIN target ON target.id = local key;
     * - joined on another field: LEFT JOIN (SELECT MIN(id) id, field k FROM target WHERE <ACL> GROUP BY field) d
     *   ON d.k = local key, then LEFT JOIN target ON target.id = d.id — at most one target record per row, so
     *   rows are never duplicated (the first matching record is used).
     *
     * @return array{string, string}
     */
    public function ensureCustomJoin(string $rootEntityType, CustomJoin $customJoin, JoinRegistry $registry): array
    {
        $entityType = $customJoin->entityType;

        if ($registry->has($customJoin->name)) {
            return [$registry->getAlias($customJoin->name), $entityType];
        }

        $this->checkCustomJoinTarget($customJoin);

        $registry->startResolving($customJoin->name);

        try {
            $local = $this->resolveKey($rootEntityType, $customJoin->getLocalPath(), $registry);
        } finally {
            $registry->endResolving($customJoin->name);
        }

        $alias = $registry->nextAlias();
        $conditions = ["{$alias}.deleted" => false];

        if ($customJoin->isById()) {
            $conditions["{$alias}.id:"] = $this->restrictToReadable(
                $entityType,
                $local->expression,
                $registry,
                $customJoin->name
            );
        } else {
            $dedupAlias = $registry->nextAlias('acxD');
            $foreignColumn = $this->getKeyAttribute($entityType, $customJoin->foreignField);

            $subQuery = $this->selectBuilderFactory
                ->create()
                ->from($entityType)
                ->forUser($this->user)
                ->withAccessControlFilter()
                ->buildQueryBuilder()
                ->select([
                    [Expression::min(Expression::column('id'))->getValue(), 'id'],
                    [$foreignColumn, 'k'],
                ])
                ->where(["{$foreignColumn}!=" => null])
                ->group([$foreignColumn])
                ->build();

            $registry->addJoin(
                $customJoin->name . '#dedup',
                Join::createWithSubQuery($subQuery, $dedupAlias)->withConditions(
                    Condition::equal(Expression::column("{$dedupAlias}.k"), $local->expression)
                ),
                $dedupAlias
            );

            // The de-duplication sub-query only returns records the user can read.
            $conditions["{$alias}.id:"] = "{$dedupAlias}.id";
        }

        $registry->add($customJoin->name, $entityType, $conditions, $alias);

        return [$alias, $entityType];
    }

    /**
     * Validates the target side of a custom link: entity access, key field type and field ACL.
     */
    public function checkCustomJoinTarget(CustomJoin $customJoin): void
    {
        $entityType = $customJoin->entityType;

        if (
            !$this->metadata->get(['scopes', $entityType, 'entity']) ||
            !$this->acl->checkScope($entityType, Table::ACTION_READ)
        ) {
            throw new SchemaError("No access to entity of custom link: {$customJoin->name}");
        }

        if ($customJoin->foreignField === 'id') {
            return;
        }

        $type = $this->metadata->get(['entityDefs', $entityType, 'fields', $customJoin->foreignField, 'type']);

        if (
            !in_array($type, self::KEY_TYPES, true) ||
            $this->metadata->get(['entityDefs', $entityType, 'fields', $customJoin->foreignField, 'notStorable']) ||
            $this->isFieldForbidden($entityType, $customJoin->foreignField)
        ) {
            throw new SchemaError("Invalid field: {$entityType}.{$customJoin->foreignField}");
        }
    }

    /**
     * A key usable for a join: id, link (its ID), or a plain text/number column.
     */
    public function resolveKey(string $rootEntityType, string $path, JoinRegistry $registry): ResolvedField
    {
        $field = $this->resolve($rootEntityType, $path, $registry);

        if (!in_array($field->fieldType, self::KEY_TYPES, true)) {
            throw new SchemaError("This field can't be used to link entities: {$path}");
        }

        return $field;
    }

    /**
     * Column of a key field on its own table (no alias).
     */
    public function getKeyAttribute(string $entityType, string $field): string
    {
        if ($field === 'id') {
            return 'id';
        }

        $type = $this->metadata->get(['entityDefs', $entityType, 'fields', $field, 'type']);

        return $type === 'link' ? $field . 'Id' : $field;
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

    /**
     * A to-many relation of the entity at path `from` ('' = data source): a one-to-many, many-to-many or children
     * link, or a custom link (from the data source only).
     *
     * @throws SchemaError
     */
    public function resolveToMany(string $rootEntityType, string $from, string $link, JoinRegistry $registry): ToManyRelation
    {
        $customJoin = $registry->getCustomJoin($link);

        if ($customJoin) {
            if ($from !== '') {
                throw new SchemaError("A custom link is always used from the data source.");
            }

            $this->checkCustomJoinTarget($customJoin);

            $target = $customJoin->entityType;

            $relation = new ToManyRelation(
                entityType: $target,
                localKey: $this->resolveKey($rootEntityType, $customJoin->getLocalPath(), $registry)->expression,
                foreignKey: $this->getKeyAttribute($target, $customJoin->foreignField),
            );
        } else {
            $ownerType = $from === '' ?
                $rootEntityType :
                $this->resolve($rootEntityType, $from . '.id', $registry)->entityType;

            if ($this->isFieldForbidden($ownerType, $link) || !$this->metadata->get(['entityDefs', $ownerType, 'links', $link])) {
                throw new SchemaError("Invalid related link: {$link}");
            }

            $relationDefs = $this->entityManager->getDefs()->getEntity($ownerType)->getRelation($link);

            if (!$relationDefs->hasForeignEntityType()) {
                throw new SchemaError("Invalid related link: {$link}");
            }

            $target = $relationDefs->getForeignEntityType();
            $localKey = $this->resolve($rootEntityType, ($from === '' ? '' : $from . '.') . 'id', $registry)->expression;

            if ($relationDefs->isManyToMany()) {
                $relation = new ToManyRelation(
                    entityType: $target,
                    localKey: $localKey,
                    foreignKey: 'acxMid.' . $relationDefs->getMidKey(),
                    middle: [
                        'entityType' => ucfirst($relationDefs->getRelationshipName()),
                        'nearKey' => $relationDefs->getMidKey(),
                        'farKey' => $relationDefs->getForeignMidKey(),
                        'conditions' => $relationDefs->getConditions(),
                    ],
                );
            } else if ($relationDefs->isHasMany() || $relationDefs->isHasChildren()) {
                $relation = new ToManyRelation(
                    entityType: $target,
                    localKey: $localKey,
                    foreignKey: $relationDefs->getForeignKey(),
                    parentTypeCondition: $relationDefs->isHasChildren() ?
                        [($relationDefs->getParam('foreignType') ?? 'parentType') => $ownerType] :
                        null,
                );
            } else {
                throw new SchemaError("Not a one-to-many or many-to-many link: {$link}. Use its fields directly.");
            }
        }

        if (!$this->acl->checkScope($target, Table::ACTION_READ)) {
            throw new SchemaError("No access to related entity: {$link}");
        }

        return $relation;
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
        string $foreignKey,
        string $foreignEntityType,
        JoinRegistry $registry,
        string $linkPath
    ): array {

        return [
            "{$alias}.id:" => $this->restrictToReadable(
                $foreignEntityType,
                Expression::column($foreignKey),
                $registry,
                $linkPath
            ),
            "{$alias}.deleted" => false,
        ];
    }

    /**
     * Record-level security on a joined entity: when the user can't read all its records, the key is first matched
     * against the IDs the user can read,
     *
     *   LEFT JOIN (SELECT id FROM entity WHERE <ACL>) acxA ON acxA.id = key
     *
     * and the entity is then joined on acxA.id (records the user can't read behave as empty values). A derived table
     * is used rather than `IN (sub-query)` in the ON clause, which EspoCRM 8.x does not support in join conditions.
     *
     * @return string The column to join the entity's ID on.
     */
    private function restrictToReadable(
        string $entityType,
        Expression $key,
        JoinRegistry $registry,
        string $linkPath
    ): string {

        if ($this->acl->getLevel($entityType, Table::ACTION_READ) === Table::LEVEL_ALL) {
            return $key->getValue();
        }

        $subQuery = $this->selectBuilderFactory
            ->create()
            ->from($entityType)
            ->forUser($this->user)
            ->withAccessControlFilter()
            ->buildQueryBuilder()
            ->select(['id'])
            ->order([])
            ->build();

        $aclAlias = $registry->nextAlias('acxA');

        $registry->addJoin(
            $linkPath . '#acl',
            Join::createWithSubQuery($subQuery, $aclAlias)
                ->withConditions(Condition::equal(Expression::column("{$aclAlias}.id"), $key)),
            $aclAlias
        );

        return "{$aclAlias}.id";
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
