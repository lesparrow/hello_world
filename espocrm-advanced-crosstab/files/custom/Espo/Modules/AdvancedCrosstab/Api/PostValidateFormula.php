<?php

namespace Espo\Modules\AdvancedCrosstab\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\AdvancedCrosstab\Tools\ReportService;

/**
 * POST AdvancedCrosstab/action/validateFormula
 * {entityType, formula, kind: record|condition|aggregate|display, measureKeys?}
 */
class PostValidateFormula implements Action
{
    public function __construct(private ReportService $service) {}

    public function process(Request $request): Response
    {
        return ResponseComposer::json($this->service->validateFormula($request->getParsedBody()));
    }
}
