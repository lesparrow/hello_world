<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use DateTimeImmutable;
use DateTimeZone;
use Espo\Core\FileStorage\Manager as FileStorageManager;
use Espo\Core\Utils\Config;
use Espo\Entities\Attachment;
use Espo\Modules\WalletPasses\Core\Exception\WalletException;
use Espo\Modules\WalletPasses\Core\Model\BarcodeFormat;
use Espo\Modules\WalletPasses\Core\Model\PassDefinition;
use Espo\Modules\WalletPasses\Core\Model\PassField;
use Espo\Modules\WalletPasses\Core\Model\PassStatus;
use Espo\Modules\WalletPasses\Core\Model\PassType;
use Espo\Modules\WalletPasses\Core\Util\Placeholder;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * Converts EspoCRM records (WalletPass + WalletPassTemplate + Contact/Account/Lead) into a PassDefinition.
 *
 * Placeholders available in template values / barcode message:
 *   {pass.<attribute>}      e.g. {pass.serialNumber}, {pass.holderName}, {pass.points}, {pass.expiresAt}
 *   {contact.<attribute>}   e.g. {contact.firstName}, {contact.name}, {contact.emailAddress}
 *   {account.<attribute>}, {lead.<attribute>}, {template.<attribute>}
 */
class PassDefinitionFactory
{
    private const MAX_IMAGE_SIZE = 2 * 1024 * 1024;

    public function __construct(
        private EntityManager $entityManager,
        private FileStorageManager $fileStorageManager,
        private PassLinks $links,
        private Config $config,
    ) {
    }

    public function create(WalletPass $pass, bool $withImages = true): PassDefinition
    {
        $template = $this->getTemplate($pass);

        $values = $this->buildPlaceholderValues($pass, $template);

        $barcodeMessage = $this->barcodeTemplate($pass, $template);

        return new PassDefinition(
            templateId: (string) $template->getId(),
            passType: PassType::fromString($template->getPassType()),
            serialNumber: $pass->getSerialNumber(),
            authenticationToken: $pass->getAuthenticationToken(),
            organizationName: Placeholder::render((string) $template->get('organizationName'), $values),
            description: Placeholder::render((string) $template->get('description'), $values),
            logoText: $template->get('logoText') ? Placeholder::render($template->get('logoText'), $values) : null,
            backgroundColor: $template->get('backgroundColor'),
            foregroundColor: $template->get('foregroundColor'),
            labelColor: $template->get('labelColor'),
            barcodeFormat: BarcodeFormat::fromStringOrDefault($template->get('barcodeFormat')),
            barcodeMessage: Placeholder::render($barcodeMessage, $values),
            barcodeAltText: $template->get('barcodeAltText') ?
                Placeholder::render($template->get('barcodeAltText'), $values) : null,
            fields: $this->buildFields($template, $values),
            status: PassStatus::fromStringOrDefault($pass->getStatus()),
            expiresAt: $this->toDateTime($pass->get('expiresAt')),
            relevantDate: $this->toDateTime($template->get('relevantDate')),
            updatedAt: (new DateTimeImmutable())->setTimestamp($pass->getContentUpdatedTimestamp() ?: time()),
            holderName: $pass->get('holderName') ?: null,
            images: $withImages ? $this->loadImages($template) : [],
            imageUrls: $this->buildImageUrls($template),
        );
    }

    /**
     * Normalized data used by the HTML preview (template only or issued pass).
     *
     * @return array<string, mixed>
     */
    public function preview(?WalletPass $pass, WalletPassTemplate $template): array
    {
        if ($pass === null) {
            $pass = $this->entityManager->getNewEntity(WalletPass::ENTITY_TYPE);
            assert($pass instanceof WalletPass);

            $pass->set([
                'serialNumber' => 'PREVIEW0001',
                'authenticationToken' => 'preview',
                'holderName' => 'Jane Doe',
                'points' => 120,
                'status' => WalletPass::STATUS_ACTIVE,
                'templateId' => $template->getId(),
            ]);
        }

        $values = $this->buildPlaceholderValues($pass, $template);
        $barcodeMessage = $this->barcodeTemplate($pass, $template);

        $images = [];

        foreach (WalletPassTemplate::IMAGE_FIELD_LIST as $field) {
            $id = $template->getImageId($field);
            $images[$field] = $id ? '?entryPoint=image&size=large&id=' . rawurlencode($id) : null;
        }

        $fields = array_map(fn (PassField $f) => [
            'key' => $f->key,
            'label' => $f->label,
            'value' => $f->value,
            'section' => $f->section,
            'textAlignment' => $f->textAlignment,
        ], $this->buildFields($template, $values));

        return [
            'passType' => $template->getPassType(),
            'appleStyle' => PassType::fromString($template->getPassType())->appleStyle(),
            'organizationName' => Placeholder::render((string) $template->get('organizationName'), $values),
            'description' => Placeholder::render((string) $template->get('description'), $values),
            'logoText' => Placeholder::render((string) $template->get('logoText'), $values),
            'backgroundColor' => $template->get('backgroundColor'),
            'foregroundColor' => $template->get('foregroundColor'),
            'labelColor' => $template->get('labelColor'),
            'barcodeFormat' => $template->get('barcodeFormat') ?: 'QR',
            'barcodeMessage' => Placeholder::render($barcodeMessage, $values),
            'barcodeAltText' => Placeholder::render((string) $template->get('barcodeAltText'), $values),
            'status' => $pass->getStatus(),
            'expiresAt' => $pass->get('expiresAt'),
            'fields' => $fields,
            'images' => $images,
        ];
    }

    public function getTemplate(WalletPass $pass): WalletPassTemplate
    {
        $templateId = $pass->getTemplateId();
        $template = $templateId ?
            $this->entityManager->getEntityById(WalletPassTemplate::ENTITY_TYPE, $templateId) : null;

        if (!$template instanceof WalletPassTemplate) {
            throw new WalletException('The pass has no valid template.');
        }

        return $template;
    }

    private function barcodeTemplate(WalletPass $pass, WalletPassTemplate $template): string
    {
        return (string) ($pass->get('barcodeValue') ?: $template->get('barcodeMessage') ?: '{pass.serialNumber}');
    }

    /**
     * @return PassField[]
     */
    private function buildFields(WalletPassTemplate $template, array $values): array
    {
        $fields = [];
        $index = 0;

        $sources = ['frontFields' => PassField::SECTION_SECONDARY, 'backFields' => PassField::SECTION_BACK];

        foreach ($sources as $attr => $default) {
            foreach ($template->getFieldList($attr) as $raw) {
                if ($attr === 'backFields') {
                    $raw['section'] = PassField::SECTION_BACK;
                } elseif (($raw['section'] ?? null) === PassField::SECTION_BACK) {
                    $raw['section'] = $default;
                }

                $field = PassField::fromArray($raw, $default, ++$index);
                $fields[] = $field->withValue(Placeholder::render($field->value, $values));
            }
        }

        return $fields;
    }

    /**
     * @return array<string, scalar|null>
     */
    private function buildPlaceholderValues(WalletPass $pass, WalletPassTemplate $template): array
    {
        $values = [];

        $this->addEntityValues($values, 'pass', $pass);
        $this->addEntityValues($values, 'template', $template);

        foreach (['contact' => 'Contact', 'account' => 'Account', 'lead' => 'Lead'] as $prefix => $entityType) {
            $id = $pass->get($prefix . 'Id');

            if (!$id) {
                continue;
            }

            $entity = $this->entityManager->getEntityById($entityType, $id);

            if ($entity) {
                $this->addEntityValues($values, $prefix, $entity);
            }
        }

        // Human readable dates.
        foreach (['pass.expiresAt', 'pass.issuedAt'] as $key) {
            if (!empty($values[$key])) {
                $values[$key] = $this->formatDate((string) $values[$key]);
            }
        }

        return $values;
    }

    /**
     * @param array<string, scalar|null> $values
     */
    private function addEntityValues(array &$values, string $prefix, Entity $entity): void
    {
        foreach ($entity->getAttributeList() as $attribute) {
            if ($attribute === 'authenticationToken') {
                continue;
            }

            $value = $entity->get($attribute);

            if (is_scalar($value) || $value === null) {
                $values[$prefix . '.' . $attribute] = $value;
            }
        }
    }

    /**
     * @return array<string, string>
     */
    private function loadImages(WalletPassTemplate $template): array
    {
        $images = [];

        foreach (WalletPassTemplate::IMAGE_FIELD_LIST as $field) {
            $id = $template->getImageId($field);

            if (!$id) {
                continue;
            }

            $attachment = $this->entityManager->getEntityById(Attachment::ENTITY_TYPE, $id);

            if (!$attachment instanceof Attachment) {
                continue;
            }

            try {
                $contents = $this->fileStorageManager->getContents($attachment);
            } catch (Throwable) {
                continue;
            }

            if (strlen($contents) > self::MAX_IMAGE_SIZE) {
                throw new WalletException("Image '$field' exceeds 2 MB.");
            }

            $images[$field] = $this->ensurePng($contents, $field);
        }

        return $images;
    }

    /**
     * Wallet only accepts PNG: convert JPEG/GIF/WebP uploads on the fly (GD).
     */
    private function ensurePng(string $contents, string $field): string
    {
        if (str_starts_with($contents, "\x89PNG")) {
            return $contents;
        }

        $image = @imagecreatefromstring($contents);

        if ($image === false) {
            throw new WalletException("Image '$field' is not a valid image.");
        }

        imagesavealpha($image, true);
        ob_start();
        imagepng($image);
        $png = (string) ob_get_clean();
        imagedestroy($image);

        return $png;
    }

    /**
     * @return array<string, string>
     */
    private function buildImageUrls(WalletPassTemplate $template): array
    {
        $urls = [];

        foreach (WalletPassTemplate::IMAGE_FIELD_LIST as $field) {
            $url = $this->links->imageUrl((string) $template->getId(), $field, $template->getImageId($field));

            if ($url !== null) {
                $urls[$field] = $url;
            }
        }

        return $urls;
    }

    private function toDateTime(?string $value): ?DateTimeImmutable
    {
        if (!$value) {
            return null;
        }

        return new DateTimeImmutable($value, new DateTimeZone('UTC'));
    }

    private function formatDate(string $value): string
    {
        try {
            $timeZone = new DateTimeZone((string) ($this->config->get('timeZone') ?: 'UTC'));
            $date = (new DateTimeImmutable($value, new DateTimeZone('UTC')))->setTimezone($timeZone);
        } catch (Throwable) {
            return $value;
        }

        $format = str_contains($value, ':') ? 'd/m/Y H:i' : 'd/m/Y';

        return $date->format($format);
    }
}
