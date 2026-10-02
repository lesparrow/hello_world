<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\WebService;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Modules\WalletPasses\Api\ResponseFactory;

/**
 * POST /v1/log — error messages reported by Wallet on the devices.
 */
class PostLog implements Action
{
    public function __construct(private HandlerFactory $handlerFactory)
    {
    }

    public function process(Request $request): Response
    {
        return ResponseFactory::fromWebServiceResult(
            $this->handlerFactory->create()->log($request->getBodyContents())
        );
    }
}
