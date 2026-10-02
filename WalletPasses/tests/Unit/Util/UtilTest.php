<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Unit\Util;

use Espo\Modules\WalletPasses\Core\Apple\Certificate;
use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;
use Espo\Modules\WalletPasses\Core\Model\PassField;
use Espo\Modules\WalletPasses\Core\Util\Color;
use Espo\Modules\WalletPasses\Core\Util\LinkSigner;
use Espo\Modules\WalletPasses\Core\Util\Placeholder;
use Espo\Modules\WalletPasses\Core\Util\QrCode;
use Espo\Modules\WalletPasses\Core\Util\SecureToken;
use Espo\Modules\WalletPasses\Core\Util\UserAgent;
use PHPUnit\Framework\TestCase;
use WalletPasses\Tests\Support\TestCertificates;

final class UtilTest extends TestCase
{
    public function testColor(): void
    {
        $this->assertSame('rgb(255, 0, 170)', Color::hexToAppleRgb('#ff00aa'));
        $this->assertSame('rgb(255, 255, 255)', Color::hexToAppleRgb('fff'));
        $this->assertNull(Color::hexToAppleRgb('red'));
        $this->assertSame('#ABCDEF', Color::normalizeHex('abcdef'));
    }

    public function testPlaceholder(): void
    {
        $this->assertSame(
            'Hello Jane, 120 pts, ',
            Placeholder::render('Hello {contact.firstName}, {pass.points} pts, {pass.unknown}', [
                'contact.firstName' => 'Jane',
                'pass.points' => 120,
            ])
        );
        $this->assertSame('{notAPlaceholder}', Placeholder::render('{notAPlaceholder}', []));
    }

    public function testUserAgent(): void
    {
        $iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1';
        $android = 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36';
        $windows = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36';

        $this->assertSame(UserAgent::PLATFORM_APPLE, UserAgent::detectPlatform($iphone));
        $this->assertSame(UserAgent::PLATFORM_GOOGLE, UserAgent::detectPlatform($android));
        $this->assertSame(UserAgent::PLATFORM_OTHER, UserAgent::detectPlatform($windows));
        $this->assertSame(UserAgent::PLATFORM_OTHER, UserAgent::detectPlatform(null));
    }

    public function testLinkSigner(): void
    {
        $signer = new LinkSigner('secret');
        $signature = $signer->sign('go', 'SER1');

        $this->assertTrue($signer->verify($signature, 'go', 'SER1'));
        $this->assertFalse($signer->verify($signature, 'go', 'SER2'));
        $this->assertFalse((new LinkSigner('other'))->verify($signature, 'go', 'SER1'));
        $this->assertFalse($signer->verify('', 'go', 'SER1'));
    }

    public function testTokens(): void
    {
        $this->assertMatchesRegularExpression('/^[0-9a-f]{64}$/', SecureToken::authenticationToken());
        $this->assertMatchesRegularExpression('/^[0-9A-F]{20}$/', SecureToken::serialNumber());
        $this->assertFalse(SecureToken::equals('', ''));
        $this->assertTrue(SecureToken::equals('abc', 'abc'));
    }

    public function testPassFieldNormalization(): void
    {
        $field = PassField::fromArray(['key' => 'a b!', 'section' => 'nope', 'textAlignment' => 'x'], 'secondary', 3);

        $this->assertSame('ab', $field->key);
        $this->assertSame('secondary', $field->section);
        $this->assertSame('natural', $field->textAlignment);
        $this->assertSame('field7', PassField::fromArray([], 'back', 7)->key);
    }

    public function testQrCodeIsPng(): void
    {
        $this->assertStringStartsWith("\x89PNG", QrCode::png('https://example.com'));
    }

    public function testCertificateHelpers(): void
    {
        $certs = TestCertificates::get();

        $pair = Certificate::readP12($certs['p12'], TestCertificates::PASSWORD);
        $info = Certificate::describe($pair['cert']);

        $this->assertSame(TestCertificates::PASS_TYPE_ID, $info['uid']);
        $this->assertGreaterThan(time(), $info['validTo']->getTimestamp());

        // DER → PEM conversion of the WWDR certificate.
        $der = base64_decode(preg_replace('/-----[A-Z ]+-----|\s/', '', $certs['caPem']));
        $this->assertStringContainsString('BEGIN CERTIFICATE', Certificate::toPem($der));

        $this->expectException(ConfigurationException::class);
        Certificate::readP12($certs['p12'], 'wrong');
    }
}
