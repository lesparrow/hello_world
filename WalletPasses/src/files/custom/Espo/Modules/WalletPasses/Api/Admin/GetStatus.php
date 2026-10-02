<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Admin;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\WalletPasses\Core\Apple\Certificate;
use Espo\Modules\WalletPasses\Core\Google\ServiceAccount;
use Espo\Modules\WalletPasses\Tools\SecretStore;
use Espo\Modules\WalletPasses\Tools\WalletSettings;
use Throwable;

/**
 * GET /WalletPasses/settings/status — non-secret description of the uploaded credentials.
 */
class GetStatus implements Action
{
    public function __construct(
        private AdminGuard $guard,
        private SecretStore $store,
        private WalletSettings $settings,
    ) {
    }

    public function process(Request $request): Response
    {
        $this->guard->check();

        return ResponseComposer::json([
            'appleP12' => $this->describeP12(),
            'appleWwdr' => $this->describeCertificate(SecretStore::APPLE_WWDR),
            'googleServiceAccount' => $this->describeServiceAccount(),
            'webServiceUrl' => $this->settings->getWebServiceUrl(),
            'publicBaseUrl' => $this->settings->getPublicBaseUrl(),
        ]);
    }

    /**
     * @return array<string, mixed>
     */
    private function describeP12(): array
    {
        if (!$this->store->has(SecretStore::APPLE_P12)) {
            return ['uploaded' => false];
        }

        try {
            $pair = Certificate::readP12(
                (string) $this->store->get(SecretStore::APPLE_P12),
                (string) $this->store->get(SecretStore::APPLE_P12_PASSWORD)
            );

            return ['uploaded' => true, 'uploadedAt' => $this->date(SecretStore::APPLE_P12)] +
                $this->info($pair['cert']);
        } catch (Throwable $e) {
            return ['uploaded' => true, 'error' => $e->getMessage()];
        }
    }

    /**
     * @return array<string, mixed>
     */
    private function describeCertificate(string $name): array
    {
        if (!$this->store->has($name)) {
            return ['uploaded' => false];
        }

        try {
            return ['uploaded' => true, 'uploadedAt' => $this->date($name)] +
                $this->info((string) $this->store->get($name));
        } catch (Throwable $e) {
            return ['uploaded' => true, 'error' => $e->getMessage()];
        }
    }

    /**
     * @return array<string, mixed>
     */
    private function describeServiceAccount(): array
    {
        if (!$this->store->has(SecretStore::GOOGLE_SERVICE_ACCOUNT)) {
            return ['uploaded' => false];
        }

        try {
            $account = ServiceAccount::fromJson((string) $this->store->get(SecretStore::GOOGLE_SERVICE_ACCOUNT));

            return [
                'uploaded' => true,
                'uploadedAt' => $this->date(SecretStore::GOOGLE_SERVICE_ACCOUNT),
                'subject' => $account->clientEmail,
            ];
        } catch (Throwable $e) {
            return ['uploaded' => true, 'error' => $e->getMessage()];
        }
    }

    /**
     * @return array<string, mixed>
     */
    private function info(string $pem): array
    {
        $info = Certificate::describe($pem);

        return [
            'subject' => $info['subject'],
            'uid' => $info['uid'],
            'validTo' => $info['validTo']->format('Y-m-d'),
            'expired' => $info['validTo']->getTimestamp() < time(),
        ];
    }

    private function date(string $name): ?string
    {
        $time = $this->store->modifiedAt($name);

        return $time ? gmdate('Y-m-d H:i', $time) : null;
    }
}
