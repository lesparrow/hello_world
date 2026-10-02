<?php

namespace Espo\Modules\AdvancedCrosstab\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\AdvancedCrosstab\Tools\ReportService;

/**
 * POST AdvancedCrosstab/action/preview {definition, stage: source|filtered, limit}
 * → {count, columns, rows}: ETL-style data preview of a pipeline stage (user's ACL applies).
 */
class PostPreview implements Action
{
    public function __construct(private ReportService $service) {}

    public function process(Request $request): Response
    {
        return ResponseComposer::json($this->service->preview($request->getParsedBody()));
    }
}
