<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Utils\Config;
use RuntimeException;

/**
 * Stores credentials (certificates, passwords, service account key, link secret) outside the web root
 * in data/wallet-passes/, encrypted with AES-256-GCM using a key derived from EspoCRM's cryptKey.
 * Nothing secret is written to data/config.php nor exposed by the Settings API.
 */
class SecretStore
{
    public const DIR = 'data/wallet-passes';

    public const APPLE_P12 = 'apple-pass.p12';
    public const APPLE_P12_PASSWORD = 'apple-pass-password';
    public const APPLE_WWDR = 'apple-wwdr.pem';
    public const GOOGLE_SERVICE_ACCOUNT = 'google-service-account.json';
    public const LINK_SECRET = 'link-secret';

    private const CIPHER = 'aes-256-gcm';

    public function __construct(private Config $config)
    {
    }

    public function has(string $name): bool
    {
        return is_file($this->path($name));
    }

    public function get(string $name): ?string
    {
        $path = $this->path($name);

        if (!is_file($path)) {
            return null;
        }

        $raw = base64_decode((string) file_get_contents($path), true);

        if ($raw === false || strlen($raw) < 28) {
            throw new RuntimeException("Wallet secret '$name' is corrupted.");
        }

        $iv = substr($raw, 0, 12);
        $tag = substr($raw, 12, 16);
        $cipherText = substr($raw, 28);

        $value = openssl_decrypt($cipherText, self::CIPHER, $this->key(), OPENSSL_RAW_DATA, $iv, $tag);

        if ($value === false) {
            throw new RuntimeException("Wallet secret '$name' can't be decrypted (cryptKey changed?).");
        }

        return $value;
    }

    public function set(string $name, string $value): void
    {
        $this->ensureDir();

        $iv = random_bytes(12);
        $tag = '';
        $cipherText = openssl_encrypt($value, self::CIPHER, $this->key(), OPENSSL_RAW_DATA, $iv, $tag);

        if ($cipherText === false) {
            throw new RuntimeException('Encryption failure.');
        }

        $path = $this->path($name);
        file_put_contents($path, base64_encode($iv . $tag . $cipherText), LOCK_EX);
        @chmod($path, 0600);
    }

    public function delete(string $name): void
    {
        @unlink($this->path($name));
    }

    public function modifiedAt(string $name): ?int
    {
        $path = $this->path($name);

        return is_file($path) ? (int) filemtime($path) : null;
    }

    /**
     * Returns the secret used to sign public links, generating it on first use.
     */
    public function getLinkSecret(): string
    {
        $secret = $this->get(self::LINK_SECRET);

        if ($secret === null) {
            $secret = bin2hex(random_bytes(32));
            $this->set(self::LINK_SECRET, $secret);
        }

        return $secret;
    }

    /**
     * Writes a decrypted copy to a private temp file (for libraries that need a path). Caller unlinks it.
     */
    public function exportToTempFile(string $name): ?string
    {
        $value = $this->get($name);

        if ($value === null) {
            return null;
        }

        $file = (string) tempnam(sys_get_temp_dir(), 'wps');
        chmod($file, 0600);
        file_put_contents($file, $value);

        return $file;
    }

    private function ensureDir(): void
    {
        if (!is_dir(self::DIR)) {
            mkdir(self::DIR, 0700, true);
        }

        $htaccess = self::DIR . '/.htaccess';

        if (!is_file($htaccess)) {
            file_put_contents($htaccess, "Require all denied\nDeny from all\n");
        }
    }

    private function path(string $name): string
    {
        if (!preg_match('/^[a-z0-9.-]+$/', $name)) {
            throw new RuntimeException('Bad secret name.');
        }

        return self::DIR . '/' . $name . '.enc';
    }

    private function key(): string
    {
        $cryptKey = (string) $this->config->get('cryptKey');

        if ($cryptKey === '') {
            throw new RuntimeException('EspoCRM cryptKey is not set.');
        }

        return hash_hmac('sha256', 'wallet-passes-secret-store', $cryptKey, true);
    }
}
