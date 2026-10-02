<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Hooks\WalletPassTemplate;

use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;

/**
 * A template change flags every non-voided pass for update. The PushPendingUpdates job
 * pushes them in batches (a template may have thousands of passes).
 */
class PropagateChanges
{
    public function __construct(private EntityManager $entityManager)
    {
    }

    /**
     * @param array<string, mixed> $options
     */
    public function afterSave(Entity $entity, array $options): void
    {
        assert($entity instanceof WalletPassTemplate);

        if ($entity->isNew()) {
            return;
        }

        $changed = false;

        foreach (WalletPassTemplate::CONTENT_ATTRIBUTE_LIST as $attribute) {
            if ($entity->isAttributeChanged($attribute)) {
                $changed = true;

                break;
            }
        }

        if (!$changed) {
            return;
        }

        $this->entityManager->getQueryExecutor()->execute(
            $this->entityManager->getQueryBuilder()
                ->update()
                ->in(WalletPass::ENTITY_TYPE)
                ->set([
                    'contentUpdatedAt' => DateTimeUtil::getSystemNowString(),
                    'pushPending' => true,
                ])
                ->where([
                    'templateId' => $entity->getId(),
                    'status!=' => WalletPass::STATUS_VOIDED,
                    'deleted' => false,
                ])
                ->build()
        );
    }
}
