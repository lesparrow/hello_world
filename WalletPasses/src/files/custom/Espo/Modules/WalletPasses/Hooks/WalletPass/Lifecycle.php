<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Hooks\WalletPass;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Core\Utils\Log;
use Espo\Modules\WalletPasses\Core\Util\SecureToken;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\Modules\WalletPasses\Tools\PassLinks;
use Espo\Modules\WalletPasses\Tools\PassLogger;
use Espo\Modules\WalletPasses\Tools\UpdateNotifier;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * - New pass: serial number, authenticationToken, issue/expiration dates, holder name, smart link.
 * - Content change: contentUpdatedAt + pushPending, then immediate push (APNs + Google);
 *   failures are retried by the PushPendingUpdates job.
 */
class Lifecycle
{
    public static int $order = 10;

    public function __construct(
        private EntityManager $entityManager,
        private PassLinks $links,
        private PassLogger $logger,
        private UpdateNotifier $notifier,
        private Log $log,
    ) {
    }

    /**
     * @param array<string, mixed> $options
     */
    public function beforeSave(Entity $entity, array $options): void
    {
        assert($entity instanceof WalletPass);

        $now = DateTimeUtil::getSystemNowString();

        if ($entity->isNew()) {
            $this->initialize($entity, $now);

            return;
        }

        if (!$entity->getAuthenticationToken()) {
            $entity->set('authenticationToken', SecureToken::authenticationToken());
        }

        foreach (WalletPass::CONTENT_ATTRIBUTE_LIST as $attribute) {
            if ($entity->isAttributeChanged($attribute)) {
                $entity->set('contentUpdatedAt', $now);
                $entity->set('pushPending', true);

                break;
            }
        }
    }

    /**
     * @param array<string, mixed> $options
     */
    public function afterSave(Entity $entity, array $options): void
    {
        assert($entity instanceof WalletPass);

        if ($entity->isNew()) {
            $this->logger->log(WalletPassLog::EVENT_CREATED, $entity->getId(), $entity->getSerialNumber());

            return;
        }

        if (!$entity->isAttributeChanged('contentUpdatedAt') || !$entity->get('pushPending')) {
            return;
        }

        $changed = array_filter(
            WalletPass::CONTENT_ATTRIBUTE_LIST,
            fn (string $a) => $entity->isAttributeChanged($a)
        );

        $this->logger->log(WalletPassLog::EVENT_UPDATED, $entity->getId(), 'Changed: ' . implode(', ', $changed));

        if (!empty($options['walletSkipPush'])) {
            return;
        }

        try {
            $this->notifier->notify($entity);
        } catch (Throwable $e) {
            // Never break the user's save: the cron job will retry.
            $this->log->error('WalletPasses: immediate push failed: ' . $e->getMessage());
        }
    }

    private function initialize(WalletPass $entity, string $now): void
    {
        $entity->set('serialNumber', $this->generateUniqueSerial());
        $entity->set('authenticationToken', SecureToken::authenticationToken());
        $entity->set('issuedAt', $now);
        $entity->set('contentUpdatedAt', $now);
        $entity->set('pushPending', false);
        $entity->set('deviceCount', 0);
        $entity->set('scanCount', 0);

        if (!$entity->get('status')) {
            $entity->set('status', WalletPass::STATUS_ACTIVE);
        }

        $template = $entity->getTemplateId() ?
            $this->entityManager->getEntityById(WalletPassTemplate::ENTITY_TYPE, $entity->getTemplateId()) : null;

        if ($template instanceof WalletPassTemplate && !$entity->get('expiresAt')) {
            $entity->set('expiresAt', $this->computeExpiration($template));
        }

        if (!$entity->get('holderName')) {
            foreach (['contact', 'account', 'lead'] as $link) {
                if ($entity->get($link . 'Name')) {
                    $entity->set('holderName', $entity->get($link . 'Name'));

                    break;
                }
            }
        }

        $entity->set('walletLink', $this->links->smartLink($entity->getSerialNumber()));
        $entity->set('walletQrCodeUrl', $this->links->qrCodeUrl($entity->getSerialNumber()));
    }

    private function computeExpiration(WalletPassTemplate $template): ?string
    {
        $days = (int) $template->get('validityDays');

        if ($days > 0) {
            return (new DateTimeImmutable('now', new DateTimeZone('UTC')))
                ->modify("+$days days")
                ->format(DateTimeUtil::SYSTEM_DATE_TIME_FORMAT);
        }

        $date = $template->get('defaultExpirationDate');

        return $date ? $date . ' 23:59:59' : null;
    }

    private function generateUniqueSerial(): string
    {
        $repository = $this->entityManager->getRDBRepository(WalletPass::ENTITY_TYPE);

        do {
            $serial = SecureToken::serialNumber();
        } while ($repository->where(['serialNumber' => $serial])->findOne() !== null);

        return $serial;
    }
}
