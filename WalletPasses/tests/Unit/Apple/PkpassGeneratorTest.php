<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Unit\Apple;

use Espo\Modules\WalletPasses\Core\Apple\AppleConfig;
use Espo\Modules\WalletPasses\Core\Apple\PkpassGenerator;
use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;
use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use PHPUnit\Framework\TestCase;
use WalletPasses\Tests\Support\PassFactory;
use WalletPasses\Tests\Support\TestCertificates;
use ZipArchive;

/**
 * Signature of the .pkpass: manifest hashes + detached PKCS#7 signature verified with OpenSSL.
 */
final class PkpassGeneratorTest extends TestCase
{
    private function config(string $password = TestCertificates::PASSWORD): AppleConfig
    {
        $certs = TestCertificates::get();

        return new AppleConfig(
            'ABCDE12345',
            TestCertificates::PASS_TYPE_ID,
            $certs['p12'],
            $password,
            $certs['caPath'],
            'https://crm.example.com/api/v1/WalletService'
        );
    }

    /**
     * @return array<string, string>
     */
    private function unzip(string $pkpass): array
    {
        $file = (string) tempnam(sys_get_temp_dir(), 'pkt');
        file_put_contents($file, $pkpass);

        $zip = new ZipArchive();
        $this->assertTrue($zip->open($file) === true);

        $files = [];

        for ($i = 0; $i < $zip->numFiles; $i++) {
            $name = (string) $zip->getNameIndex($i);
            $files[$name] = (string) $zip->getFromIndex($i);
        }

        $zip->close();
        unlink($file);

        return $files;
    }

    public function testArchiveContainsSignedManifest(): void
    {
        $files = $this->unzip((new PkpassGenerator())->generate(PassFactory::create(), $this->config()));

        foreach (['pass.json', 'manifest.json', 'signature', 'icon.png', 'icon@2x.png', 'logo.png'] as $name) {
            $this->assertArrayHasKey($name, $files, "$name missing");
        }

        $manifest = json_decode($files['manifest.json'], true);

        foreach ($manifest as $name => $sha1) {
            $this->assertSame(sha1($files[$name]), $sha1, "Bad hash for $name");
        }

        $this->assertArrayNotHasKey('signature', $manifest);
        $this->assertSame('SERIAL123', json_decode($files['pass.json'], true)['serialNumber']);
    }

    public function testSignatureIsValidDetachedPkcs7(): void
    {
        if (!is_executable('/usr/bin/openssl') && trim((string) shell_exec('command -v openssl')) === '') {
            $this->markTestSkipped('openssl CLI not available.');
        }

        $certs = TestCertificates::get();
        $files = $this->unzip((new PkpassGenerator())->generate(PassFactory::create(), $this->config()));

        $dir = sys_get_temp_dir() . '/pkt' . bin2hex(random_bytes(4));
        mkdir($dir);
        file_put_contents("$dir/signature", $files['signature']);
        file_put_contents("$dir/manifest.json", $files['manifest.json']);
        file_put_contents("$dir/ca.pem", $certs['caPem']);

        // Detached DER signature over manifest.json, chained to the (test) WWDR certificate.
        exec(sprintf(
            'openssl cms -verify -binary -inform DER -in %s -content %s -CAfile %s -purpose any ' .
            '-signer %s -out /dev/null 2>&1',
            escapeshellarg("$dir/signature"),
            escapeshellarg("$dir/manifest.json"),
            escapeshellarg("$dir/ca.pem"),
            escapeshellarg("$dir/signer.pem")
        ), $output, $code);

        $this->assertSame(0, $code, 'CMS verification failed: ' . implode("\n", $output));

        $this->assertSame(
            openssl_x509_fingerprint($certs['certPem']),
            openssl_x509_fingerprint((string) file_get_contents("$dir/signer.pem")),
            'The signer must be the pass certificate'
        );

        // A tampered manifest must not verify.
        file_put_contents("$dir/manifest.json", $files['manifest.json'] . ' ');
        exec(sprintf(
            'openssl cms -verify -binary -inform DER -in %s -content %s -CAfile %s -purpose any -out /dev/null 2>&1',
            escapeshellarg("$dir/signature"),
            escapeshellarg("$dir/manifest.json"),
            escapeshellarg("$dir/ca.pem")
        ), $output, $tamperedCode);

        $this->assertNotSame(0, $tamperedCode);

        array_map('unlink', glob("$dir/*") ?: []);
        rmdir($dir);
    }

    public function testLogoIsUsedWhenIconIsMissing(): void
    {
        $png = PassFactory::png();
        $files = $this->unzip(
            (new PkpassGenerator())->generate(PassFactory::create(['images' => ['logo' => $png]]), $this->config())
        );

        $this->assertSame($png, $files['icon.png']);
    }

    public function testMissingImagesThrow(): void
    {
        $this->expectException(WalletException::class);

        (new PkpassGenerator())->generate(PassFactory::create(['images' => []]), $this->config());
    }

    public function testWrongPasswordThrows(): void
    {
        $this->expectException(WalletException::class);

        (new PkpassGenerator())->generate(PassFactory::create(), $this->config('wrong'));
    }

    public function testInvalidTeamIdIsRejected(): void
    {
        $this->expectException(ConfigurationException::class);

        $config = new AppleConfig('bad', 'pass.com.example.test', 'x', 'y');
        (new PkpassGenerator())->generate(PassFactory::create(), $config);
    }
}
