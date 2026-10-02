<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\Error;
use Espo\Modules\WalletPasses\Api\ResponseFactory;
use Espo\Modules\WalletPasses\Core\Apple\PkpassGenerator;
use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use Espo\Modules\WalletPasses\Tools\WalletPassService;

/**
 * GET /WalletPasses/pass/{id}/pkpass — authenticated download of the signed pass.
 */
class GetPkpass implements Action
{
    public function __construct(
        private PassLoader $loader,
        private WalletPassService $service,
    ) {
    }

    public function process(Request $request): Response
    {
        $pass = $this->loader->loadPass($request->getRouteParam('id'));

        try {
            $contents = $this->service->renderPkpass($pass);
        } catch (WalletException $e) {
            throw new Error($e->getMessage());
        }

        return ResponseFactory::binary($contents, PkpassGenerator::MIME_TYPE, $this->service->pkpassFileName($pass));
    }
}
