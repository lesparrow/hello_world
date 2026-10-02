<?php

namespace Espo\Modules\AdvancedCrosstab\Tools\Export;

/**
 * Formats measure values as text (CSV, PDF) and provides spreadsheet number formats (XLSX),
 * following the same rules as the UI.
 */
class ValueFormatter
{
    public function __construct(
        private string $thousandSeparator = ',',
        private string $decimalMark = '.',
        private ?string $defaultCurrency = null,
    ) {}

    public function format(int|float|null $value, array $format, string $variant = 'value', string $compareMode = 'percent'): string
    {
        if ($value === null) {
            return '';
        }

        if ($variant === 'compare') {
            if ($compareMode === 'percent') {
                return ($value > 0 ? '+' : '') . $this->number($value, 1) . ' %';
            }

            return ($value > 0 ? '+' : '') . $this->format($value, $format);
        }

        $type = $format['type'] ?? 'number';
        $decimals = $format['decimals'] ?? null;

        $text = match ($type) {
            'integer' => $this->number($value, 0),
            'decimal' => $this->number($value, $decimals ?? 2),
            'percent' => $this->number($value, $decimals ?? 1) . ' %',
            'currency' => $this->number($value, $decimals ?? 2) . ' ' . ($format['currency'] ?? $this->defaultCurrency ?? ''),
            'duration' => self::duration((int) round($value)),
            'date' => is_numeric($value) && $value > 100000 ? gmdate('Y-m-d', (int) $value) : (string) $value,
            default => $this->number($value, $decimals ?? (floor($value) == $value ? 0 : 2)),
        };

        return ($format['prefix'] ?? '') . trim($text) . ($format['suffix'] ?? '');
    }

    /**
     * Excel number format code.
     */
    public function excelFormat(array $format, string $variant = 'value', string $compareMode = 'percent'): string
    {
        if ($variant === 'compare' && $compareMode === 'percent') {
            return '+0.0" %";-0.0" %";0.0" %"';
        }

        $type = $format['type'] ?? 'number';
        $decimals = $format['decimals'] ?? match ($type) {
            'integer' => 0,
            'percent' => 1,
            'decimal', 'currency' => 2,
            default => 2,
        };

        $code = '#,##0' . ($decimals > 0 ? '.' . str_repeat('0', $decimals) : '');

        $prefix = self::quote($format['prefix'] ?? '');
        $suffix = self::quote($format['suffix'] ?? '');

        return match ($type) {
            'percent' => $prefix . $code . '" %"' . $suffix,
            'currency' => $prefix . $code . self::quote(' ' . ($format['currency'] ?? $this->defaultCurrency ?? '')) . $suffix,
            'duration' => '[h]:mm',
            default => $prefix . $code . $suffix,
        };
    }

    private function number(int|float $value, int $decimals): string
    {
        return number_format((float) $value, $decimals, $this->decimalMark, $this->thousandSeparator);
    }

    private static function duration(int $seconds): string
    {
        $sign = $seconds < 0 ? '-' : '';
        $seconds = abs($seconds);

        return sprintf('%s%d:%02d', $sign, intdiv($seconds, 3600), intdiv($seconds % 3600, 60));
    }

    private static function quote(string $text): string
    {
        return $text === '' ? '' : '"' . str_replace('"', '', $text) . '"';
    }
}
