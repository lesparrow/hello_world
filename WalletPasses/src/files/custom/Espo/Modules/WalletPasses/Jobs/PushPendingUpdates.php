<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Jobs;

use Espo\Core\Job\JobDataLess;
use Espo\Core\Utils\Log;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Tools\UpdateNotifier;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * Fallback job (every 5 minutes): pushes updates of passes still flagged pushPending
 * (template changes, APNs/Google outages, …).
 */
class PushPendingUpdates implements JobDataLess
{
    private const BATCH_SIZE = 200;

    public function __construct(
        private EntityManager $entityManager,
        private UpdateNotifier $notifier,
        private Log $log,
    ) {
    }

    public function run(): void
    {
        $passes = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->where(['pushPending' => true])
            ->order('contentUpdatedAt', 'ASC')
            ->limit(0, self::BATCH_SIZE)
            ->find();

        foreach ($passes as $pass) {
            assert($pass instanceof WalletPass);

            try {
                $this->notifier->notify($pass);
            } catch (Throwable $e) {
                $this->log->error('WalletPasses job: push failed for ' . $pass->getId() . ': ' . $e->getMessage());
            }
        }
    }
}
