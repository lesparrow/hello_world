<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Api;

use Espo\Core\Api\Response;
use Espo\Core\Api\ResponseComposer;
use Espo\Modules\WalletPasses\Core\Apple\WebService\WebServiceResult;

/**
 * Converts core results into EspoCRM API responses.
 */
final class ResponseFactory
{
    public static function fromWebServiceResult(WebServiceResult $result): Response
    {
        $response = ResponseComposer::empty()->setStatus($result->status);

        foreach ($result->headers as $name => $value) {
            $response->setHeader($name, $value);
        }

        if ($result->body !== '') {
            $response->writeBody($result->body);
        }

        return $response;
    }

    public static function binary(string $contents, string $contentType, ?string $fileName = null): Response
    {
        $response = ResponseComposer::empty()
            ->setHeader('Content-Type', $contentType)
            ->setHeader('Content-Length', (string) strlen($contents))
            ->setHeader('X-Content-Type-Options', 'nosniff')
            ->writeBody($contents);

        if ($fileName !== null) {
            $response->setHeader('Content-Disposition', 'attachment; filename="' . $fileName . '"');
        }

        return $response;
    }

    public static function redirect(string $url): Response
    {
        return ResponseComposer::empty()
            ->setStatus(302)
            ->setHeader('Location', $url)
            ->setHeader('Cache-Control', 'no-store');
    }

    public static function html(string $html, int $status = 200): Response
    {
        return ResponseComposer::empty()
            ->setStatus($status)
            ->setHeader('Content-Type', 'text/html; charset=utf-8')
            ->setHeader('Cache-Control', 'no-store')
            ->writeBody($html);
    }
}
