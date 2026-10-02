<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Util;

/**
 * Replaces "{scope.attribute}" placeholders, e.g. "{contact.firstName}" or "{pass.serialNumber}".
 * Unknown placeholders are replaced by an empty string.
 */
final class Placeholder
{
    /**
     * @param array<string, scalar|null> $values Flat map: "contact.firstName" => "John".
     */
    public static function render(string $template, array $values): string
    {
        return (string) preg_replace_callback(
            '/\{([A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*)\}/',
            static fn (array $m): string => (string) ($values[$m[1]] ?? ''),
            $template
        );
    }
}
