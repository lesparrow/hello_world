<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Util;

/**
 * HMAC signatures for public links (smart link, public images).
 * Links stay valid until the secret is rotated.
 */
final class LinkSigner
{
    public function __construct(private readonly string $secret)
    {
    }

    public function sign(string ...$parts): string
    {
        $raw = hash_hmac('sha256', implode('|', $parts), $this->secret, true);

        return rtrim(strtr(base64_encode(substr($raw, 0, 18)), '+/', '-_'), '=');
    }

    public function verify(string $signature, string ...$parts): bool
    {
        return $signature !== '' && hash_equals($this->sign(...$parts), $signature);
    }
}
