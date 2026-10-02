<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Exceptions\BadRequest;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/**
 * Issues a new pass for a Contact, Account or Lead from a template.
 * Serial number, authentication token, dates and link are filled by the WalletPass hook.
 */
class PassIssuer
{
    public const HOLDER_LINK_MAP = [
        'Contact' => 'contact',
        'Account' => 'account',
        'Lead' => 'lead',
    ];

    public function __construct(private EntityManager $entityManager)
    {
    }

    public function issue(WalletPassTemplate $template, Entity $holder, ?string $assignedUserId = null): WalletPass
    {
        $link = self::HOLDER_LINK_MAP[$holder->getEntityType()] ?? null;

        if ($link === null) {
            throw new BadRequest('Passes can only be issued for Contact, Account or Lead.');
        }

        if (!$template->isActive()) {
            throw new BadRequest('The pass template is inactive.');
        }

        $pass = $this->entityManager->getNewEntity(WalletPass::ENTITY_TYPE);
        assert($pass instanceof WalletPass);

        $holderName = (string) $holder->get('name');

        $pass->set([
            'name' => trim($template->getName() . ' – ' . $holderName, ' –'),
            'templateId' => $template->getId(),
            $link . 'Id' => $holder->getId(),
            'holderName' => $holderName ?: null,
            'assignedUserId' => $assignedUserId ?? $holder->get('assignedUserId'),
            'teamsIds' => $holder->hasAttribute('teamsIds') ? $holder->getLinkMultipleIdList('teams') : [],
        ]);

        $this->entityManager->saveEntity($pass);

        return $pass;
    }
}
