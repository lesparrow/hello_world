<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\WalletPasses\Tools\PassDefinitionFactory;

/**
 * GET /WalletPasses/template/{id}/preview — template preview with sample values.
 */
class GetTemplatePreview implements Action
{
    public function __construct(
        private PassLoader $loader,
        private PassDefinitionFactory $factory,
    ) {
    }

    public function process(Request $request): Response
    {
        $template = $this->loader->loadTemplate($request->getRouteParam('id'));

        return ResponseComposer::json($this->factory->preview(null, $template));
    }
}
