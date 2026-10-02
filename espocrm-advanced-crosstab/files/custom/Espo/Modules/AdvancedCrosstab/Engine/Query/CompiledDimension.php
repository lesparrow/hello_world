<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Query;

use Espo\Modules\AdvancedCrosstab\Engine\Definition\Dimension;
use Espo\Modules\AdvancedCrosstab\Engine\Schema\ResolvedField;
use Espo\ORM\Query\Part\Expression;

class CompiledDimension
{
    public function __construct(
        public readonly Dimension $dimension,
        public readonly Expression $expression,
        /** Null for formula dimensions. */
        public readonly ?ResolvedField $field,
        /** Effective granularity for date fields. */
        public readonly ?string $granularity,
        public readonly string $label,
    ) {}

    /**
     * Whether an empty key may mean an empty string (not only NULL).
     */
    public function isTextual(): bool
    {
        if (!$this->field) {
            return true;
        }

        return in_array($this->field->fieldType, ['varchar', 'enum', 'text', 'url', 'personName', 'number'], true);
    }
}
