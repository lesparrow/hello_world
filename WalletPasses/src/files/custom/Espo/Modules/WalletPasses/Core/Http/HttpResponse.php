<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Http;

final class HttpResponse
{
    public function __construct(
        public readonly int $status,
        public readonly string $body,
    ) {
    }

    /**
     * @return array<string, mixed>
     */
    public function json(): array
    {
        $data = json_decode($this->body, true);

        return is_array($data) ? $data : [];
    }

    public function isSuccess(): bool
    {
        return $this->status >= 200 && $this->status < 300;
    }
}
