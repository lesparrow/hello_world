<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Schema;

/**
 * A user-defined link to any entity: records of `entityType` whose `foreignField` equals the `localField` of the
 * entity at path `from` ('' = data source). Usable as the first segment of field paths (`{name}.field`).
 *
 * When `foreignField` is `id` the link is many-to-one by nature. Otherwise several target records may match: as a
 * dimension or filter, the first matching record (lowest ID) is used, so rows are never duplicated; aggregated
 * related measures use all matching records.
 */
class CustomJoin
{
    public function __construct(
        public readonly string $name,
        public readonly string $from,
        public readonly string $localField,
        public readonly string $entityType,
        public readonly string $foreignField,
        public readonly ?string $label = null,
    ) {}

    public function isById(): bool
    {
        return $this->foreignField === 'id';
    }

    public function getLocalPath(): string
    {
        return $this->from === '' ? $this->localField : "{$this->from}.{$this->localField}";
    }
}
