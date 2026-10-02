<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api\PublicLink;

use Espo\Core\Api\Action;
use Espo\Core\Api\Request;
use Espo\Core\Api\Response;
use Espo\Core\Exceptions\NotFound;
use Espo\Core\FileStorage\Manager as FileStorageManager;
use Espo\Entities\Attachment;
use Espo\Modules\WalletPasses\Api\ResponseFactory;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\Modules\WalletPasses\Tools\PassLinks;
use Espo\ORM\EntityManager;

/**
 * GET /WalletService/image/{templateId}/{image}?v=<attachmentId>&s=<hmac>
 * Google Wallet fetches logos / hero images from public URLs; only signed template images are served.
 */
class GetImage implements Action
{
    public function __construct(
        private PassLinks $links,
        private EntityManager $entityManager,
        private FileStorageManager $fileStorageManager,
    ) {
    }

    public function process(Request $request): Response
    {
        $templateId = (string) $request->getRouteParam('templateId');
        $image = (string) $request->getRouteParam('image');
        $version = (string) $request->getQueryParam('v');

        if (
            !in_array($image, WalletPassTemplate::IMAGE_FIELD_LIST, true) ||
            !$this->links->verify((string) $request->getQueryParam('s'), 'image', $templateId, $image, $version)
        ) {
            throw new NotFound();
        }

        $template = $this->entityManager->getEntityById(WalletPassTemplate::ENTITY_TYPE, $templateId);

        if (!$template instanceof WalletPassTemplate || $template->getImageId($image) !== $version) {
            throw new NotFound();
        }

        $attachment = $this->entityManager->getEntityById(Attachment::ENTITY_TYPE, $version);

        if (!$attachment instanceof Attachment) {
            throw new NotFound();
        }

        $type = (string) $attachment->get('type');

        if (!in_array($type, ['image/png', 'image/jpeg', 'image/gif', 'image/webp'], true)) {
            throw new NotFound();
        }

        return ResponseFactory::binary($this->fileStorageManager->getContents($attachment), $type)
            ->setHeader('Cache-Control', 'public, max-age=604800');
    }
}
