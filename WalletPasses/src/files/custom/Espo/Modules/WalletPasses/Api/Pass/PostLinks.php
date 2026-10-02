<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\WalletPasses\Tools\WalletPassService;

/**
 * POST /WalletPasses/pass/{id}/links — smart link, Apple link, Google save link and QR code.
 */
class PostLinks implements Action
{
    public function __construct(
        private PassLoader $loader,
        private WalletPassService $service,
    ) {
    }

    public function process(Request $request): Response
    {
        $pass = $this->loader->loadPass($request->getRouteParam('id'));

        return ResponseComposer::json($this->service->getLinks($pass));
    }
}
