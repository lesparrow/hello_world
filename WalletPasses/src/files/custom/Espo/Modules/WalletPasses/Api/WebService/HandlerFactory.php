<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\WebService;

use Espo\Core\Exceptions\NotFound;
use Espo\Modules\WalletPasses\Core\Apple\WebService\WebServiceHandler;
use Espo\Modules\WalletPasses\Tools\EspoPassStore;
use Espo\Modules\WalletPasses\Tools\WalletSettings;

class HandlerFactory
{
    public function __construct(
        private WalletSettings $settings,
        private EspoPassStore $store,
    ) {
    }

    public function create(): WebServiceHandler
    {
        if (!$this->settings->isAppleEnabled() || $this->settings->getPassTypeIdentifier() === '') {
            throw new NotFound();
        }

        return new WebServiceHandler($this->store, $this->settings->getPassTypeIdentifier());
    }
}
