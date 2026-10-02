<?php

namespace Espo\Modules\AdvancedCrosstab\Engine;

use Espo\Core\Utils\Config;
use Espo\Core\Utils\Metadata;

/**
 * Server protection limits. Defaults live in metadata `app.advancedCrosstab.limits`
 * and can be overridden in config (`advancedCrosstabLimits`).
 */
class Limits
{
    private array $values;

    public function __construct(Metadata $metadata, Config $config)
    {
        $this->values = array_merge(
            $metadata->get(['app', 'advancedCrosstab', 'limits']) ?? [],
            (array) ($config->get('advancedCrosstabLimits') ?? [])
        );
    }

    public function get(string $name, int $default): int
    {
        return (int) ($this->values[$name] ?? $default);
    }

    public function maxRowDimensions(): int { return $this->get('maxRowDimensions', 5); }
    public function maxColumnDimensions(): int { return $this->get('maxColumnDimensions', 3); }
    public function maxMeasures(): int { return $this->get('maxMeasures', 25); }
    public function maxCells(): int { return $this->get('maxCells', 50000); }
    public function maxJoins(): int { return $this->get('maxJoins', 30); }
    public function maxPathDepth(): int { return $this->get('maxPathDepth', 3); }
    public function maxFilterItems(): int { return $this->get('maxFilterItems', 100); }
    public function maxFormulaLength(): int { return $this->get('maxFormulaLength', 4000); }
    public function cacheTtl(): int { return $this->get('cacheTtl', 120); }
    public function asyncExportCellThreshold(): int { return $this->get('asyncExportCellThreshold', 20000); }
    public function drillDownMaxSize(): int { return $this->get('drillDownMaxSize', 200); }
}
