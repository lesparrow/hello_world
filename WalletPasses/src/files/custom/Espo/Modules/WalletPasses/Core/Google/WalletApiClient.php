<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use Espo\Modules\WalletPasses\Core\Http\HttpClient;

/**
 * Thin REST client for the Google Wallet API (walletobjects/v1).
 *
 * Library choice: the official google/apiclient was deliberately NOT vendored: with its generated
 * services it weighs ~40 MB and pulls guzzle/psr packages that can clash with EspoCRM's own vendor
 * directory. The Wallet API is plain JSON over HTTPS + an RS256 JWT, which this class covers fully.
 */
class WalletApiClient
{
    public const BASE_URL = 'https://walletobjects.googleapis.com/walletobjects/v1/';

    public function __construct(
        private readonly AccessTokenProvider $tokenProvider,
        private readonly HttpClient $http,
    ) {
    }

    /**
     * Inserts the resource or patches it if it already exists.
     *
     * @param string $resource e.g. "genericClass", "loyaltyObject".
     * @param array<string, mixed> $data Must contain "id".
     * @return array<string, mixed>
     */
    public function upsert(string $resource, array $data): array
    {
        $id = (string) ($data['id'] ?? '');
        $existing = $this->call('GET', $resource . '/' . rawurlencode($id), null, [404]);

        if ($existing === null) {
            return (array) $this->call('POST', $resource, $data);
        }

        return (array) $this->call('PATCH', $resource . '/' . rawurlencode($id), $data);
    }

    /**
     * @param array<string, mixed> $data
     * @return array<string, mixed>
     */
    public function patch(string $resource, string $id, array $data): array
    {
        return (array) $this->call('PATCH', $resource . '/' . rawurlencode($id), $data);
    }

    /**
     * Read-only call used by "Test configuration".
     *
     * @return array<string, mixed>|null
     */
    public function get(string $resource, string $id): ?array
    {
        return $this->call('GET', $resource . '/' . rawurlencode($id), null, [404]);
    }

    /**
     * @param array<string, mixed>|null $data
     * @param int[] $nullStatuses Statuses converted to a null result instead of an exception.
     * @return array<string, mixed>|null
     */
    private function call(string $method, string $path, ?array $data = null, array $nullStatuses = []): ?array
    {
        $response = $this->http->request($method, self::BASE_URL . $path, [
            'Authorization' => 'Bearer ' . $this->tokenProvider->getToken(),
            'Content-Type' => 'application/json',
        ], $data !== null ? (string) json_encode($data, JSON_UNESCAPED_SLASHES) : null);

        if (in_array($response->status, $nullStatuses, true)) {
            return null;
        }

        if (!$response->isSuccess()) {
            $error = $response->json()['error']['message'] ?? $response->body;

            throw new WalletException(sprintf(
                'Google Wallet API %s %s failed (%d): %s',
                $method,
                $path,
                $response->status,
                mb_substr((string) $error, 0, 500)
            ));
        }

        return $response->json();
    }
}
