<?php

namespace Espo\Modules\AdvancedCrosstab\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\AdvancedCrosstab\Tools\ReportService;

/**
 * POST AdvancedCrosstab/:id/run — run a saved crosstab.
 * POST AdvancedCrosstab/action/run — run a saved crosstab ({id}) or an unsaved definition ({definition}).
 */
class PostRun implements Action
{
    public function __construct(private ReportService $service) {}

    public function process(Request $request): Response
    {
        $body = $request->getParsedBody();

        $id = $request->getRouteParam('id') ?? ($body->id ?? null);
        $definition = $this->service->getDefinition($id, $body->definition ?? null);

        return ResponseComposer::json($this->service->run($definition, empty($body->noCache)));
    }
}
