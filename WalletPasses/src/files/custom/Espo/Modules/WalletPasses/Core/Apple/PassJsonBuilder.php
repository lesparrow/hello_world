<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Core\Apple;

use DateTimeInterface;
use Espo\Modules\WalletPasses\Core\Model\PassDefinition;
use Espo\Modules\WalletPasses\Core\Model\PassField;
use Espo\Modules\WalletPasses\Core\Model\PassStatus;
use Espo\Modules\WalletPasses\Core\Util\Color;

/**
 * Builds the pass.json dictionary (Apple PassKit format version 1).
 */
final class PassJsonBuilder
{
    /**
     * @return array<string, mixed>
     */
    public function build(PassDefinition $pass, AppleConfig $config): array
    {
        $data = [
            'formatVersion' => 1,
            'passTypeIdentifier' => $config->passTypeIdentifier,
            'serialNumber' => $pass->serialNumber,
            'teamIdentifier' => $config->teamIdentifier,
            'organizationName' => $pass->organizationName,
            'description' => $pass->description !== '' ? $pass->description : $pass->organizationName,
        ];

        if ($pass->logoText !== null && $pass->logoText !== '') {
            $data['logoText'] = $pass->logoText;
        }

        foreach (
            [
                'backgroundColor' => $pass->backgroundColor,
                'foregroundColor' => $pass->foregroundColor,
                'labelColor' => $pass->labelColor,
            ] as $key => $hex
        ) {
            $rgb = Color::hexToAppleRgb($hex);

            if ($rgb !== null) {
                $data[$key] = $rgb;
            }
        }

        if ($config->webServiceUrl !== null && $config->webServiceUrl !== '') {
            $data['webServiceURL'] = rtrim($config->webServiceUrl, '/');
            $data['authenticationToken'] = $pass->authenticationToken;
        }

        if ($pass->barcodeMessage !== '') {
            $barcode = [
                'format' => $pass->barcodeFormat->apple(),
                'message' => $pass->barcodeMessage,
                'messageEncoding' => 'iso-8859-1',
            ];

            if ($pass->barcodeAltText !== null && $pass->barcodeAltText !== '') {
                $barcode['altText'] = $pass->barcodeAltText;
            }

            $data['barcodes'] = [$barcode];

            if ($pass->barcodeFormat->supportedByLegacyAppleKey()) {
                $data['barcode'] = $barcode;
            }
        }

        if ($pass->expiresAt !== null) {
            $data['expirationDate'] = $pass->expiresAt->format(DateTimeInterface::ATOM);
        }

        if ($pass->relevantDate !== null) {
            $data['relevantDate'] = $pass->relevantDate->format(DateTimeInterface::ATOM);
        }

        if ($pass->status === PassStatus::Voided) {
            $data['voided'] = true;
        }

        $data[$pass->passType->appleStyle()] = $this->buildStructure($pass);

        return $data;
    }

    /**
     * @return array<string, list<array<string, string>>>
     */
    private function buildStructure(PassDefinition $pass): array
    {
        $structure = [];
        $usedKeys = [];

        foreach (PassField::SECTION_LIST as $section) {
            $items = [];

            foreach ($pass->fieldsInSection($section) as $field) {
                $key = $field->key;

                // Keys must be unique across the whole pass.
                for ($i = 2; isset($usedKeys[$key]); $i++) {
                    $key = $field->key . '_' . $i;
                }

                $usedKeys[$key] = true;

                $item = [
                    'key' => $key,
                    'label' => $field->label,
                    'value' => $field->value,
                ];

                if ($section !== PassField::SECTION_BACK && $field->textAlignment !== 'natural') {
                    $item['textAlignment'] = $field->appleAlignment();
                }

                $items[] = $item;
            }

            if ($items !== []) {
                $structure[$section . 'Fields'] = $items;
            }
        }

        // An empty style dictionary is still required by Wallet.
        return $structure;
    }
}
