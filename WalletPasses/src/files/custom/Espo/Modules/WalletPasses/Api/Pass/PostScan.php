<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Acl;
use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Tools\WalletPassService;

/**
 * POST /WalletPasses/scan  {"code": "<barcode value or serial number>"}
 * Called by a scanning app / point of sale to record a scan and check validity.
 */
class PostScan implements Action
{
    public function __construct(
        private Acl $acl,
        private WalletPassService $service,
    ) {
    }

    public function process(Request $request): Response
    {
        if (!$this->acl->checkScope(WalletPass::ENTITY_TYPE, Acl\Table::ACTION_EDIT)) {
            throw new Forbidden();
        }

        $code = $request->getParsedBody()->code ?? null;

        if (!is_string($code) || $code === '' || mb_strlen($code) > 255) {
            throw new BadRequest('"code" is required.');
        }

        $pass = $this->service->registerScan(trim($code));

        if ($pass === null || !$this->acl->checkEntityRead($pass)) {
            throw new NotFound('Unknown pass.');
        }

        return ResponseComposer::json([
            'id' => $pass->getId(),
            'name' => $pass->get('name'),
            'serialNumber' => $pass->getSerialNumber(),
            'holderName' => $pass->get('holderName'),
            'status' => $pass->getStatus(),
            'valid' => $pass->getStatus() === WalletPass::STATUS_ACTIVE,
            'scanCount' => (int) $pass->get('scanCount'),
            'points' => $pass->get('points'),
        ]);
    }
}
