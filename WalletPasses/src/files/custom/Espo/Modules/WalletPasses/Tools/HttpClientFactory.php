<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Modules\WalletPasses\Core\Http\CurlHttpClient;
use Espo\Modules\WalletPasses\Core\Http\HttpClient;

/**
 * Indirection allowing the HTTP client to be replaced (e.g. by a proxy-aware implementation).
 */
class HttpClientFactory
{
    public function create(): HttpClient
    {
        return new CurlHttpClient();
    }
}
