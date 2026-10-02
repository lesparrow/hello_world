<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Acl\Table;
use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Modules\WalletPasses\Tools\UpdateNotifier;
use Espo\Modules\WalletPasses\Tools\WalletPassService;

/**
 * POST /WalletPasses/pass/{id}/push — force re-generation and push to every registered device.
 */
class PostPush implements Action
{
    public function __construct(
        private PassLoader $loader,
        private WalletPassService $service,
        private UpdateNotifier $notifier,
    ) {
    }

    public function process(Request $request): Response
    {
        $pass = $this->loader->loadPass($request->getRouteParam('id'), Table::ACTION_EDIT);

        $this->service->updateSilently($pass, [
            'contentUpdatedAt' => DateTimeUtil::getSystemNowString(),
            'pushPending' => true,
        ]);

        $success = $this->notifier->notify($pass);

        return ResponseComposer::json([
            'success' => $success,
            'deviceCount' => (int) $pass->get('deviceCount'),
        ]);
    }
}
