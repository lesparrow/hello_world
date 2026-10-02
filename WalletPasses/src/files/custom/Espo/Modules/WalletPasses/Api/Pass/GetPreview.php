<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\WalletPasses\Tools\PassDefinitionFactory;

/**
 * GET /WalletPasses/pass/{id}/preview — data for the Wallet-like HTML preview.
 */
class GetPreview implements Action
{
    public function __construct(
        private PassLoader $loader,
        private PassDefinitionFactory $factory,
    ) {
    }

    public function process(Request $request): Response
    {
        $pass = $this->loader->loadPass($request->getRouteParam('id'));
        $template = $this->loader->loadTemplate($pass->getTemplateId());

        return ResponseComposer::json($this->factory->preview($pass, $template));
    }
}
