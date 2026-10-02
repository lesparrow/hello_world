<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple;

use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use Espo\Modules\WalletPasses\Core\Model\PassDefinition;
use PKPass\PKPass;
use Throwable;

/**
 * Produces a signed .pkpass archive.
 *
 * Library choice: pkpass/pkpass (formerly tschoffelen/php-pkpass) — MIT, no transitive dependency,
 * handles manifest hashing, PKCS#7 detached signature (with WWDR chain) and ZIP packaging.
 */
final class PkpassGenerator
{
    public const MIME_TYPE = 'application/vnd.apple.pkpass';

    private const IMAGE_NAMES = ['icon', 'logo', 'strip', 'background', 'thumbnail', 'footer'];

    public function __construct(private readonly PassJsonBuilder $jsonBuilder = new PassJsonBuilder())
    {
    }

    public function generate(PassDefinition $pass, AppleConfig $config): string
    {
        $config->assertValid();

        $images = $pass->images;

        // icon.png is mandatory; fall back on the logo.
        if (empty($images['icon']) && !empty($images['logo'])) {
            $images['icon'] = $images['logo'];
        }

        if (empty($images['icon'])) {
            throw new WalletException('An icon (or a logo) image is required to build an Apple pass.');
        }

        // Apple ignores "strip" when a "background" is set on event tickets; keep both, Wallet decides.
        try {
            $pkpass = new PKPass();
            $pkpass->setCertificateString($config->p12Contents);
            $pkpass->setCertificatePassword($config->p12Password);

            if ($config->wwdrPemPath !== null) {
                $pkpass->setWwdrCertificatePath($config->wwdrPemPath);
            }

            $pkpass->setData($this->jsonBuilder->build($pass, $config));

            foreach (self::IMAGE_NAMES as $name) {
                if (!empty($images[$name])) {
                    $pkpass->addFileContent($images[$name], $name . '.png');
                    $pkpass->addFileContent($images[$name], $name . '@2x.png');
                }
            }

            return $pkpass->create();
        } catch (Throwable $e) {
            throw new WalletException('Apple pass signing failed: ' . $e->getMessage(), 0, $e);
        }
    }
}
