<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple\WebService;

/**
 * Persistence port of the Apple web service. Implemented on top of EspoCRM's ORM
 * (Espo\Modules\WalletPasses\Tools\EspoPassStore) and by an in-memory fake in unit tests.
 */
interface PassStore
{
    public function findPass(string $serialNumber): ?StoredPass;

    /**
     * Returns the binary .pkpass for the latest version of the pass.
     */
    public function renderPkpass(StoredPass $pass): string;

    /**
     * @return bool True if a new registration was created, false if it already existed.
     */
    public function registerDevice(StoredPass $pass, string $deviceLibraryIdentifier, string $pushToken): bool;

    /**
     * @return bool False if no registration existed.
     */
    public function unregisterDevice(StoredPass $pass, string $deviceLibraryIdentifier): bool;

    /**
     * @return string[] Serial numbers registered on the device and updated after $since (all when null).
     */
    public function findUpdatedSerialNumbers(string $deviceLibraryIdentifier, ?int $since): array;

    /**
     * @param string[] $messages
     */
    public function logDeviceMessages(array $messages): void;

    /**
     * Records a rejected authentication attempt (for the WalletPassLog / EspoCRM log).
     */
    public function logUnauthorized(string $serialNumber, string $context): void;
}
