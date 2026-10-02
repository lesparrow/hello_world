<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Support;

use Espo\Modules\WalletPasses\Core\Apple\WebService\PassStore;
use Espo\Modules\WalletPasses\Core\Apple\WebService\StoredPass;

final class InMemoryPassStore implements PassStore
{
    /** @var array<string, StoredPass> */
    public array $passes = [];
    /** @var array<string, array<string, string>> device => [serial => pushToken] */
    public array $registrations = [];
    /** @var string[] */
    public array $logs = [];
    /** @var string[] */
    public array $unauthorized = [];

    public function add(StoredPass $pass): void
    {
        $this->passes[$pass->serialNumber] = $pass;
    }

    public function findPass(string $serialNumber): ?StoredPass
    {
        return $this->passes[$serialNumber] ?? null;
    }

    public function renderPkpass(StoredPass $pass): string
    {
        return 'PKPASS:' . $pass->serialNumber;
    }

    public function registerDevice(StoredPass $pass, string $deviceLibraryIdentifier, string $pushToken): bool
    {
        $exists = isset($this->registrations[$deviceLibraryIdentifier][$pass->serialNumber]);
        $this->registrations[$deviceLibraryIdentifier][$pass->serialNumber] = $pushToken;

        return !$exists;
    }

    public function unregisterDevice(StoredPass $pass, string $deviceLibraryIdentifier): bool
    {
        $exists = isset($this->registrations[$deviceLibraryIdentifier][$pass->serialNumber]);
        unset($this->registrations[$deviceLibraryIdentifier][$pass->serialNumber]);

        return $exists;
    }

    public function findUpdatedSerialNumbers(string $deviceLibraryIdentifier, ?int $since): array
    {
        $result = [];

        foreach (array_keys($this->registrations[$deviceLibraryIdentifier] ?? []) as $serial) {
            if ($since === null || $this->passes[$serial]->updatedAt > $since) {
                $result[] = $serial;
            }
        }

        return $result;
    }

    public function logDeviceMessages(array $messages): void
    {
        array_push($this->logs, ...$messages);
    }

    public function logUnauthorized(string $serialNumber, string $context): void
    {
        $this->unauthorized[] = $serialNumber . ':' . $context;
    }
}
