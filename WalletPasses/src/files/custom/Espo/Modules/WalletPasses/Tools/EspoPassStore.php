<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Modules\WalletPasses\Core\Apple\WebService\PassStore;
use Espo\Modules\WalletPasses\Core\Apple\WebService\StoredPass;
use Espo\Modules\WalletPasses\Entities\WalletDevice;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\ORM\EntityManager;

/**
 * EspoCRM ORM implementation of the Apple web service persistence port.
 */
class EspoPassStore implements PassStore
{
    public function __construct(
        private EntityManager $entityManager,
        private WalletPassService $passService,
        private PassLogger $logger,
    ) {
    }

    public function findPass(string $serialNumber): ?StoredPass
    {
        $pass = $this->findEntity($serialNumber);

        if ($pass === null) {
            return null;
        }

        return new StoredPass(
            (string) $pass->getId(),
            $pass->getSerialNumber(),
            $pass->getAuthenticationToken(),
            $pass->getContentUpdatedTimestamp(),
        );
    }

    public function renderPkpass(StoredPass $pass): string
    {
        $entity = $this->getEntity($pass);

        try {
            $contents = $this->passService->renderPkpass($entity);
        } catch (\Throwable $e) {
            $this->logger->log(WalletPassLog::EVENT_ERROR, $pass->id, 'Pass generation failed: ' . $e->getMessage());

            throw $e;
        }

        $this->logger->log(WalletPassLog::EVENT_DOWNLOADED, $pass->id, 'Fetched by Apple Wallet web service.');

        return $contents;
    }

    public function registerDevice(StoredPass $pass, string $deviceLibraryIdentifier, string $pushToken): bool
    {
        $entity = $this->getEntity($pass);
        $device = $this->findDevice($deviceLibraryIdentifier);

        if ($device === null) {
            $device = $this->entityManager->getNewEntity(WalletDevice::ENTITY_TYPE);
            $device->set([
                'name' => $deviceLibraryIdentifier,
                'deviceLibraryIdentifier' => $deviceLibraryIdentifier,
            ]);
        }

        // The push token can change for a given device: always keep the latest one.
        $device->set('pushToken', $pushToken);
        $this->entityManager->saveEntity($device, ['skipHooks' => true, 'silent' => true]);

        $relation = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->getRelation($entity, 'devices');

        if ($relation->isRelated($device)) {
            return false;
        }

        $relation->relate($device);
        $this->refreshDeviceCount($entity);

        $this->logger->log(
            WalletPassLog::EVENT_DEVICE_REGISTERED,
            $pass->id,
            null,
            $deviceLibraryIdentifier
        );

        return true;
    }

    public function unregisterDevice(StoredPass $pass, string $deviceLibraryIdentifier): bool
    {
        $entity = $this->getEntity($pass);
        $device = $this->findDevice($deviceLibraryIdentifier);

        if ($device === null) {
            return false;
        }

        $relation = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->getRelation($entity, 'devices');

        if (!$relation->isRelated($device)) {
            return false;
        }

        $relation->unrelate($device);
        $this->refreshDeviceCount($entity);

        // Remove orphan devices (no pass left).
        $remaining = $this->entityManager
            ->getRDBRepository(WalletDevice::ENTITY_TYPE)
            ->getRelation($device, 'passes')
            ->count();

        if ($remaining === 0) {
            $this->entityManager->removeEntity($device);
        }

        $this->logger->log(WalletPassLog::EVENT_DEVICE_UNREGISTERED, $pass->id, null, $deviceLibraryIdentifier);

        return true;
    }

    public function findUpdatedSerialNumbers(string $deviceLibraryIdentifier, ?int $since): array
    {
        $device = $this->findDevice($deviceLibraryIdentifier);

        if ($device === null) {
            return [];
        }

        $builder = $this->entityManager
            ->getRDBRepository(WalletDevice::ENTITY_TYPE)
            ->getRelation($device, 'passes')
            ->select(['id', 'serialNumber']);

        if ($since !== null) {
            $builder = $builder->where(['contentUpdatedAt>' => gmdate(DateTimeUtil::SYSTEM_DATE_TIME_FORMAT, $since)]);
        }

        $serials = [];

        foreach ($builder->find() as $pass) {
            $serials[] = (string) $pass->get('serialNumber');
        }

        return $serials;
    }

    public function logDeviceMessages(array $messages): void
    {
        foreach ($messages as $message) {
            $this->logger->log(WalletPassLog::EVENT_DEVICE_LOG, null, $message);
        }
    }

    public function logUnauthorized(string $serialNumber, string $context): void
    {
        $pass = $this->findEntity($serialNumber);

        $this->logger->log(
            WalletPassLog::EVENT_UNAUTHORIZED,
            $pass?->getId(),
            "serial=$serialNumber; $context"
        );
    }

    private function findEntity(string $serialNumber): ?WalletPass
    {
        $pass = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->where(['serialNumber' => $serialNumber])
            ->findOne();

        return $pass instanceof WalletPass ? $pass : null;
    }

    private function getEntity(StoredPass $pass): WalletPass
    {
        $entity = $this->entityManager->getEntityById(WalletPass::ENTITY_TYPE, $pass->id);
        assert($entity instanceof WalletPass);

        return $entity;
    }

    private function findDevice(string $deviceLibraryIdentifier): ?WalletDevice
    {
        $device = $this->entityManager
            ->getRDBRepository(WalletDevice::ENTITY_TYPE)
            ->where(['deviceLibraryIdentifier' => $deviceLibraryIdentifier])
            ->findOne();

        return $device instanceof WalletDevice ? $device : null;
    }

    private function refreshDeviceCount(WalletPass $pass): void
    {
        $count = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->getRelation($pass, 'devices')
            ->count();

        $this->passService->updateSilently($pass, ['deviceCount' => $count]);
    }
}
