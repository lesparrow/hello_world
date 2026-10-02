<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\WebService;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Modules\WalletPasses\Api\ResponseFactory;

/**
 * GET /v1/passes/{passTypeIdentifier}/{serialNumber} — latest version of a pass.
 */
class GetPass implements Action
{
    public function __construct(private HandlerFactory $handlerFactory)
    {
    }

    public function process(Request $request): Response
    {
        return ResponseFactory::fromWebServiceResult(
            $this->handlerFactory->create()->getLatestPass(
                (string) $request->getRouteParam('passTypeIdentifier'),
                (string) $request->getRouteParam('serialNumber'),
                $request->getHeader('Authorization'),
                $request->getHeader('If-Modified-Since'),
            )
        );
    }
}
