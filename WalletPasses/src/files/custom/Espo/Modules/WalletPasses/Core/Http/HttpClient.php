<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Http;

interface HttpClient
{
    /**
     * @param array<string, string> $headers
     */
    public function request(string $method, string $url, array $headers = [], ?string $body = null): HttpResponse;
}
