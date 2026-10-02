<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple\WebService;

/**
 * Framework-agnostic HTTP response produced by the web service handler.
 */
final class WebServiceResult
{
    /**
     * @param array<string, string> $headers
     */
    public function __construct(
        public readonly int $status,
        public readonly string $body = '',
        public readonly array $headers = [],
    ) {
    }

    public static function status(int $status): self
    {
        return new self($status);
    }

    /**
     * @param array<string, mixed> $data
     */
    public static function json(int $status, array $data): self
    {
        return new self($status, (string) json_encode($data, JSON_UNESCAPED_SLASHES), [
            'Content-Type' => 'application/json',
        ]);
    }
}
