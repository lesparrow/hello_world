<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple;

use DateTimeImmutable;
use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;

/**
 * Certificate helpers: PKCS#12 parsing (with OpenSSL 3 "legacy" fallback),
 * DER → PEM conversion and metadata extraction.
 */
final class Certificate
{
    private const KEY_PATTERN = '/-----BEGIN (?:RSA )?PRIVATE KEY-----.+?-----END (?:RSA )?PRIVATE KEY-----/s';

    /**
     * @return array{cert: string, pkey: string}
     */
    public static function readP12(string $contents, string $password): array
    {
        $certs = [];

        if (@openssl_pkcs12_read($contents, $certs, $password)) {
            return ['cert' => $certs['cert'], 'pkey' => $certs['pkey']];
        }

        $error = self::collectOpenSslErrors();

        // Apple-exported .p12 files often use RC2-40, disabled by default in OpenSSL 3.
        if (str_contains($error, 'unsupported') && function_exists('proc_open')) {
            $converted = self::readP12WithLegacyCli($contents, $password);

            if ($converted !== null) {
                return $converted;
            }
        }

        throw new ConfigurationException(
            'Unable to read the .p12 certificate (wrong password, missing private key or legacy encryption). ' .
            'OpenSSL: ' . ($error ?: 'unknown error')
        );
    }

    /**
     * Converts a certificate given as DER (.cer) or PEM into PEM.
     */
    public static function toPem(string $contents): string
    {
        if (str_contains($contents, '-----BEGIN CERTIFICATE-----')) {
            $pem = $contents;
        } else {
            $pem = "-----BEGIN CERTIFICATE-----\n" .
                chunk_split(base64_encode($contents), 64, "\n") .
                "-----END CERTIFICATE-----\n";
        }

        if (@openssl_x509_read($pem) === false) {
            throw new ConfigurationException('Invalid X.509 certificate.');
        }

        return $pem;
    }

    /**
     * @return array{subject: string, issuer: string, validTo: DateTimeImmutable, uid: ?string}
     */
    public static function describe(string $pem): array
    {
        $info = openssl_x509_parse($pem);

        if ($info === false) {
            throw new ConfigurationException('Invalid X.509 certificate.');
        }

        $subject = $info['subject'] ?? [];

        return [
            'subject' => (string) ($subject['CN'] ?? ''),
            'issuer' => (string) (($info['issuer'] ?? [])['CN'] ?? ''),
            'validTo' => (new DateTimeImmutable())->setTimestamp((int) $info['validTo_time_t']),
            // For Pass Type ID certificates, UID = pass type identifier.
            'uid' => isset($subject['UID']) ? (string) $subject['UID'] : null,
        ];
    }

    private static function collectOpenSslErrors(): string
    {
        $error = '';

        while ($message = openssl_error_string()) {
            $error .= $message . ' ';
        }

        return trim($error);
    }

    /**
     * @return array{cert: string, pkey: string}|null
     */
    private static function readP12WithLegacyCli(string $contents, string $password): ?array
    {
        $in = tempnam(sys_get_temp_dir(), 'wp12');

        if ($in === false) {
            return null;
        }

        try {
            chmod($in, 0600);
            file_put_contents($in, $contents);

            $process = proc_open(
                ['openssl', 'pkcs12', '-in', $in, '-nodes', '-legacy', '-passin', 'stdin'],
                [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
                $pipes
            );

            if (!is_resource($process)) {
                return null;
            }

            fwrite($pipes[0], $password . "\n");
            fclose($pipes[0]);
            $output = (string) stream_get_contents($pipes[1]);
            fclose($pipes[1]);
            fclose($pipes[2]);
            proc_close($process);

            if (
                !preg_match('/-----BEGIN CERTIFICATE-----.+?-----END CERTIFICATE-----/s', $output, $cert) ||
                !preg_match(self::KEY_PATTERN, $output, $k)
            ) {
                return null;
            }

            return ['cert' => $cert[0] . "\n", 'pkey' => $k[0] . "\n"];
        } finally {
            @unlink($in);
        }
    }
}
