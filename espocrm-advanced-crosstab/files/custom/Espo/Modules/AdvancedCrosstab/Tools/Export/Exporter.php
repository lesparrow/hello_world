<?php

namespace Espo\Modules\AdvancedCrosstab\Tools\Export;

use Dompdf\Dompdf;
use Espo\Core\Exceptions\BadRequest;
use PhpOffice\PhpSpreadsheet\Cell\Coordinate;
use PhpOffice\PhpSpreadsheet\Cell\DataType;
use PhpOffice\PhpSpreadsheet\Spreadsheet;
use PhpOffice\PhpSpreadsheet\Style\Alignment;
use PhpOffice\PhpSpreadsheet\Style\Fill;
use PhpOffice\PhpSpreadsheet\Writer\Xlsx;

/**
 * Renders a Grid as CSV, XLSX, HTML (print) or PDF.
 */
class Exporter
{
    public const FORMATS = [
        'csv' => ['mimeType' => 'text/csv', 'extension' => 'csv'],
        'xlsx' => ['mimeType' => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'extension' => 'xlsx'],
        'html' => ['mimeType' => 'text/html', 'extension' => 'html'],
        'pdf' => ['mimeType' => 'application/pdf', 'extension' => 'pdf'],
    ];

    public function render(Grid $grid, string $format, string $title, ValueFormatter $formatter, string $csvDelimiter = ','): string
    {
        return match ($format) {
            'csv' => $this->csv($grid, $formatter, $csvDelimiter),
            'xlsx' => $this->xlsx($grid, $title, $formatter),
            'html' => $this->html($grid, $title, $formatter),
            'pdf' => $this->pdf($grid, $title, $formatter),
            default => throw new BadRequest("Unsupported export format."),
        };
    }

    public static function isPdfAvailable(): bool
    {
        return class_exists(Dompdf::class);
    }

    private function csv(Grid $grid, ValueFormatter $formatter, string $delimiter): string
    {
        $handle = fopen('php://temp', 'r+');

        foreach ($grid->header as $row) {
            $line = [];

            foreach ($row as $cell) {
                $line[] = self::safeText($cell['text']);

                for ($i = 1; $i < $cell['span']; $i++) {
                    $line[] = '';
                }
            }

            fputcsv($handle, $line, $delimiter, '"', '');
        }

        foreach ($grid->body as $row) {
            $line = array_map([self::class, 'safeText'], $row['labels'] ?: ['']);

            foreach ($row['values'] as $i => $value) {
                $meta = $grid->valueFormats[$i];
                $line[] = $formatter->format($value, $meta['format'], $meta['variant'], $meta['compareMode']);
            }

            fputcsv($handle, $line, $delimiter, '"', '');
        }

        rewind($handle);
        $contents = stream_get_contents($handle);
        fclose($handle);

        return "\xEF\xBB\xBF" . $contents;
    }

    private function xlsx(Grid $grid, string $title, ValueFormatter $formatter): string
    {
        $spreadsheet = new Spreadsheet();
        $sheet = $spreadsheet->getActiveSheet();
        $sheet->setTitle(mb_substr(preg_replace('/[\\\\\/?*\[\]:]/', ' ', $title) ?: 'Crosstab', 0, 31));

        $rowNumber = 1;

        foreach ($grid->header as $row) {
            $column = 1;

            foreach ($row as $cell) {
                $coordinate = Coordinate::stringFromColumnIndex($column) . $rowNumber;
                $sheet->setCellValueExplicit($coordinate, $cell['text'], DataType::TYPE_STRING);

                if ($cell['span'] > 1) {
                    $sheet->mergeCells(
                        $coordinate . ':' . Coordinate::stringFromColumnIndex($column + $cell['span'] - 1) . $rowNumber
                    );
                }

                $column += $cell['span'];
            }

            $rowNumber++;
        }

        $headerRows = count($grid->header);
        $lastColumn = Coordinate::stringFromColumnIndex($grid->labelColumnCount + count($grid->valueFormats));

        if ($headerRows) {
            $style = $sheet->getStyle("A1:{$lastColumn}{$headerRows}");
            $style->getFont()->setBold(true);
            $style->getAlignment()->setHorizontal(Alignment::HORIZONTAL_CENTER);
            $style->getFill()->setFillType(Fill::FILL_SOLID)->getStartColor()->setRGB('EEF2F7');
        }

        // One number format per value column.
        $formatCodes = [];

        foreach ($grid->valueFormats as $i => $meta) {
            $formatCodes[$i] = $formatter->excelFormat($meta['format'], $meta['variant'], $meta['compareMode']);
        }

        $firstBodyRow = $rowNumber;

        foreach ($grid->body as $row) {
            foreach ($row['labels'] as $i => $label) {
                $sheet->setCellValueExplicit(
                    Coordinate::stringFromColumnIndex($i + 1) . $rowNumber,
                    $label,
                    DataType::TYPE_STRING
                );
            }

            foreach ($row['values'] as $i => $value) {
                if ($value === null) {
                    continue;
                }

                $meta = $grid->valueFormats[$i];

                // Durations are stored in seconds; Excel durations are fractions of a day.
                if (($meta['format']['type'] ?? null) === 'duration' && $meta['variant'] === 'value') {
                    $value = $value / 86400;
                }

                $sheet->setCellValueExplicit(
                    Coordinate::stringFromColumnIndex($grid->labelColumnCount + $i + 1) . $rowNumber,
                    $value,
                    DataType::TYPE_NUMERIC
                );
            }

            if ($row['total'] || $row['level'] < count($row['labels']) - 1) {
                $sheet->getStyle("A{$rowNumber}:{$lastColumn}{$rowNumber}")->getFont()->setBold(true);
            }

            $rowNumber++;
        }

        $lastBodyRow = $rowNumber - 1;

        if ($lastBodyRow >= $firstBodyRow) {
            foreach ($formatCodes as $i => $code) {
                $letter = Coordinate::stringFromColumnIndex($grid->labelColumnCount + $i + 1);
                $sheet->getStyle("{$letter}{$firstBodyRow}:{$letter}{$lastBodyRow}")
                    ->getNumberFormat()
                    ->setFormatCode($code);
            }
        }

        for ($i = 1; $i <= $grid->labelColumnCount; $i++) {
            $sheet->getColumnDimension(Coordinate::stringFromColumnIndex($i))->setAutoSize(true);
        }

        $sheet->freezePane(Coordinate::stringFromColumnIndex($grid->labelColumnCount + 1) . ($headerRows + 1));

        $file = tempnam(sys_get_temp_dir(), 'acx');

        try {
            (new Xlsx($spreadsheet))->save($file);

            return (string) file_get_contents($file);
        } finally {
            @unlink($file);
            $spreadsheet->disconnectWorksheets();
        }
    }

    public function html(Grid $grid, string $title, ValueFormatter $formatter): string
    {
        $e = fn (string $text) => htmlspecialchars($text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

        $html = '<!doctype html><html><head><meta charset="utf-8"><title>' . $e($title) . '</title><style>
            body { font-family: DejaVu Sans, Arial, sans-serif; font-size: 9px; color: #222; }
            h1 { font-size: 14px; margin: 0 0 8px; }
            table { border-collapse: collapse; }
            th, td { border: 1px solid #ccc; padding: 2px 5px; white-space: nowrap; }
            thead th { background: #eef2f7; }
            td.num { text-align: right; }
            tr.total td, tr.total th, tr.parent td, tr.parent th { font-weight: bold; }
            tbody th { text-align: left; font-weight: normal; }
        </style></head><body><h1>' . $e($title) . '</h1><table><thead>';

        foreach ($grid->header as $row) {
            $html .= '<tr>';

            foreach ($row as $cell) {
                $html .= '<th' . ($cell['span'] > 1 ? ' colspan="' . $cell['span'] . '"' : '') . '>' . $e($cell['text']) . '</th>';
            }

            $html .= '</tr>';
        }

        $html .= '</thead><tbody>';

        foreach ($grid->body as $row) {
            $isParent = $row['level'] < count($row['labels']) - 1;
            $class = $row['total'] ? 'total' : ($isParent ? 'parent' : '');

            $html .= '<tr' . ($class ? " class=\"{$class}\"" : '') . '>';

            foreach ($row['labels'] as $label) {
                $html .= '<th>' . $e($label) . '</th>';
            }

            foreach ($row['values'] as $i => $value) {
                $meta = $grid->valueFormats[$i];
                $html .= '<td class="num">' . $e($formatter->format($value, $meta['format'], $meta['variant'], $meta['compareMode'])) . '</td>';
            }

            $html .= '</tr>';
        }

        return $html . '</tbody></table></body></html>';
    }

    private function pdf(Grid $grid, string $title, ValueFormatter $formatter): string
    {
        if (!self::isPdfAvailable()) {
            throw new BadRequest("PDF export is not available on this installation.");
        }

        $dompdf = new Dompdf(['isRemoteEnabled' => false, 'isPhpEnabled' => false]);
        $dompdf->loadHtml($this->html($grid, $title, $formatter));
        $dompdf->setPaper('A4', count($grid->valueFormats) > 6 ? 'landscape' : 'portrait');
        $dompdf->render();

        return (string) $dompdf->output();
    }

    /**
     * Prevents spreadsheet formula injection from record values used as labels.
     */
    private static function safeText(string $text): string
    {
        return preg_match('/^[=+\-@\t\r]/', $text) ? "'" . $text : $text;
    }
}
