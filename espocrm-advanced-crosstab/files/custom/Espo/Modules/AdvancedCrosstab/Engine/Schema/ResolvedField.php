<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

use Espo\ORM\Query\Part\Expression;

/**
 * A field path resolved to an SQL-safe ORM expression.
 */
class ResolvedField
{
    public function __construct(
        public readonly string $path,
        public readonly Expression $expression,
        /** Entity type owning the final field. */
        public readonly string $entityType,
        public readonly string $field,
        public readonly string $fieldType,
        /** For link fields: the target entity type (the expression yields an ID). */
        public readonly ?string $foreignEntityType = null,
    ) {}

    public function isDate(): bool
    {
        return in_array($this->fieldType, ['date', 'datetime', 'datetimeOptional'], true);
    }

    public function isDateTime(): bool
    {
        return in_array($this->fieldType, ['datetime', 'datetimeOptional'], true);
    }

    public function isNumeric(): bool
    {
        return in_array($this->fieldType, ['int', 'float', 'currency', 'autoincrement', 'duration', 'enumInt', 'enumFloat'], true);
    }
}
