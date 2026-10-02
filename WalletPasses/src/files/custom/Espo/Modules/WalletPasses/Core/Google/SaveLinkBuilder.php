<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use Espo\Modules\WalletPasses\Core\Model\PassDefinition;

/**
 * Builds the "Add to Google Wallet" link: https://pay.google.com/gp/v/save/<signed JWT>.
 *
 * The object is created beforehand through the REST API, so the JWT only references its id
 * (short URL, fits in a QR code).
 */
final class SaveLinkBuilder
{
    public const SAVE_URL = 'https://pay.google.com/gp/v/save/';

    public function __construct(
        private readonly GoogleConfig $config,
        private readonly ObjectMapper $mapper,
    ) {
    }

    public function build(PassDefinition $pass): string
    {
        $vertical = $pass->passType->googleVertical();

        $claims = [
            'iss' => $this->config->serviceAccount->clientEmail,
            'aud' => 'google',
            'typ' => 'savetowallet',
            'iat' => time(),
            'origins' => array_values($this->config->origins),
            'payload' => [
                $vertical . 'Objects' => [
                    [
                        'id' => $this->mapper->objectId($pass),
                        'classId' => $this->mapper->classId($pass),
                    ],
                ],
            ],
        ];

        return self::SAVE_URL . Jwt::encodeRs256(
            $claims,
            $this->config->serviceAccount->privateKey,
            $this->config->serviceAccount->privateKeyId
        );
    }
}
