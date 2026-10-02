<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\PublicLink;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\NotFound;
use Espo\Modules\WalletPasses\Api\ResponseFactory;
use Espo\Modules\WalletPasses\Core\Util\QrCode;
use Espo\Modules\WalletPasses\Tools\PassLinks;

/**
 * GET /WalletService/qr/{serialNumber}?s=<hmac>[&size=320] — PNG QR code of the smart link
 * (usable in e-mails: <img src="{WalletPass.walletQrCodeUrl}">).
 */
class GetQrCode implements Action
{
    public function __construct(private PassLinks $links)
    {
    }

    public function process(Request $request): Response
    {
        $serial = (string) $request->getRouteParam('serialNumber');

        if (
            !preg_match('/^[A-Za-z0-9._-]{1,128}$/', $serial) ||
            !$this->links->verify((string) $request->getQueryParam('s'), 'qr', $serial)
        ) {
            throw new NotFound();
        }

        $size = (int) ($request->getQueryParam('size') ?: 320);

        return ResponseFactory::binary(QrCode::png($this->links->smartLink($serial), $size), 'image/png')
            ->setHeader('Cache-Control', 'public, max-age=86400');
    }
}
