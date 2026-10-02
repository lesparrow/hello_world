<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Model;

/**
 * A single front/back field of a pass, with its value already rendered.
 */
final class PassField
{
    public const SECTION_HEADER = 'header';
    public const SECTION_PRIMARY = 'primary';
    public const SECTION_SECONDARY = 'secondary';
    public const SECTION_AUXILIARY = 'auxiliary';
    public const SECTION_BACK = 'back';

    public const SECTION_LIST = [
        self::SECTION_HEADER,
        self::SECTION_PRIMARY,
        self::SECTION_SECONDARY,
        self::SECTION_AUXILIARY,
        self::SECTION_BACK,
    ];

    public const ALIGNMENT_LIST = ['natural', 'left', 'center', 'right'];

    public function __construct(
        public readonly string $key,
        public readonly string $label,
        public readonly string $value,
        public readonly string $section = self::SECTION_SECONDARY,
        public readonly string $textAlignment = 'natural',
    ) {
    }

    /**
     * Builds a field from a raw (user supplied) array, normalizing invalid values.
     *
     * @param array<string, mixed> $raw
     */
    public static function fromArray(array $raw, string $defaultSection, int $index): self
    {
        $key = preg_replace('/[^A-Za-z0-9_.-]/', '', (string) ($raw['key'] ?? '')) ?: 'field' . $index;
        $section = in_array($raw['section'] ?? null, self::SECTION_LIST, true) ? $raw['section'] : $defaultSection;
        $alignment = in_array($raw['textAlignment'] ?? null, self::ALIGNMENT_LIST, true) ?
            $raw['textAlignment'] : 'natural';

        return new self(
            $key,
            (string) ($raw['label'] ?? ''),
            (string) ($raw['value'] ?? ''),
            $section,
            $alignment,
        );
    }

    public function withValue(string $value): self
    {
        return new self($this->key, $this->label, $value, $this->section, $this->textAlignment);
    }

    public function appleAlignment(): string
    {
        return 'PKTextAlignment' . ucfirst($this->textAlignment);
    }
}
