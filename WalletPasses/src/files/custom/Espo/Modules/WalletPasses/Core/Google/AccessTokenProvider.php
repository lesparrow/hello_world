<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use Espo\Modules\WalletPasses\Core\Http\HttpClient;

/**
 * OAuth 2.0 access token for the service account (JWT bearer grant), cached in memory.
 */
class AccessTokenProvider
{
    public const SCOPE = 'https://www.googleapis.com/auth/wallet_object.issuer';

    private ?string $token = null;
    private int $expiresAt = 0;

    public function __construct(
        private readonly ServiceAccount $account,
        private readonly HttpClient $http,
    ) {
    }

    public function getToken(): string
    {
        if ($this->token !== null && time() < $this->expiresAt - 60) {
            return $this->token;
        }

        $now = time();

        $assertion = Jwt::encodeRs256([
            'iss' => $this->account->clientEmail,
            'scope' => self::SCOPE,
            'aud' => $this->account->tokenUri,
            'iat' => $now,
            'exp' => $now + 3600,
        ], $this->account->privateKey, $this->account->privateKeyId);

        $response = $this->http->request('POST', $this->account->tokenUri, [
            'Content-Type' => 'application/x-www-form-urlencoded',
        ], http_build_query([
            'grant_type' => 'urn:ietf:params:oauth:grant-type:jwt-bearer',
            'assertion' => $assertion,
        ]));

        $data = $response->json();

        if (!$response->isSuccess() || empty($data['access_token'])) {
            throw new WalletException(
                'Google OAuth token request failed (' . $response->status . '): ' .
                ($data['error_description'] ?? $data['error'] ?? 'unknown error')
            );
        }

        $this->token = (string) $data['access_token'];
        $this->expiresAt = $now + (int) ($data['expires_in'] ?? 3600);

        return $this->token;
    }
}
