<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Http;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;

final class CurlHttpClient implements HttpClient
{
    public function __construct(private readonly int $timeout = 20)
    {
    }

    public function request(string $method, string $url, array $headers = [], ?string $body = null): HttpResponse
    {
        $handle = curl_init($url);

        $headerLines = [];

        foreach ($headers as $name => $value) {
            $headerLines[] = $name . ': ' . $value;
        }

        curl_setopt_array($handle, [
            CURLOPT_CUSTOMREQUEST => strtoupper($method),
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headerLines,
            CURLOPT_CONNECTTIMEOUT => 10,
            CURLOPT_TIMEOUT => $this->timeout,
            CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
        ]);

        if ($body !== null) {
            curl_setopt($handle, CURLOPT_POSTFIELDS, $body);
        }

        $result = curl_exec($handle);

        if ($result === false) {
            $error = curl_error($handle);
            curl_close($handle);

            throw new WalletException('HTTP request failed: ' . $error);
        }

        $status = (int) curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
        curl_close($handle);

        return new HttpResponse($status, (string) $result);
    }
}
