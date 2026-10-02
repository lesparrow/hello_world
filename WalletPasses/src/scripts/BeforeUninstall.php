<?php

declare(strict_types=1);

use Espo\Core\Container;
use Espo\Core\InjectableFactory;
use Espo\Core\Utils\Config;
use Espo\Core\Utils\Config\ConfigWriter;
use Espo\ORM\EntityManager;

/**
 * Removes scheduled jobs and navigation entries. Business data (passes, templates, logs) and
 * credentials in data/wallet-passes/ are kept so a re-install restores the service; delete that
 * directory and the wallet_* tables manually for a full purge (see README).
 */
// phpcs:ignore PSR1.Classes.ClassDeclaration.MissingNamespace -- EspoCRM loads extension scripts by global class name.
class BeforeUninstall
{
    private const JOBS = ['WalletPassesPushPendingUpdates', 'WalletPassesExpirePasses'];
    private const SCOPES = ['WalletPass', 'WalletPassTemplate', 'WalletPassLog', 'WalletDevice'];

    /**
     * @param array<string, mixed> $params
     */
    public function run(Container $container, array $params = []): void
    {
        /** @var EntityManager $entityManager */
        $entityManager = $container->get('entityManager');
        /** @var Config $config */
        $config = $container->get('config');
        /** @var InjectableFactory $injectableFactory */
        $injectableFactory = $container->get('injectableFactory');

        foreach (self::JOBS as $job) {
            $list = $entityManager
                ->getRDBRepository('ScheduledJob')
                ->where(['job' => $job])
                ->find();

            foreach ($list as $scheduledJob) {
                $entityManager->removeEntity($scheduledJob);
            }
        }

        $configWriter = $injectableFactory->create(ConfigWriter::class);

        foreach (['tabList', 'quickCreateList', 'globalSearchEntityList'] as $param) {
            $list = $config->get($param);

            if (!is_array($list)) {
                continue;
            }

            $filtered = array_values(array_filter(
                $list,
                fn ($item) => !(is_string($item) && in_array($item, self::SCOPES, true))
            ));

            if ($filtered !== $list) {
                $configWriter->set($param, $filtered);
            }
        }

        $configWriter->save();
    }
}
