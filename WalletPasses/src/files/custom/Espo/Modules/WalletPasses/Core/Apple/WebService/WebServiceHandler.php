<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple\WebService;

use Espo\Modules\WalletPasses\Core\Apple\PkpassGenerator;
use Espo\Modules\WalletPasses\Core\Util\SecureToken;
use Throwable;

/**
 * Apple Wallet web service, protocol v1:
 * https://developer.apple.com/documentation/walletpasses/adding-a-web-service-to-update-passes
 *
 * Every method validates its inputs and returns a WebServiceResult; HTTP plumbing lives in the
 * EspoCRM route actions (Espo\Modules\WalletPasses\Api\WebService\*).
 */
final class WebServiceHandler
{
    private const DEVICE_PATTERN = '/^[A-Za-z0-9]{1,128}$/';
    private const SERIAL_PATTERN = '/^[A-Za-z0-9._-]{1,128}$/';
    private const PUSH_TOKEN_PATTERN = '/^[0-9a-fA-F]{32,200}$/';
    private const MAX_LOG_MESSAGES = 50;
    private const MAX_LOG_LENGTH = 2000;

    public function __construct(
        private readonly PassStore $store,
        private readonly string $passTypeIdentifier,
    ) {
    }

    /**
     * GET /v1/passes/{passTypeIdentifier}/{serialNumber}
     */
    public function getLatestPass(
        string $passTypeIdentifier,
        string $serialNumber,
        ?string $authorization,
        ?string $ifModifiedSince
    ): WebServiceResult {
        $pass = $this->authenticate($passTypeIdentifier, $serialNumber, $authorization, 'getPass');

        if ($pass instanceof WebServiceResult) {
            return $pass;
        }

        if ($ifModifiedSince !== null && $ifModifiedSince !== '') {
            $since = strtotime($ifModifiedSince);

            if ($since !== false && $pass->updatedAt <= $since) {
                return WebServiceResult::status(304);
            }
        }

        try {
            $body = $this->store->renderPkpass($pass);
        } catch (Throwable) {
            return WebServiceResult::status(500);
        }

        return new WebServiceResult(200, $body, [
            'Content-Type' => PkpassGenerator::MIME_TYPE,
            'Last-Modified' => gmdate('D, d M Y H:i:s', $pass->updatedAt) . ' GMT',
            'Cache-Control' => 'no-cache, no-store, must-revalidate',
        ]);
    }

    /**
     * POST /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}
     */
    public function registerDevice(
        string $deviceLibraryIdentifier,
        string $passTypeIdentifier,
        string $serialNumber,
        ?string $authorization,
        ?string $rawBody
    ): WebServiceResult {
        if (!preg_match(self::DEVICE_PATTERN, $deviceLibraryIdentifier)) {
            return WebServiceResult::status(400);
        }

        $pass = $this->authenticate($passTypeIdentifier, $serialNumber, $authorization, 'register');

        if ($pass instanceof WebServiceResult) {
            return $pass;
        }

        $body = json_decode((string) $rawBody, true);
        $pushToken = is_array($body) ? ($body['pushToken'] ?? null) : null;

        if (!is_string($pushToken) || !preg_match(self::PUSH_TOKEN_PATTERN, $pushToken)) {
            return WebServiceResult::status(400);
        }

        $created = $this->store->registerDevice($pass, $deviceLibraryIdentifier, $pushToken);

        return WebServiceResult::status($created ? 201 : 200);
    }

    /**
     * GET /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}?passesUpdatedSince=tag
     * (no authentication token is sent by Wallet for this call).
     */
    public function getSerialNumbers(
        string $deviceLibraryIdentifier,
        string $passTypeIdentifier,
        ?string $passesUpdatedSince
    ): WebServiceResult {
        if (!preg_match(self::DEVICE_PATTERN, $deviceLibraryIdentifier)) {
            return WebServiceResult::status(400);
        }

        if ($passTypeIdentifier !== $this->passTypeIdentifier) {
            return WebServiceResult::status(404);
        }

        $since = null;

        if ($passesUpdatedSince !== null && $passesUpdatedSince !== '') {
            if (!ctype_digit($passesUpdatedSince)) {
                return WebServiceResult::status(400);
            }

            $since = (int) $passesUpdatedSince;
        }

        $serials = $this->store->findUpdatedSerialNumbers($deviceLibraryIdentifier, $since);

        if ($serials === []) {
            return WebServiceResult::status(204);
        }

        return WebServiceResult::json(200, [
            'serialNumbers' => array_values($serials),
            'lastUpdated' => (string) time(),
        ]);
    }

    /**
     * DELETE /v1/devices/{deviceLibraryIdentifier}/registrations/{passTypeIdentifier}/{serialNumber}
     */
    public function unregisterDevice(
        string $deviceLibraryIdentifier,
        string $passTypeIdentifier,
        string $serialNumber,
        ?string $authorization
    ): WebServiceResult {
        if (!preg_match(self::DEVICE_PATTERN, $deviceLibraryIdentifier)) {
            return WebServiceResult::status(400);
        }

        $pass = $this->authenticate($passTypeIdentifier, $serialNumber, $authorization, 'unregister');

        if ($pass instanceof WebServiceResult) {
            return $pass;
        }

        $this->store->unregisterDevice($pass, $deviceLibraryIdentifier);

        return WebServiceResult::status(200);
    }

    /**
     * POST /v1/log  — body: {"logs": ["message", …]}
     */
    public function log(?string $rawBody): WebServiceResult
    {
        $body = json_decode((string) $rawBody, true);
        $logs = is_array($body) ? ($body['logs'] ?? null) : null;

        if (!is_array($logs)) {
            return WebServiceResult::status(400);
        }

        $messages = [];

        foreach (array_slice($logs, 0, self::MAX_LOG_MESSAGES) as $message) {
            if (is_string($message)) {
                $messages[] = mb_substr($message, 0, self::MAX_LOG_LENGTH);
            }
        }

        $this->store->logDeviceMessages($messages);

        return WebServiceResult::status(200);
    }

    /**
     * Parses "Authorization: ApplePass <token>".
     */
    public static function extractToken(?string $authorization): ?string
    {
        if ($authorization === null || !preg_match('/^ApplePass\s+(\S+)$/', trim($authorization), $m)) {
            return null;
        }

        return $m[1];
    }

    private function authenticate(
        string $passTypeIdentifier,
        string $serialNumber,
        ?string $authorization,
        string $context
    ): StoredPass|WebServiceResult {
        if (!preg_match(self::SERIAL_PATTERN, $serialNumber)) {
            return WebServiceResult::status(400);
        }

        $token = self::extractToken($authorization);

        if ($token === null) {
            $this->store->logUnauthorized($serialNumber, $context . ': missing or malformed Authorization header');

            return WebServiceResult::status(401);
        }

        if ($passTypeIdentifier !== $this->passTypeIdentifier) {
            return WebServiceResult::status(404);
        }

        $pass = $this->store->findPass($serialNumber);

        // Same answer for "unknown serial" and "bad token" to avoid serial enumeration.
        if ($pass === null || !SecureToken::equals($pass->authenticationToken, $token)) {
            $this->store->logUnauthorized($serialNumber, $context . ': invalid authentication token');

            return WebServiceResult::status(401);
        }

        return $pass;
    }
}
