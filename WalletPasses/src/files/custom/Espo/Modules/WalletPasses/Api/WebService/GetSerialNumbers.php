<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\WebService;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Modules\WalletPasses\Api\ResponseFactory;

/**
 * GET /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}?passesUpdatedSince=tag
 */
class GetSerialNumbers implements Action
{
    public function __construct(private HandlerFactory $handlerFactory)
    {
    }

    public function process(Request $request): Response
    {
        return ResponseFactory::fromWebServiceResult(
            $this->handlerFactory->create()->getSerialNumbers(
                (string) $request->getRouteParam('deviceLibraryIdentifier'),
                (string) $request->getRouteParam('passTypeIdentifier'),
                $request->getQueryParam('passesUpdatedSince'),
            )
        );
    }
}
