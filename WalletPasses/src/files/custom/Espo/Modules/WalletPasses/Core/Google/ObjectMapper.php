<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Google;

use DateTimeInterface;
use Espo\Modules\WalletPasses\Core\Exception\ConfigurationException;
use Espo\Modules\WalletPasses\Core\Model\PassDefinition;
use Espo\Modules\WalletPasses\Core\Model\PassField;
use Espo\Modules\WalletPasses\Core\Model\PassType;
use Espo\Modules\WalletPasses\Core\Util\Color;

/**
 * Maps a PassDefinition to Google Wallet class + object JSON for the matching vertical:
 *  generic → genericClass/genericObject, coupon → offer*, eventTicket → eventTicket*,
 *  storeCard / loyaltyCard → loyalty*.
 */
final class ObjectMapper
{
    public function __construct(private readonly GoogleConfig $config)
    {
    }

    public function classId(PassDefinition $pass): string
    {
        return $this->config->issuerId . '.tpl_' . self::sanitize($pass->templateId);
    }

    public function objectId(PassDefinition $pass): string
    {
        return $this->config->issuerId . '.' . self::sanitize($pass->serialNumber);
    }

    public function classResource(PassType $type): string
    {
        return $type->googleVertical() . 'Class';
    }

    public function objectResource(PassType $type): string
    {
        return $type->googleVertical() . 'Object';
    }

    /**
     * @return array<string, mixed>
     */
    public function buildClass(PassDefinition $pass): array
    {
        $class = ['id' => $this->classId($pass)];
        $color = Color::normalizeHex($pass->backgroundColor);
        $issuerName = $this->truncate($pass->organizationName, 20);
        $logo = $this->image($pass->imageUrls['logo'] ?? null);
        $hero = $this->image($pass->imageUrls['strip'] ?? $pass->imageUrls['background'] ?? null);

        switch ($pass->passType) {
            case PassType::Generic:
                break;

            case PassType::LoyaltyCard:
            case PassType::StoreCard:
                if ($logo === null) {
                    throw new ConfigurationException(
                        'Google loyalty passes require a logo reachable through a public HTTPS URL.'
                    );
                }

                $class += [
                    'issuerName' => $issuerName,
                    'programName' => $this->truncate($pass->description ?: $pass->organizationName, 40),
                    'programLogo' => $logo,
                    'reviewStatus' => 'UNDER_REVIEW',
                ];
                break;

            case PassType::Coupon:
                $class += [
                    'issuerName' => $issuerName,
                    'provider' => $pass->organizationName,
                    'title' => $pass->description ?: $pass->organizationName,
                    'redemptionChannel' => 'BOTH',
                    'reviewStatus' => 'UNDER_REVIEW',
                ];

                if ($logo !== null) {
                    $class['titleImage'] = $logo;
                }
                break;

            case PassType::EventTicket:
                $class += [
                    'issuerName' => $issuerName,
                    'eventName' => $this->localized($pass->description ?: $pass->organizationName),
                    'reviewStatus' => 'UNDER_REVIEW',
                ];

                if ($logo !== null) {
                    $class['logo'] = $logo;
                }
                break;
        }

        if ($pass->passType !== PassType::Generic) {
            if ($color !== null) {
                $class['hexBackgroundColor'] = $color;
            }

            if ($hero !== null) {
                $class['heroImage'] = $hero;
            }
        }

        return $class;
    }

    /**
     * @return array<string, mixed>
     */
    public function buildObject(PassDefinition $pass): array
    {
        $object = [
            'id' => $this->objectId($pass),
            'classId' => $this->classId($pass),
            'state' => $pass->status->googleState(),
        ];

        if ($pass->barcodeMessage !== '') {
            $object['barcode'] = array_filter([
                'type' => $pass->barcodeFormat->google(),
                'value' => $pass->barcodeMessage,
                'alternateText' => $pass->barcodeAltText,
            ], fn ($v) => $v !== null && $v !== '');
        }

        $modules = [];

        foreach ($pass->fields as $index => $field) {
            if ($field->value === '') {
                continue;
            }

            $modules[] = [
                'id' => self::sanitize($field->key) ?: 'f' . $index,
                'header' => $field->label !== '' ? $field->label : ' ',
                'body' => $field->value,
            ];
        }

        if ($modules !== []) {
            $object['textModulesData'] = array_slice($modules, 0, 10);
        }

        if ($pass->expiresAt !== null) {
            $object['validTimeInterval'] = [
                'end' => ['date' => $pass->expiresAt->format(DateTimeInterface::ATOM)],
            ];
        }

        $primary = $pass->fieldsInSection(PassField::SECTION_PRIMARY)[0] ?? null;

        switch ($pass->passType) {
            case PassType::Generic:
                $object['cardTitle'] = $this->localized($pass->organizationName);
                $object['header'] = $this->localized(
                    $primary?->value ?: ($pass->holderName ?: ($pass->description ?: $pass->serialNumber))
                );

                if ($primary !== null && $primary->label !== '') {
                    $object['subheader'] = $this->localized($primary->label);
                }

                $color = Color::normalizeHex($pass->backgroundColor);

                if ($color !== null) {
                    $object['hexBackgroundColor'] = $color;
                }

                if ($logo = $this->image($pass->imageUrls['logo'] ?? null)) {
                    $object['logo'] = $logo;
                }

                if ($hero = $this->image($pass->imageUrls['strip'] ?? $pass->imageUrls['background'] ?? null)) {
                    $object['heroImage'] = $hero;
                }
                break;

            case PassType::LoyaltyCard:
            case PassType::StoreCard:
                $object['accountId'] = $pass->serialNumber;

                if ($pass->holderName) {
                    $object['accountName'] = $pass->holderName;
                }
                break;

            case PassType::EventTicket:
                if ($pass->holderName) {
                    $object['ticketHolderName'] = $pass->holderName;
                }
                break;

            case PassType::Coupon:
                break;
        }

        return $object;
    }

    public static function sanitize(string $value): string
    {
        return (string) preg_replace('/[^A-Za-z0-9._-]/', '_', $value);
    }

    /**
     * @return array{defaultValue: array{language: string, value: string}}
     */
    private function localized(string $value): array
    {
        return ['defaultValue' => ['language' => $this->config->language, 'value' => $value]];
    }

    /**
     * @return array{sourceUri: array{uri: string}}|null
     */
    private function image(?string $url): ?array
    {
        if ($url === null || !str_starts_with($url, 'https://')) {
            return null;
        }

        return ['sourceUri' => ['uri' => $url]];
    }

    private function truncate(string $value, int $length): string
    {
        return mb_substr($value, 0, $length);
    }
}
