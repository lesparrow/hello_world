<?php

namespace Espo\Modules\Crosstab\Api;

use Espo\Core\Acl;
use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Core\Exceptions\Forbidden;
use Espo\Modules\Crosstab\Tools\Crosstab\Params;
use Espo\Modules\Crosstab\Tools\Crosstab\Service;

class PostRun implements Action
{
    public function __construct(
        private Service $service,
        private Acl $acl
    ) {}

    public function process(Request $request): Response
    {
        if (!$this->acl->checkScope('Crosstab')) {
            throw new Forbidden();
        }

        $params = Params::fromRaw($request->getParsedBody());

        return ResponseComposer::json($this->service->run($params));
    }
}
