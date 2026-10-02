<?php

declare(strict_types=1);

namespace WalletPasses\Tests\Support;

/**
 * Generates throw-away certificates at runtime: a fake "WWDR" CA and a "Pass Type ID" leaf
 * signed by it, exported as .p12. No real Apple certificate is ever committed.
 */
final class TestCertificates
{
    public const PASSWORD = 'test-password';
    public const PASS_TYPE_ID = 'pass.com.example.test';

    private static ?array $cache = null;

    /**
     * @return array{p12: string, caPem: string, certPem: string, caPath: string}
     */
    public static function get(): array
    {
        if (self::$cache !== null) {
            return self::$cache;
        }

        $config = ['digest_alg' => 'sha256', 'private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA];

        $caKey = openssl_pkey_new($config);
        $caCsr = openssl_csr_new(['commonName' => 'Test WWDR CA'], $caKey, $config);
        $caCert = openssl_csr_sign($caCsr, null, $caKey, 30, $config, 1);
        openssl_x509_export($caCert, $caPem);

        $key = openssl_pkey_new($config);
        $csr = openssl_csr_new([
            'commonName' => 'Pass Type ID: ' . self::PASS_TYPE_ID,
            'UID' => self::PASS_TYPE_ID,
        ], $key, $config);
        $cert = openssl_csr_sign($csr, $caCert, $caKey, 30, $config, 2);
        openssl_x509_export($cert, $certPem);
        openssl_pkcs12_export($cert, $p12, $key, self::PASSWORD);

        $caPath = (string) tempnam(sys_get_temp_dir(), 'wwdr');
        file_put_contents($caPath, $caPem);

        return self::$cache = ['p12' => $p12, 'caPem' => $caPem, 'certPem' => $certPem, 'caPath' => $caPath];
    }

    public static function serviceAccountJson(): string
    {
        $key = openssl_pkey_new(['private_key_bits' => 2048, 'private_key_type' => OPENSSL_KEYTYPE_RSA]);
        openssl_pkey_export($key, $pem);

        return (string) json_encode([
            'type' => 'service_account',
            'project_id' => 'test',
            'private_key_id' => 'kid123',
            'private_key' => $pem,
            'client_email' => 'wallet@test.iam.gserviceaccount.com',
            'token_uri' => 'https://oauth2.googleapis.com/token',
        ]);
    }
}
