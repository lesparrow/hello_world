<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Unit\Apple;

use Espo\Modules\WalletPasses\Core\Apple\WebService\StoredPass;
use Espo\Modules\WalletPasses\Core\Apple\WebService\WebServiceHandler;
use PHPUnit\Framework\TestCase;
use WalletPasses\Tests\Support\InMemoryPassStore;

/**
 * Apple Wallet web service endpoints (controller logic behind the EspoCRM route actions).
 */
final class WebServiceHandlerTest extends TestCase
{
    private const TYPE = 'pass.com.example.test';
    private const TOKEN = 'abcdefghijklmnopqrstuvwxyz012345';
    private const DEVICE = 'a1b2c3d4e5f6';
    private const PUSH = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef';

    private InMemoryPassStore $store;
    private WebServiceHandler $handler;

    protected function setUp(): void
    {
        $this->store = new InMemoryPassStore();
        $this->store->add(new StoredPass('id1', 'SER1', self::TOKEN, 1_700_000_000));
        $this->store->add(new StoredPass('id2', 'SER2', 'other-token-other-token-123', 1_800_000_000));
        $this->handler = new WebServiceHandler($this->store, self::TYPE);
    }

    private function auth(string $token = self::TOKEN): string
    {
        return 'ApplePass ' . $token;
    }

    public function testGetPassRequiresValidToken(): void
    {
        $this->assertSame(401, $this->handler->getLatestPass(self::TYPE, 'SER1', null, null)->status);
        $this->assertSame(401, $this->handler->getLatestPass(self::TYPE, 'SER1', 'Bearer x', null)->status);
        $this->assertSame(401, $this->handler->getLatestPass(self::TYPE, 'SER1', $this->auth('nope'), null)->status);
        $this->assertSame(401, $this->handler->getLatestPass(self::TYPE, 'UNKNOWN', $this->auth(), null)->status);
        $this->assertCount(4, $this->store->unauthorized);
    }

    public function testGetPassReturnsPkpass(): void
    {
        $result = $this->handler->getLatestPass(self::TYPE, 'SER1', $this->auth(), null);

        $this->assertSame(200, $result->status);
        $this->assertSame('PKPASS:SER1', $result->body);
        $this->assertSame('application/vnd.apple.pkpass', $result->headers['Content-Type']);
        $this->assertSame(gmdate('D, d M Y H:i:s', 1_700_000_000) . ' GMT', $result->headers['Last-Modified']);
    }

    public function testGetPassNotModified(): void
    {
        $since = gmdate('D, d M Y H:i:s', 1_700_000_100) . ' GMT';

        $this->assertSame(304, $this->handler->getLatestPass(self::TYPE, 'SER1', $this->auth(), $since)->status);
    }

    public function testWrongPassTypeAndBadSerial(): void
    {
        $this->assertSame(404, $this->handler->getLatestPass('pass.other', 'SER1', $this->auth(), null)->status);
        $this->assertSame(400, $this->handler->getLatestPass(self::TYPE, '../etc', $this->auth(), null)->status);
    }

    public function testRegisterDevice(): void
    {
        $body = json_encode(['pushToken' => self::PUSH]);

        $first = $this->handler->registerDevice(self::DEVICE, self::TYPE, 'SER1', $this->auth(), $body);
        $second = $this->handler->registerDevice(self::DEVICE, self::TYPE, 'SER1', $this->auth(), $body);

        $this->assertSame(201, $first->status);
        $this->assertSame(200, $second->status);
        $this->assertSame(self::PUSH, $this->store->registrations[self::DEVICE]['SER1']);
    }

    public function testRegisterDeviceValidation(): void
    {
        $register = fn (string $device, string $body) =>
            $this->handler->registerDevice($device, self::TYPE, 'SER1', $this->auth(), $body)->status;

        $this->assertSame(400, $register(self::DEVICE, '{}'));
        $this->assertSame(400, $register(self::DEVICE, 'not json'));
        $this->assertSame(400, $register('bad/id', '{}'));
        $this->assertSame(401, $this->handler->registerDevice(
            self::DEVICE,
            self::TYPE,
            'SER1',
            $this->auth('bad'),
            json_encode(['pushToken' => self::PUSH])
        )->status);
        $this->assertSame([], $this->store->registrations);
    }

    public function testSerialNumbers(): void
    {
        $this->assertSame(204, $this->handler->getSerialNumbers(self::DEVICE, self::TYPE, null)->status);

        $this->store->registrations[self::DEVICE] = ['SER1' => self::PUSH, 'SER2' => self::PUSH];

        $all = $this->handler->getSerialNumbers(self::DEVICE, self::TYPE, null);
        $this->assertSame(200, $all->status);
        $data = json_decode($all->body, true);
        $this->assertSame(['SER1', 'SER2'], $data['serialNumbers']);
        $this->assertMatchesRegularExpression('/^\d+$/', $data['lastUpdated']);

        $since = $this->handler->getSerialNumbers(self::DEVICE, self::TYPE, '1750000000');
        $this->assertSame(['SER2'], json_decode($since->body, true)['serialNumbers']);

        $this->assertSame(204, $this->handler->getSerialNumbers(self::DEVICE, self::TYPE, '1900000000')->status);
        $this->assertSame(400, $this->handler->getSerialNumbers(self::DEVICE, self::TYPE, 'yesterday')->status);
        $this->assertSame(404, $this->handler->getSerialNumbers(self::DEVICE, 'pass.other', null)->status);
    }

    public function testUnregister(): void
    {
        $this->store->registrations[self::DEVICE] = ['SER1' => self::PUSH];

        $this->assertSame(401, $this->handler->unregisterDevice(self::DEVICE, self::TYPE, 'SER1', null)->status);
        $result = $this->handler->unregisterDevice(self::DEVICE, self::TYPE, 'SER1', $this->auth());
        $this->assertSame(200, $result->status);
        $this->assertSame([], $this->store->registrations[self::DEVICE]);
    }

    public function testLog(): void
    {
        $this->assertSame(200, $this->handler->log(json_encode(['logs' => ['err 1', 42, 'err 2']]))->status);
        $this->assertSame(['err 1', 'err 2'], $this->store->logs);
        $this->assertSame(400, $this->handler->log('{"foo":1}')->status);
    }

    public function testExtractToken(): void
    {
        $this->assertSame('abc', WebServiceHandler::extractToken('ApplePass abc'));
        $this->assertSame('abc', WebServiceHandler::extractToken('  ApplePass   abc '));
        $this->assertNull(WebServiceHandler::extractToken('Basic abc'));
        $this->assertNull(WebServiceHandler::extractToken('ApplePass'));
        $this->assertNull(WebServiceHandler::extractToken(null));
    }
}
