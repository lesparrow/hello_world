<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Http\HttpClient;
use Espo\Modules\WalletPasses\Core\Model\PassDefinition;

/**
 * Façade: synchronises class + object with Google and returns the save link.
 * Patching an existing object is enough for Google to update the pass on every device.
 */
class GoogleWalletService
{
    private ObjectMapper $mapper;
    private WalletApiClient $api;

    public function __construct(private readonly GoogleConfig $config, HttpClient $http)
    {
        $config->assertValid();

        $this->mapper = new ObjectMapper($config);
        $this->api = new WalletApiClient(new AccessTokenProvider($config->serviceAccount, $http), $http);
    }

    /**
     * @return array{classId: string, objectId: string}
     */
    public function sync(PassDefinition $pass): array
    {
        $type = $pass->passType;

        $this->api->upsert($this->mapper->classResource($type), $this->mapper->buildClass($pass));
        $this->api->upsert($this->mapper->objectResource($type), $this->mapper->buildObject($pass));

        return [
            'classId' => $this->mapper->classId($pass),
            'objectId' => $this->mapper->objectId($pass),
        ];
    }

    public function saveLink(PassDefinition $pass): string
    {
        return (new SaveLinkBuilder($this->config, $this->mapper))->build($pass);
    }

    /**
     * Checks credentials end-to-end (OAuth token + an API read). Returns the HTTP-level outcome.
     */
    public function testConnection(): string
    {
        $result = $this->api->get('genericClass', $this->config->issuerId . '.wallet_passes_connectivity_check');

        return $result === null ? 'OK (authenticated, test class not found as expected)' : 'OK';
    }
}
