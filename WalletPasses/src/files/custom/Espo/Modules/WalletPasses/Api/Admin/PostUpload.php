<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Admin;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Modules\WalletPasses\Core\Apple\Certificate;
use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use Espo\Modules\WalletPasses\Core\Google\ServiceAccount;
use Espo\Modules\WalletPasses\Tools\SecretStore;

/**
 * POST /WalletPasses/settings/upload/{kind}
 * body: {"contents": "<base64>", "password": "…"} or {"delete": true}
 * kind: appleP12 | appleWwdr | googleServiceAccount
 */
class PostUpload implements Action
{
    private const MAX_SIZE = 64 * 1024;

    public function __construct(
        private AdminGuard $guard,
        private SecretStore $store,
    ) {
    }

    public function process(Request $request): Response
    {
        $this->guard->check();

        $kind = (string) $request->getRouteParam('kind');
        $body = $request->getParsedBody();

        $names = [
            'appleP12' => [SecretStore::APPLE_P12, SecretStore::APPLE_P12_PASSWORD],
            'appleWwdr' => [SecretStore::APPLE_WWDR],
            'googleServiceAccount' => [SecretStore::GOOGLE_SERVICE_ACCOUNT],
        ];

        if (!isset($names[$kind])) {
            throw new BadRequest('Unknown credential kind.');
        }

        if (!empty($body->delete)) {
            foreach ($names[$kind] as $name) {
                $this->store->delete($name);
            }

            return ResponseComposer::json(['success' => true]);
        }

        $contents = is_string($body->contents ?? null) ? base64_decode($body->contents, true) : false;

        if ($contents === false || $contents === '' || strlen($contents) > self::MAX_SIZE) {
            throw new BadRequest('Invalid or too large file.');
        }

        try {
            match ($kind) {
                'appleP12' => $this->storeP12($contents, is_string($body->password ?? null) ? $body->password : ''),
                'appleWwdr' => $this->store->set(SecretStore::APPLE_WWDR, Certificate::toPem($contents)),
                'googleServiceAccount' => $this->storeServiceAccount($contents),
            };
        } catch (WalletException $e) {
            throw new BadRequest($e->getMessage());
        }

        return ResponseComposer::json(['success' => true]);
    }

    /**
     * Validates the .p12 and re-exports it with modern encryption (AES), so OpenSSL 3
     * never needs the "legacy" provider at runtime.
     */
    private function storeP12(string $contents, string $password): void
    {
        $pair = Certificate::readP12($contents, $password);

        $key = openssl_pkey_get_private($pair['pkey'], $password);

        if ($key === false || !openssl_x509_check_private_key($pair['cert'], $key)) {
            throw new WalletException('The private key does not match the certificate.');
        }

        if (!openssl_pkcs12_export($pair['cert'], $normalized, $key, $password)) {
            throw new WalletException('Unable to re-export the .p12 certificate.');
        }

        $this->store->set(SecretStore::APPLE_P12, $normalized);
        $this->store->set(SecretStore::APPLE_P12_PASSWORD, $password);
    }

    private function storeServiceAccount(string $contents): void
    {
        ServiceAccount::fromJson($contents);

        $this->store->set(SecretStore::GOOGLE_SERVICE_ACCOUNT, $contents);
    }
}
