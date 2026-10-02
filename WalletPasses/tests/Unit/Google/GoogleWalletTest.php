<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Unit\Google;

use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;
use Espo\Modules\WalletPasses\Core\Google\GoogleConfig;
use Espo\Modules\WalletPasses\Core\Google\Jwt;
use Espo\Modules\WalletPasses\Core\Google\ObjectMapper;
use Espo\Modules\WalletPasses\Core\Google\SaveLinkBuilder;
use Espo\Modules\WalletPasses\Core\Google\ServiceAccount;
use Espo\Modules\WalletPasses\Core\Model\PassStatus;
use Espo\Modules\WalletPasses\Core\Model\PassType;
use PHPUnit\Framework\TestCase;
use WalletPasses\Tests\Support\PassFactory;
use WalletPasses\Tests\Support\TestCertificates;

final class GoogleWalletTest extends TestCase
{
    private GoogleConfig $config;

    protected function setUp(): void
    {
        $this->config = new GoogleConfig(
            '3388000000012345678',
            ServiceAccount::fromJson(TestCertificates::serviceAccountJson()),
            ['https://crm.example.com']
        );
    }

    public function testServiceAccountValidation(): void
    {
        $this->expectException(ConfigurationException::class);

        ServiceAccount::fromJson('{"type":"authorized_user"}');
    }

    public function testSaveLinkJwtIsSignedAndReferencesObject(): void
    {
        $mapper = new ObjectMapper($this->config);
        $url = (new SaveLinkBuilder($this->config, $mapper))->build(PassFactory::create());

        $this->assertStringStartsWith('https://pay.google.com/gp/v/save/', $url);

        $jwt = substr($url, strlen(SaveLinkBuilder::SAVE_URL));
        [$header, $payload, $signature] = explode('.', $jwt);

        $privateKey = openssl_pkey_get_private($this->config->serviceAccount->privateKey);
        $publicKey = openssl_pkey_get_details($privateKey)['key'];
        $valid = openssl_verify(
            "$header.$payload",
            base64_decode(strtr($signature, '-_', '+/')),
            $publicKey,
            OPENSSL_ALGO_SHA256
        );
        $this->assertSame(1, $valid);

        $claims = Jwt::decodePayload($jwt);
        $this->assertSame('google', $claims['aud']);
        $this->assertSame('savetowallet', $claims['typ']);
        $this->assertSame(['https://crm.example.com'], $claims['origins']);
        $this->assertSame('3388000000012345678.SERIAL123', $claims['payload']['loyaltyObjects'][0]['id']);
        $this->assertSame('3388000000012345678.tpl_tpl1', $claims['payload']['loyaltyObjects'][0]['classId']);
    }

    public function testLoyaltyMapping(): void
    {
        $mapper = new ObjectMapper($this->config);
        $pass = PassFactory::create();

        $class = $mapper->buildClass($pass);
        $this->assertSame('ACME', $class['issuerName']);
        $this->assertSame('https://crm.example.com/logo.png', $class['programLogo']['sourceUri']['uri']);
        $this->assertSame('#1E3A5F', $class['hexBackgroundColor']);

        $object = $mapper->buildObject($pass);
        $this->assertSame('ACTIVE', $object['state']);
        $this->assertSame('QR_CODE', $object['barcode']['type']);
        $this->assertSame('SERIAL123', $object['accountId']);
        $this->assertSame('Jane Doe', $object['accountName']);
        $this->assertCount(4, $object['textModulesData']);
        $this->assertSame('2030-01-01T00:00:00+00:00', $object['validTimeInterval']['end']['date']);
    }

    public function testLoyaltyRequiresPublicLogo(): void
    {
        $this->expectException(ConfigurationException::class);

        (new ObjectMapper($this->config))->buildClass(PassFactory::create(['imageUrls' => []]));
    }

    public function testGenericAndStateMapping(): void
    {
        $mapper = new ObjectMapper($this->config);
        $pass = PassFactory::create(['passType' => PassType::Generic, 'status' => PassStatus::Voided]);

        $object = $mapper->buildObject($pass);

        $this->assertSame('genericObject', $mapper->objectResource(PassType::Generic));
        $this->assertSame('offerClass', $mapper->classResource(PassType::Coupon));
        $this->assertSame('INACTIVE', $object['state']);
        $this->assertSame('ACME', $object['cardTitle']['defaultValue']['value']);
        $this->assertSame('120', $object['header']['defaultValue']['value']);
        $this->assertSame('Points', $object['subheader']['defaultValue']['value']);
    }
}
