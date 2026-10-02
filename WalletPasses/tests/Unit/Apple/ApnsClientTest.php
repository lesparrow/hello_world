<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Unit\Apple;

use Espo\Modules\WalletPasses\Core\Apple\ApnsClient;
use Espo\Modules\WalletPasses\Core\Apple\AppleConfig;
use Espo\Modules\WalletPasses\Core\Apple\PushResult;
use PHPUnit\Framework\TestCase;
use WalletPasses\Tests\Support\TestCertificates;

final class ApnsClientTest extends TestCase
{
    private function client(string $host): ApnsClient
    {
        $certs = TestCertificates::get();

        return new ApnsClient(new AppleConfig(
            'ABCDE12345',
            TestCertificates::PASS_TYPE_ID,
            $certs['p12'],
            TestCertificates::PASSWORD,
            apnsHost: $host,
        ));
    }

    public function testInvalidTokensAreIgnored(): void
    {
        $this->assertSame([], $this->client('https://127.0.0.1:1')->push(['', 'not-hex', 'abc']));
    }

    public function testTransportErrorIsReported(): void
    {
        // Nothing listens on port 1: the push must fail with an explicit reason, never silently.
        $results = $this->client('https://127.0.0.1:1')->push([str_repeat('ab', 32)]);

        $this->assertCount(1, $results);
        $this->assertFalse($results[0]->isSuccess());
        $this->assertSame(0, $results[0]->statusCode);
        $this->assertNotEmpty($results[0]->reason);
    }

    public function testPushResultClassification(): void
    {
        $this->assertTrue((new PushResult('t', 200))->isSuccess());
        $this->assertTrue((new PushResult('t', 410, 'Unregistered'))->isTokenInvalid());
        $this->assertTrue((new PushResult('t', 400, 'BadDeviceToken'))->isTokenInvalid());
        $this->assertFalse((new PushResult('t', 400, 'BadTopic'))->isTokenInvalid());
        $this->assertFalse((new PushResult('t', 503))->isTokenInvalid());
    }
}
