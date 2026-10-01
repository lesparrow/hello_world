<?php

namespace Espo\Modules\AdvancedCrosstab\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\AdvancedCrosstab\Tools\Export\ExportService;
use Espo\Modules\AdvancedCrosstab\Tools\ReportService;

/**
 * POST AdvancedCrosstab/:id/export or AdvancedCrosstab/action/export
 * {id?, definition?, format: csv|xlsx|pdf|html, title?}
 * → {attachmentId} or {async: true} (the user is notified when the file is ready).
 */
class PostExport implements Action
{
    public function __construct(
        private ReportService $reportService,
        private ExportService $exportService,
    ) {}

    public function process(Request $request): Response
    {
        $body = $request->getParsedBody();

        $id = $request->getRouteParam('id') ?? ($body->id ?? null);
        $definition = $this->reportService->getDefinition($id, $body->definition ?? null);

        $title = mb_substr(trim((string) ($body->title ?? '')), 0, 100) ?: 'Crosstab';

        return ResponseComposer::json(
            $this->exportService->export($definition, (string) ($body->format ?? 'xlsx'), $title)
        );
    }
}
