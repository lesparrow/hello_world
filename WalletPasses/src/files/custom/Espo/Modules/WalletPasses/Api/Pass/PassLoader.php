<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\Pass;

use Espo\Core\Acl;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Exceptions\NotFound;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\ORM\EntityManager;

/**
 * Loads records for authenticated actions, enforcing EspoCRM role ACL.
 */
class PassLoader
{
    public function __construct(
        private EntityManager $entityManager,
        private Acl $acl,
    ) {
    }

    public function loadPass(?string $id, string $action = Acl\Table::ACTION_READ): WalletPass
    {
        $pass = $id ? $this->entityManager->getEntityById(WalletPass::ENTITY_TYPE, $id) : null;

        if (!$pass instanceof WalletPass) {
            throw new NotFound();
        }

        if (!$this->acl->checkEntity($pass, $action)) {
            throw new Forbidden();
        }

        return $pass;
    }

    public function loadTemplate(?string $id): WalletPassTemplate
    {
        $template = $id ? $this->entityManager->getEntityById(WalletPassTemplate::ENTITY_TYPE, $id) : null;

        if (!$template instanceof WalletPassTemplate) {
            throw new NotFound();
        }

        if (!$this->acl->checkEntityRead($template)) {
            throw new Forbidden();
        }

        return $template;
    }
}
