<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;

/**
 * Sends Wallet "pass updated" notifications through APNs (HTTP/2, certificate authentication).
 *
 * - Payload: empty JSON dictionary "{}".
 * - Topic: the Pass Type ID; certificate = the same Pass Type ID certificate used for signing.
 * - Wallet updates are only delivered by the production gateway.
 * - There is no "pass.update" apns-push-type; the header is omitted by default (optionally "background").
 */
class ApnsClient
{
    public function __construct(private readonly AppleConfig $config)
    {
    }

    /**
     * @param string[] $pushTokens
     * @return PushResult[]
     */
    public function push(array $pushTokens): array
    {
        $pushTokens = array_values(array_unique(array_filter($pushTokens, fn ($t) => $this->isValidToken($t))));

        if ($pushTokens === []) {
            return [];
        }

        if (!defined('CURL_HTTP_VERSION_2_0')) {
            throw new WalletException('cURL with HTTP/2 support is required for APNs.');
        }

        $pair = Certificate::readP12($this->config->p12Contents, $this->config->p12Password);
        [$certFile, $keyFile] = $this->writeTempCredentials($pair);

        try {
            $multi = curl_multi_init();
            $handles = [];

            foreach ($pushTokens as $token) {
                $handle = $this->createHandle($token, $certFile, $keyFile);
                curl_multi_add_handle($multi, $handle);
                $handles[$token] = $handle;
            }

            $transportErrors = [];

            do {
                $status = curl_multi_exec($multi, $running);

                while ($info = curl_multi_info_read($multi)) {
                    if ($info['result'] !== CURLE_OK) {
                        $transportErrors[array_search($info['handle'], $handles, true)] =
                            curl_strerror($info['result']);
                    }
                }

                if ($running) {
                    curl_multi_select($multi, 1.0);
                }
            } while ($running && $status === CURLM_OK);

            $results = [];

            foreach ($handles as $token => $handle) {
                $code = (int) curl_getinfo($handle, CURLINFO_RESPONSE_CODE);
                $body = (string) curl_multi_getcontent($handle);
                $reason = null;

                if ($code !== 200) {
                    $decoded = json_decode($body, true);
                    $reason = is_array($decoded) && isset($decoded['reason']) ?
                        (string) $decoded['reason'] :
                        ($transportErrors[$token] ?? (curl_error($handle) ?: 'connection failed'));
                }

                $results[] = new PushResult((string) $token, $code, $reason);
                curl_multi_remove_handle($multi, $handle);
                curl_close($handle);
            }

            curl_multi_close($multi);

            return $results;
        } finally {
            @unlink($certFile);
            @unlink($keyFile);
        }
    }

    private function isValidToken(mixed $token): bool
    {
        return is_string($token) && preg_match('/^[0-9a-fA-F]{32,200}$/', $token) === 1;
    }

    /**
     * @return \CurlHandle
     */
    private function createHandle(string $token, string $certFile, string $keyFile)
    {
        $headers = [
            'apns-topic: ' . $this->config->passTypeIdentifier,
            'content-type: application/json',
        ];

        if ($this->config->apnsPushType) {
            $headers[] = 'apns-push-type: ' . $this->config->apnsPushType;
            $headers[] = 'apns-priority: 5';
        }

        $handle = curl_init(rtrim($this->config->apnsHost, '/') . '/3/device/' . $token);

        curl_setopt_array($handle, [
            CURLOPT_POST => true,
            CURLOPT_POSTFIELDS => '{}',
            CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_2_0,
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_HTTPHEADER => $headers,
            CURLOPT_SSLCERT => $certFile,
            CURLOPT_SSLKEY => $keyFile,
            CURLOPT_CONNECTTIMEOUT => 10,
            CURLOPT_TIMEOUT => 20,
        ]);

        return $handle;
    }

    /**
     * @param array{cert: string, pkey: string} $pair
     * @return array{string, string}
     */
    private function writeTempCredentials(array $pair): array
    {
        $key = openssl_pkey_get_private($pair['pkey'], $this->config->p12Password);

        if ($key === false || !openssl_pkey_export($key, $keyPem)) {
            throw new WalletException('Unable to extract the private key from the .p12 certificate.');
        }

        $certFile = (string) tempnam(sys_get_temp_dir(), 'wapc');
        $keyFile = (string) tempnam(sys_get_temp_dir(), 'wapk');
        chmod($certFile, 0600);
        chmod($keyFile, 0600);
        file_put_contents($certFile, $pair['cert']);
        file_put_contents($keyFile, $keyPem);

        return [$certFile, $keyFile];
    }
}
