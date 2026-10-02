<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\Tools;

use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Modules\WalletPasses\Core\Apple\PkpassGenerator;
use Espo\Modules\WalletPasses\Core\Google\GoogleWalletService;
use Espo\Modules\WalletPasses\Core\Util\QrCode;
use Espo\Modules\WalletPasses\Core\Util\UserAgent;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassLog;
use Espo\ORM\EntityManager;
use Throwable;

/**
 * High level operations on an issued pass: .pkpass rendering, Google synchronisation, links, scans.
 */
class WalletPassService
{
    private ?GoogleWalletService $google = null;

    public function __construct(
        private EntityManager $entityManager,
        private WalletSettings $settings,
        private PassDefinitionFactory $definitionFactory,
        private PassLinks $links,
        private PassLogger $logger,
        private HttpClientFactory $httpClientFactory,
    ) {
    }

    public function renderPkpass(WalletPass $pass): string
    {
        $definition = $this->definitionFactory->create($pass);

        return (new PkpassGenerator())->generate($definition, $this->settings->getAppleConfig());
    }

    public function pkpassFileName(WalletPass $pass): string
    {
        return preg_replace('/[^A-Za-z0-9_-]/', '_', $pass->getSerialNumber()) . '.pkpass';
    }

    /**
     * Creates or updates the Google class + object; stores the result on the pass (without hooks).
     */
    public function syncGoogle(WalletPass $pass): void
    {
        $definition = $this->definitionFactory->create($pass, false);

        try {
            $ids = $this->getGoogle()->sync($definition);
        } catch (Throwable $e) {
            $this->updateSilently($pass, ['googleSyncError' => $e->getMessage()]);
            $this->logger->log(WalletPassLog::EVENT_GOOGLE_ERROR, $pass->getId(), $e->getMessage());

            throw $e;
        }

        $this->updateSilently($pass, [
            'googleObjectId' => $ids['objectId'],
            'googleSyncedAt' => DateTimeUtil::getSystemNowString(),
            'googleSyncError' => null,
        ]);

        $template = $this->definitionFactory->getTemplate($pass);

        if ($template->get('googleClassId') !== $ids['classId']) {
            $template->set('googleClassId', $ids['classId']);
            $this->entityManager->saveEntity($template, ['skipHooks' => true, 'silent' => true]);
        }

        $this->logger->log(WalletPassLog::EVENT_GOOGLE_SYNCED, $pass->getId(), $ids['objectId']);
    }

    /**
     * Returns the Google "Save to Wallet" URL, synchronising the object first if needed.
     */
    public function getGoogleSaveLink(WalletPass $pass, bool $forceSync = false): string
    {
        if ($forceSync || !$pass->getGoogleObjectId() || $pass->get('pushPending')) {
            $this->syncGoogle($pass);
        }

        return $this->getGoogle()->saveLink($this->definitionFactory->create($pass, false));
    }

    /**
     * Links shown by the "Wallet Links" button.
     *
     * @return array<string, mixed>
     */
    public function getLinks(WalletPass $pass): array
    {
        $serial = $pass->getSerialNumber();
        $smartLink = $this->links->smartLink($serial);

        $result = [
            'smartLink' => $smartLink,
            'appleUrl' => $this->settings->isAppleEnabled() ?
                $this->links->smartLink($serial, UserAgent::PLATFORM_APPLE) : null,
            'googleUrl' => null,
            'googleError' => null,
            'qrCodeUrl' => $this->links->qrCodeUrl($serial),
            'qrCodeDataUri' => 'data:image/png;base64,' . base64_encode(QrCode::png($smartLink)),
        ];

        if ($this->settings->isGoogleEnabled()) {
            try {
                $result['googleUrl'] = $this->getGoogleSaveLink($pass);
            } catch (Throwable $e) {
                $result['googleError'] = $e->getMessage();
            }
        }

        if ($pass->get('walletLink') !== $smartLink) {
            $this->updateSilently($pass, ['walletLink' => $smartLink]);
        }

        return $result;
    }

    /**
     * Registers a scan (by serial number or barcode value) and returns the pass.
     */
    public function registerScan(string $code): ?WalletPass
    {
        $repository = $this->entityManager->getRDBRepository(WalletPass::ENTITY_TYPE);

        $pass = $repository->where(['serialNumber' => $code])->findOne() ??
            $repository->where(['barcodeValue' => $code])->findOne();

        if (!$pass instanceof WalletPass) {
            return null;
        }

        $this->updateSilently($pass, [
            'scanCount' => (int) $pass->get('scanCount') + 1,
            'lastScannedAt' => DateTimeUtil::getSystemNowString(),
        ]);

        $this->logger->log(WalletPassLog::EVENT_SCANNED, $pass->getId(), 'Scanned: ' . $code);

        return $pass;
    }

    /**
     * Updates technical attributes without triggering hooks (no push loop, no stream note).
     *
     * @param array<string, mixed> $values
     */
    public function updateSilently(WalletPass $pass, array $values): void
    {
        $this->entityManager->getQueryExecutor()->execute(
            $this->entityManager->getQueryBuilder()
                ->update()
                ->in(WalletPass::ENTITY_TYPE)
                ->set($values)
                ->where(['id' => $pass->getId()])
                ->build()
        );

        $pass->set($values);
        $pass->setAsFetched();
    }

    private function getGoogle(): GoogleWalletService
    {
        return $this->google ??= new GoogleWalletService(
            $this->settings->getGoogleConfig(),
            $this->httpClientFactory->create()
        );
    }
}
