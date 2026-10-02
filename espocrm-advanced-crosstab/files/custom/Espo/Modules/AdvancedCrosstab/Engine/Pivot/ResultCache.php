<?php

namespace Espo\Modules\AdvancedCrosstab\Engine\Pivot;

use Espo\Modules\AdvancedCrosstab\Engine\Limits;
use Throwable;

/**
 * Short-lived per-user result cache (file based). The cache key includes the user ID, so results computed
 * under one user's ACL are never served to another user. Entries expire after `cacheTtl` seconds.
 */
class ResultCache
{
    private const DIR = 'data/cache/advanced-crosstab';

    public function __construct(private Limits $limits) {}

    public function key(array $definition, string $userId): string
    {
        return hash('sha256', json_encode([$definition, $userId, 'v1']) ?: '');
    }

    public function get(string $key): ?array
    {
        $ttl = $this->limits->cacheTtl();

        if ($ttl <= 0) {
            return null;
        }

        $file = $this->path($key);

        if (!is_file($file) || filemtime($file) < time() - $ttl) {
            return null;
        }

        try {
            $data = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (Throwable) {
            return null;
        }

        return is_array($data) ? $data : null;
    }

    public function set(string $key, array $result): void
    {
        if ($this->limits->cacheTtl() <= 0) {
            return;
        }

        try {
            if (!is_dir(self::DIR)) {
                @mkdir(self::DIR, 0775, true);
            }

            $tmp = $this->path($key) . '.' . bin2hex(random_bytes(4));

            if (@file_put_contents($tmp, json_encode($result)) !== false) {
                @rename($tmp, $this->path($key));
            }

            if (random_int(1, 50) === 1) {
                $this->purge();
            }
        } catch (Throwable) {}
    }

    private function purge(): void
    {
        $limit = time() - max($this->limits->cacheTtl(), 60) * 2;

        foreach (glob(self::DIR . '/*.json') ?: [] as $file) {
            if (@filemtime($file) < $limit) {
                @unlink($file);
            }
        }
    }

    private function path(string $key): string
    {
        return self::DIR . '/' . $key . '.json';
    }
}
