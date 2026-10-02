<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Modules\WalletPasses\Core\Apple\ApnsClient;
use Espo\Modules\WalletPasses\Entities\WalletDevice;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * Propagates a pass update: APNs push to every registered Apple device + patch of the Google object.
 * On full success pushPending is cleared; otherwise the PushPendingUpdates job retries later.
 */
class UpdateNotifier
{
    public function __construct(
        private EntityManager $entityManager,
        private WalletSettings $settings,
        private WalletPassService $passService,
        private PassLogger $logger,
    ) {
    }

    public function notify(WalletPass $pass): bool
    {
        $success = true;

        if ($this->settings->isApplePushEnabled()) {
            $success = $this->pushApple($pass) && $success;
        }

        if ($this->settings->isGoogleEnabled() && $pass->getGoogleObjectId()) {
            try {
                $this->passService->syncGoogle($pass);
            } catch (Throwable) {
                $success = false; // already logged by syncGoogle()
            }
        }

        if ($success) {
            $this->passService->updateSilently($pass, ['pushPending' => false]);
        }

        return $success;
    }

    private function pushApple(WalletPass $pass): bool
    {
        /** @var WalletDevice[] $devices */
        $devices = iterator_to_array(
            $this->entityManager
                ->getRDBRepository(WalletPass::ENTITY_TYPE)
                ->getRelation($pass, 'devices')
                ->find()
        );

        $tokens = [];

        foreach ($devices as $device) {
            if ($device->getPushToken()) {
                $tokens[$device->getPushToken()] = $device;
            }
        }

        if ($tokens === []) {
            return true;
        }

        try {
            $results = (new ApnsClient($this->settings->getAppleConfig()))->push(array_keys($tokens));
        } catch (Throwable $e) {
            $this->logger->log(WalletPassLog::EVENT_PUSH_FAILED, $pass->getId(), $e->getMessage());

            return false;
        }

        $allOk = true;
        $sent = 0;

        foreach ($results as $result) {
            $device = $tokens[$result->pushToken] ?? null;

            if ($device === null) {
                continue;
            }

            $device->set([
                'lastPushAt' => DateTimeUtil::getSystemNowString(),
                'lastPushStatus' => $result->statusCode . ($result->reason ? ' ' . $result->reason : ''),
            ]);

            if ($result->isSuccess()) {
                $sent++;
            } elseif ($result->isTokenInvalid()) {
                // Apple says the token is dead: drop the device, it is not a retryable failure.
                $this->entityManager->removeEntity($device);
                $this->logger->log(
                    WalletPassLog::EVENT_DEVICE_UNREGISTERED,
                    $pass->getId(),
                    'APNs rejected token: ' . $result->reason,
                    $device->getDeviceLibraryIdentifier()
                );

                continue;
            } else {
                $allOk = false;
                $this->logger->log(
                    WalletPassLog::EVENT_PUSH_FAILED,
                    $pass->getId(),
                    sprintf('APNs %d %s', $result->statusCode, (string) $result->reason),
                    $device->getDeviceLibraryIdentifier()
                );
            }

            $this->entityManager->saveEntity($device, ['skipHooks' => true, 'silent' => true]);
        }

        if ($sent > 0) {
            $this->logger->log(WalletPassLog::EVENT_PUSH_SENT, $pass->getId(), "APNs push sent to $sent device(s).");
        }

        return $allOk;
    }
}
