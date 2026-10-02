<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\WebService;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Modules\WalletPasses\Api\ResponseFactory;

/**
 * POST /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}
 */
class PostRegistration implements Action
{
    public function __construct(private HandlerFactory $handlerFactory)
    {
    }

    public function process(Request $request): Response
    {
        return ResponseFactory::fromWebServiceResult(
            $this->handlerFactory->create()->registerDevice(
                (string) $request->getRouteParam('deviceLibraryIdentifier'),
                (string) $request->getRouteParam('passTypeIdentifier'),
                (string) $request->getRouteParam('serialNumber'),
                $request->getHeader('Authorization'),
                $request->getBodyContents(),
            )
        );
    }
}
