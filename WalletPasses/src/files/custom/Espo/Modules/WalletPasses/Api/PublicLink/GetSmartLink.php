<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\PublicLink;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Utils\Log;
use Espo\Modules\WalletPasses\Api\ResponseFactory;
use Espo\Modules\WalletPasses\Core\Apple\PkpassGenerator;
use Espo\Modules\WalletPasses\Core\Util\QrCode;
use Espo\Modules\WalletPasses\Core\Util\UserAgent;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\Modules\WalletPasses\Tools\PassLinks;
use Espo\Modules\WalletPasses\Tools\PassLogger;
use Espo\Modules\WalletPasses\Tools\WalletPassService;
use Espo\Modules\WalletPasses\Tools\WalletSettings;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * GET /WalletService/go/{serialNumber}?s=<hmac>[&p=apple|google]
 *
 * Target of the QR code / e-mail link. The platform is detected at scan time from the User-Agent:
 * iOS → the signed .pkpass, Android → redirect to Google "Save to Wallet", other → a landing page
 * offering both buttons.
 */
class GetSmartLink implements Action
{
    public function __construct(
        private EntityManager $entityManager,
        private PassLinks $links,
        private WalletSettings $settings,
        private WalletPassService $passService,
        private PassLogger $logger,
        private Log $log,
    ) {
    }

    public function process(Request $request): Response
    {
        $serial = (string) $request->getRouteParam('serialNumber');
        $signature = (string) $request->getQueryParam('s');

        if (!preg_match('/^[A-Za-z0-9._-]{1,128}$/', $serial) || !$this->links->verify($signature, 'go', $serial)) {
            return ResponseFactory::html($this->page('Lien invalide / Invalid link', ''), 404);
        }

        $pass = $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->where(['serialNumber' => $serial])
            ->findOne();

        if (!$pass instanceof WalletPass) {
            return ResponseFactory::html($this->page('Pass introuvable / Pass not found', ''), 404);
        }

        $platform = $request->getQueryParam('p') ?? UserAgent::detectPlatform($request->getHeader('User-Agent'));

        try {
            if ($platform === UserAgent::PLATFORM_APPLE && $this->settings->isAppleEnabled()) {
                $contents = $this->passService->renderPkpass($pass);
                $this->logger->log(WalletPassLog::EVENT_DOWNLOADED, $pass->getId(), 'Apple (smart link)');

                return ResponseFactory::binary(
                    $contents,
                    PkpassGenerator::MIME_TYPE,
                    $this->passService->pkpassFileName($pass)
                );
            }

            if ($platform === UserAgent::PLATFORM_GOOGLE && $this->settings->isGoogleEnabled()) {
                $url = $this->passService->getGoogleSaveLink($pass);
                $this->logger->log(WalletPassLog::EVENT_DOWNLOADED, $pass->getId(), 'Google (smart link)');

                return ResponseFactory::redirect($url);
            }
        } catch (Throwable $e) {
            $this->log->error('WalletPasses smart link: ' . $e->getMessage());
            $this->logger->log(WalletPassLog::EVENT_ERROR, $pass->getId(), 'Smart link: ' . $e->getMessage());

            return ResponseFactory::html(
                $this->page('Pass momentanément indisponible / Pass temporarily unavailable', ''),
                503
            );
        }

        return ResponseFactory::html($this->landing($pass, $serial));
    }

    private function landing(WalletPass $pass, string $serial): string
    {
        $buttons = '';

        if ($this->settings->isAppleEnabled()) {
            $buttons .= sprintf(
                '<a class="btn apple" href="%s">Ajouter à Apple Wallet<br><small>Add to Apple Wallet</small></a>',
                htmlspecialchars($this->links->smartLink($serial, UserAgent::PLATFORM_APPLE))
            );
        }

        if ($this->settings->isGoogleEnabled()) {
            $buttons .= sprintf(
                '<a class="btn google" href="%s">Ajouter à Google Wallet<br><small>Add to Google Wallet</small></a>',
                htmlspecialchars($this->links->smartLink($serial, UserAgent::PLATFORM_GOOGLE))
            );
        }

        $qr = base64_encode(QrCode::png($this->links->smartLink($serial), 260));

        $body = $buttons .
            '<p>Ou scannez ce code avec votre téléphone<br><small>Or scan this code with your phone</small></p>' .
            '<img alt="QR" width="260" height="260" src="data:image/png;base64,' . $qr . '">';

        return $this->page(htmlspecialchars((string) $pass->get('name')), $body);
    }

    private function page(string $title, string $body): string
    {
        return '<!doctype html><html lang="fr"><head><meta charset="utf-8">' .
            '<meta name="viewport" content="width=device-width,initial-scale=1">' .
            '<meta name="robots" content="noindex">' .
            '<title>' . $title . '</title><style>' .
            'body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f3f4f6;margin:0;padding:24px;' .
            'text-align:center;color:#111}main{max-width:420px;margin:0 auto;background:#fff;border-radius:16px;' .
            'padding:24px;box-shadow:0 4px 16px rgba(0,0,0,.08)}.btn{display:block;margin:12px 0;padding:14px;' .
            'border-radius:10px;color:#fff;text-decoration:none;font-weight:600}.apple{background:#000}' .
            '.google{background:#1a73e8}small{font-weight:400;opacity:.8}img{max-width:100%;height:auto}' .
            '</style></head><body><main><h1 style="font-size:1.25rem">' . $title . '</h1>' . $body .
            '</main></body></html>';
    }
}
