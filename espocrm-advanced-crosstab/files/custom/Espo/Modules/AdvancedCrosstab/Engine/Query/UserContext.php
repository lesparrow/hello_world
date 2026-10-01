<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Query;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\Utils\Config;
use Espo\Entities\Preferences;
use Espo\Entities\User;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * Locale settings of the user a crosstab runs for (works in API requests and in background jobs).
 */
class UserContext
{
    private ?DateTimeZone $timeZone = null;
    private ?\Espo\ORM\Entity $preferences = null;
    private bool $preferencesLoaded = false;

    public function __construct(
        private User $user,
        private Config $config,
        private EntityManager $entityManager,
    ) {}

    public function getUser(): User
    {
        return $this->user;
    }

    public function getTimeZone(): DateTimeZone
    {
        if ($this->timeZone) {
            return $this->timeZone;
        }

        $name = $this->getPreference('timeZone') ?: $this->config->get('timeZone') ?: 'UTC';

        try {
            $this->timeZone = new DateTimeZone($name);
        } catch (Throwable) {
            $this->timeZone = new DateTimeZone('UTC');
        }

        return $this->timeZone;
    }

    /**
     * Current UTC offset in hours, for SQL-side time zone conversion of datetime fields.
     */
    public function getOffsetHours(): float
    {
        return $this->getTimeZone()->getOffset(new DateTimeImmutable('now')) / 3600;
    }

    public function getWeekStart(): int
    {
        $value = $this->getPreference('weekStart');

        if ($value === null || $value === -1 || $value === '') {
            $value = $this->config->get('weekStart', 0);
        }

        return (int) $value === 1 ? 1 : 0;
    }

    public function getLanguage(): string
    {
        return $this->getPreference('language') ?: $this->config->get('language') ?: 'en_US';
    }

    private function getPreference(string $name): mixed
    {
        if (!$this->preferencesLoaded) {
            $this->preferencesLoaded = true;

            try {
                $this->preferences = $this->entityManager->getEntityById(Preferences::ENTITY_TYPE, $this->user->getId());
            } catch (Throwable) {
                $this->preferences = null;
            }
        }

        return $this->preferences?->get($name);
    }
}
