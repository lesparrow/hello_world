<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Jobs;

use Espo\Core\Job\JobDataLess;
use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\Modules\WalletPasses\Tools\WalletSettings;
use Espo\ORM\EntityManager;

/**
 * Hourly: sets expired passes to "Expired" (through the ORM, so the hook pushes the change)
 * and purges old WalletPassLog records according to the retention setting.
 */
class ExpirePasses implements JobDataLess
{
    private const BATCH_SIZE = 500;

    public function __construct(
        private EntityManager $entityManager,
        private WalletSettings $settings,
    ) {
    }

    public function run(): void
    {
        $now = DateTimeUtil::getSystemNowString();

        $passes = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->where([
                'status' => WalletPass::STATUS_ACTIVE,
                'expiresAt!=' => null,
                'expiresAt<' => $now,
            ])
            ->limit(0, self::BATCH_SIZE)
            ->find();

        foreach ($passes as $pass) {
            $pass->set('status', WalletPass::STATUS_EXPIRED);
            // Push is deferred to PushPendingUpdates to keep this job short.
            $this->entityManager->saveEntity($pass, ['walletSkipPush' => true]);
        }

        $days = $this->settings->getLogRetentionDays();

        if ($days > 0) {
            $this->entityManager->getQueryExecutor()->execute(
                $this->entityManager->getQueryBuilder()
                    ->delete()
                    ->from(WalletPassLog::ENTITY_TYPE)
                    ->where(['createdAt<' => gmdate(DateTimeUtil::SYSTEM_DATE_TIME_FORMAT, time() - $days * 86400)])
                    ->build()
            );
        }
    }
}
