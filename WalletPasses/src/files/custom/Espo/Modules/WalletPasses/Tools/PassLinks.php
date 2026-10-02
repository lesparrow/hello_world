<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

/**
 * Builds the public, HMAC-signed URLs of a pass.
 *
 *  - smart link  …/api/v1/WalletService/go/{serial}?s=…   (QR code target, platform detected at scan time)
 *  - QR PNG      …/api/v1/WalletService/qr/{serial}?s=…   (embeddable in e-mails / print)
 *  - images      …/api/v1/WalletService/image/{templateId}/{image}?s=…  (Google requires public image URLs)
 */
class PassLinks
{
    public function __construct(private WalletSettings $settings)
    {
    }

    public function smartLink(string $serialNumber, ?string $platform = null): string
    {
        $url = $this->base() . '/go/' . rawurlencode($serialNumber) . '?s=' . $this->sign('go', $serialNumber);

        return $platform !== null ? $url . '&p=' . rawurlencode($platform) : $url;
    }

    public function qrCodeUrl(string $serialNumber): string
    {
        return $this->base() . '/qr/' . rawurlencode($serialNumber) . '?s=' . $this->sign('qr', $serialNumber);
    }

    public function imageUrl(string $templateId, string $image, ?string $attachmentId): ?string
    {
        if ($attachmentId === null) {
            return null;
        }

        // The attachment id is part of the signature: replacing the image invalidates the old URL.
        return $this->base() . '/image/' . rawurlencode($templateId) . '/' . rawurlencode($image) .
            '?v=' . rawurlencode($attachmentId) . '&s=' . $this->sign('image', $templateId, $image, $attachmentId);
    }

    public function verify(string $signature, string ...$parts): bool
    {
        return $this->settings->getLinkSigner()->verify($signature, ...$parts);
    }

    private function sign(string ...$parts): string
    {
        return $this->settings->getLinkSigner()->sign(...$parts);
    }

    private function base(): string
    {
        return $this->settings->getPublicBaseUrl() . '/api/v1/WalletService';
    }
}
