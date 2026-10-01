<?php

namespace Espo\Modules\Crosstab\Tools\Crosstab;

use Espo\Core\Exceptions\BadRequest;
use stdClass;

/**
 * Immutable, validated input of a crosstab request.
 */
class Params
{
    public const AGGREGATES = ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX'];
    public const GRANULARITIES = ['year', 'quarter', 'month', 'day'];

    private function __construct(
        public readonly string $entityType,
        public readonly string $rowField,
        public readonly ?string $rowGranularity,
        public readonly ?string $columnField,
        public readonly ?string $columnGranularity,
        public readonly string $aggregate,
        public readonly ?string $valueField,
        public readonly ?string $primaryFilter,
        public readonly array $where
    ) {}

    public static function fromRaw(stdClass $raw): self
    {
        $entityType = self::name($raw->entityType ?? null, 'entityType', true);
        $rowField = self::name($raw->rowField ?? null, 'rowField', true);
        $columnField = self::name($raw->columnField ?? null, 'columnField');
        $valueField = self::name($raw->valueField ?? null, 'valueField');
        $primaryFilter = self::name($raw->primaryFilter ?? null, 'primaryFilter');

        $aggregate = strtoupper((string) ($raw->aggregate ?? 'COUNT'));

        if (!in_array($aggregate, self::AGGREGATES, true)) {
            throw new BadRequest("Bad aggregate.");
        }

        if ($aggregate !== 'COUNT' && !$valueField) {
            throw new BadRequest("No valueField.");
        }

        if ($columnField === $rowField && ($raw->columnGranularity ?? null) === ($raw->rowGranularity ?? null)) {
            throw new BadRequest("Row and column are the same.");
        }

        $where = $raw->where ?? [];

        if (!is_array($where)) {
            throw new BadRequest("Bad where.");
        }

        return new self(
            $entityType,
            $rowField,
            self::granularity($raw->rowGranularity ?? null),
            $columnField,
            self::granularity($raw->columnGranularity ?? null),
            $aggregate,
            $aggregate === 'COUNT' ? null : $valueField,
            $primaryFilter,
            json_decode(json_encode($where), true)
        );
    }

    private static function name(mixed $value, string $key, bool $required = false): ?string
    {
        if ($value === null || $value === '') {
            if ($required) {
                throw new BadRequest("No {$key}.");
            }

            return null;
        }

        if (!is_string($value) || !preg_match('/^[a-zA-Z][a-zA-Z0-9_]*$/', $value)) {
            throw new BadRequest("Bad {$key}.");
        }

        return $value;
    }

    private static function granularity(mixed $value): ?string
    {
        if ($value === null || $value === '') {
            return null;
        }

        if (!in_array($value, self::GRANULARITIES, true)) {
            throw new BadRequest("Bad granularity.");
        }

        return $value;
    }
}
