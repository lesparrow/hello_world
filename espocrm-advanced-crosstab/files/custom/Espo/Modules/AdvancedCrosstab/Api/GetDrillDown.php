<?php

namespace Espo\Modules\AdvancedCrosstab\Api;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Select\SearchParams;
use Espo\Modules\AdvancedCrosstab\Tools\ReportService;

/**
 * GET AdvancedCrosstab/action/drillDown?payload={...}&select=&orderBy=&order=&offset=&maxSize=
 *
 * Compatible with EspoCRM collections, so the standard list view can display and paginate the records.
 */
class GetDrillDown implements Action
{
    public function __construct(private ReportService $service) {}

    public function process(Request $request): Response
    {
        $payload = json_decode((string) $request->getQueryParam('payload'));

        if (!$payload instanceof \stdClass) {
            throw new BadRequest("No payload.");
        }

        $select = $request->getQueryParam('attributeSelect') ?? $request->getQueryParam('select');
        $orderBy = $request->getQueryParam('orderBy');
        $order = $request->getQueryParam('order');

        if ($orderBy !== null && !preg_match('/^[a-zA-Z][a-zA-Z0-9]*$/', $orderBy)) {
            throw new BadRequest("Bad orderBy.");
        }

        $searchParams = SearchParams::fromRaw([
            'select' => $select ? explode(',', $select) : null,
            'orderBy' => $orderBy ?: null,
            'order' => $order === 'desc' ? 'desc' : ($orderBy ? 'asc' : null),
            'offset' => max(0, (int) $request->getQueryParam('offset')),
            'maxSize' => max(1, (int) ($request->getQueryParam('maxSize') ?? 20)),
        ]);

        return ResponseComposer::json($this->service->drillDown($payload, $searchParams)->toApiOutput());
    }
}
