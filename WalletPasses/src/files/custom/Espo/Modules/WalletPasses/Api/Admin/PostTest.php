<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Admin;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\WalletPasses\Tools\ConfigTester;

/**
 * POST /WalletPasses/settings/test — "Test configuration" button.
 */
class PostTest implements Action
{
    public function __construct(
        private AdminGuard $guard,
        private ConfigTester $tester,
    ) {
    }

    public function process(Request $request): Response
    {
        $this->guard->check();

        return ResponseComposer::json(['report' => $this->tester->run()]);
    }
}
