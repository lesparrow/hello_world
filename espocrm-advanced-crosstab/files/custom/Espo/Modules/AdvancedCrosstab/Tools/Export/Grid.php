<?php

namespace Espo\Modules\AdvancedCrosstab\Tools\Export;

use Espo\Modules\AdvancedCrosstab\Engine\Pivot\PivotEngine;

/**
 * Flattens a crosstab result into a 2D grid (header rows + body rows), with the same layout as the UI:
 * hierarchical row labels (one column per row level), parent rows carrying subtotals,
 * column groups followed by their subtotal column, then row totals and the grand total row.
 */
class Grid
{
    /** @var array<int, array<int, array{text: string, span: int}>> */
    public array $header = [];

    /** @var array<int, array{labels: string[], values: array<int, int|float|null>, level: int, total: bool}> */
    public array $body = [];

    /** @var array<int, array{format: array, variant: string, compareMode: string}> */
    public array $valueFormats = [];

    public int $labelColumnCount = 1;

    public static function fromResult(array $result, string $totalLabel): self
    {
        $grid = new self();

        $valueColumns = $result['valueColumns'];
        $measures = [];

        foreach ($result['measures'] as $measure) {
            $measures[$measure['key']] = $measure;
        }

        $rowDimensions = $result['rowDimensions'];
        $columnDimensions = $result['columnDimensions'];
        $R = count($rowDimensions);
        $C = count($columnDimensions);
        $options = $result['options'];

        $grid->labelColumnCount = max(1, $R);

        // Column leaves.
        $leaves = [];

        $walk = function (array $nodes, array $prefix, array $labels) use (&$walk, &$leaves, $options, $C, $totalLabel) {
            foreach ($nodes as $node) {
                $path = array_merge($prefix, [$node['k']]);
                $nodeLabels = array_merge($labels, [$node['l']]);

                if (!empty($node['c'])) {
                    $walk($node['c'], $path, $nodeLabels);

                    if ($options['subtotals']) {
                        $leaves[] = ['path' => $path, 'labels' => array_merge($nodeLabels, [$totalLabel])];
                    }

                    continue;
                }

                $leaves[] = ['path' => $path, 'labels' => $nodeLabels];
            }
        };

        if ($C) {
            $walk($result['columns'], [], []);

            if ($options['rowTotals']) {
                $leaves[] = ['path' => [], 'labels' => [$totalLabel]];
            }
        } else {
            $leaves[] = ['path' => [], 'labels' => []];
        }

        foreach ($leaves as $leaf) {
            foreach ($valueColumns as $column) {
                $measure = $measures[$column['measure']];

                $grid->valueFormats[] = [
                    'format' => $measure['format'],
                    'variant' => $column['variant'],
                    'compareMode' => $measure['compareMode'],
                ];
            }
        }

        // Header rows.
        $rowDimensionLabels = array_map(fn ($d) => $d['label'], $rowDimensions) ?: [''];
        $showMeasureRow = count($valueColumns) > 1 || $C === 0;
        $headerRowCount = $C + ($showMeasureRow ? 1 : 0);

        for ($level = 0; $level < $headerRowCount; $level++) {
            $isMeasureRow = $level === $C;
            $isLast = $level === $headerRowCount - 1;

            $row = [];

            foreach ($rowDimensionLabels as $label) {
                $row[] = ['text' => $isLast ? $label : '', 'span' => 1];
            }

            $previousKey = null;

            foreach ($leaves as $leafIndex => $leaf) {
                foreach ($valueColumns as $column) {
                    if ($isMeasureRow) {
                        $text = $measures[$column['measure']]['label'] . ($column['variant'] === 'compare' ? ' Δ' : '');
                        $key = null;
                    } else {
                        $text = $leaf['labels'][$level] ?? '';
                        $key = json_encode(array_slice($leaf['path'], 0, $level + 1)) . '|' .
                            (count($leaf['labels']) > $level ? count($leaf['labels']) : 0) . '|' . $text;
                    }

                    if ($key !== null && $key === $previousKey) {
                        $row[count($row) - 1]['span']++;

                        continue;
                    }

                    $row[] = ['text' => $text, 'span' => 1];
                    $previousKey = $key;
                }
            }

            $grid->header[] = $row;
        }

        // Body rows.
        $cells = $result['cells'];

        $addRow = function (array $path, array $labels, int $level, bool $total) use (&$grid, $leaves, $cells, $valueColumns) {
            $rowId = PivotEngine::id($path);
            $values = [];

            foreach ($leaves as $leaf) {
                $columnId = PivotEngine::id($leaf['path']);

                foreach (array_keys($valueColumns) as $index) {
                    $values[] = $cells[$rowId][$columnId][$index] ?? null;
                }
            }

            $grid->body[] = ['labels' => $labels, 'values' => $values, 'level' => $level, 'total' => $total];
        };

        $walkRows = function (array $nodes, array $prefix, int $level) use (&$walkRows, $addRow, $R) {
            foreach ($nodes as $node) {
                $path = array_merge($prefix, [$node['k']]);
                $labels = array_fill(0, $R, '');
                $labels[$level] = $node['l'] . (isset($node['r']) ? " (#{$node['r']})" : '');

                $addRow($path, $labels, $level, false);

                if (!empty($node['c'])) {
                    $walkRows($node['c'], $path, $level + 1);
                }
            }
        };

        if ($R) {
            $walkRows($result['rows'], [], 0);

            if ($options['columnTotals']) {
                $addRow([], array_pad([$totalLabel], $R, ''), 0, true);
            }
        } else {
            $addRow([], [$totalLabel], 0, true);
        }

        return $grid;
    }
}
