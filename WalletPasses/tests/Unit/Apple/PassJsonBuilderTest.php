<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Unit\Apple;

use Espo\Modules\WalletPasses\Core\Apple\AppleConfig;
use Espo\Modules\WalletPasses\Core\Apple\PassJsonBuilder;
use Espo\Modules\WalletPasses\Core\Model\BarcodeFormat;
use Espo\Modules\WalletPasses\Core\Model\PassStatus;
use PHPUnit\Framework\TestCase;
use WalletPasses\Tests\Support\PassFactory;

final class PassJsonBuilderTest extends TestCase
{
    private function config(?string $webServiceUrl = 'https://crm.example.com/api/v1/WalletService'): AppleConfig
    {
        return new AppleConfig('ABCDE12345', 'pass.com.example.test', 'p12', 'pwd', null, $webServiceUrl);
    }

    public function testBuildsLoyaltyCardAsStoreCard(): void
    {
        $json = (new PassJsonBuilder())->build(PassFactory::create(), $this->config());

        $this->assertSame(1, $json['formatVersion']);
        $this->assertSame('pass.com.example.test', $json['passTypeIdentifier']);
        $this->assertSame('ABCDE12345', $json['teamIdentifier']);
        $this->assertSame('SERIAL123', $json['serialNumber']);
        $this->assertArrayHasKey('storeCard', $json);
        $this->assertSame('rgb(30, 58, 95)', $json['backgroundColor']);
        $this->assertSame('2030-01-01T00:00:00+00:00', $json['expirationDate']);
        $this->assertArrayNotHasKey('voided', $json);
    }

    public function testFieldsAreGroupedAndKeysAreUnique(): void
    {
        $style = (new PassJsonBuilder())->build(PassFactory::create(), $this->config())['storeCard'];

        $this->assertSame('120', $style['primaryFields'][0]['value']);
        $this->assertSame('PKTextAlignmentRight', $style['secondaryFields'][0]['textAlignment']);
        $this->assertSame('name_2', $style['auxiliaryFields'][0]['key']);
        $this->assertSame('No cash value', $style['backFields'][0]['value']);
        $this->assertArrayNotHasKey('headerFields', $style);
    }

    public function testWebServiceAndTokenOnlyWithHttpsUrl(): void
    {
        $with = (new PassJsonBuilder())->build(PassFactory::create(), $this->config());
        $without = (new PassJsonBuilder())->build(PassFactory::create(), $this->config(null));

        $this->assertSame('https://crm.example.com/api/v1/WalletService', $with['webServiceURL']);
        $this->assertSame(str_repeat('a', 64), $with['authenticationToken']);
        $this->assertArrayNotHasKey('webServiceURL', $without);
        $this->assertArrayNotHasKey('authenticationToken', $without);
    }

    public function testBarcodes(): void
    {
        $qr = (new PassJsonBuilder())->build(PassFactory::create(), $this->config());
        $this->assertSame('PKBarcodeFormatQR', $qr['barcodes'][0]['format']);
        $this->assertSame('PKBarcodeFormatQR', $qr['barcode']['format']);

        $code128 = (new PassJsonBuilder())->build(
            PassFactory::create(['barcodeFormat' => BarcodeFormat::Code128]),
            $this->config()
        );
        $this->assertSame('PKBarcodeFormatCode128', $code128['barcodes'][0]['format']);
        $this->assertArrayNotHasKey('barcode', $code128, 'Legacy key does not support Code 128');
    }

    public function testVoidedPass(): void
    {
        $json = (new PassJsonBuilder())->build(PassFactory::create(['status' => PassStatus::Voided]), $this->config());

        $this->assertTrue($json['voided']);
    }
}
