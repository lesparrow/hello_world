<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Utils\Log;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * Writes WalletPassLog records and mirrors errors to the EspoCRM log (data/logs).
 */
class PassLogger
{
    private const ERROR_EVENTS = [
        WalletPassLog::EVENT_PUSH_FAILED,
        WalletPassLog::EVENT_GOOGLE_ERROR,
        WalletPassLog::EVENT_ERROR,
    ];

    public function __construct(
        private EntityManager $entityManager,
        private Log $log,
    ) {
    }

    public function log(
        string $event,
        ?string $passId,
        ?string $message = null,
        ?string $deviceLibraryIdentifier = null
    ): void {
        if (in_array($event, self::ERROR_EVENTS, true)) {
            $this->log->error("WalletPasses [$event] pass=" . ($passId ?? '-') . ': ' . $message);
        } elseif ($event === WalletPassLog::EVENT_UNAUTHORIZED) {
            $this->log->warning("WalletPasses [$event] " . $message);
        }

        try {
            $this->entityManager->createEntity(WalletPassLog::ENTITY_TYPE, [
                'event' => $event,
                'passId' => $passId,
                'message' => $message !== null ? mb_substr($message, 0, 5000) : null,
                'deviceLibraryIdentifier' => $deviceLibraryIdentifier,
                'ipAddress' => $this->getClientIp(),
            ], ['skipHooks' => true, 'silent' => true]);
        } catch (Throwable $e) {
            $this->log->error('WalletPasses: unable to write log record: ' . $e->getMessage());
        }
    }

    private function getClientIp(): ?string
    {
        $ip = $_SERVER['REMOTE_ADDR'] ?? null;

        return is_string($ip) && filter_var($ip, FILTER_VALIDATE_IP) ? $ip : null;
    }
}
