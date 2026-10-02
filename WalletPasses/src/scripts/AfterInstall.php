<?php

declare(strict_types=1);

use Espo\Core\Container;
use Espo\Core\DataManager;
use Espo\Core\Utils\Config;
use Espo\Core\Utils\Config\ConfigWriter;
use Espo\Core\InjectableFactory;
use Espo\ORM\EntityManager;

/**
 * Runs after files are copied and EspoCRM is rebuilt (tables already exist).
 */
// phpcs:ignore PSR1.Classes.ClassDeclaration.MissingNamespace -- EspoCRM loads extension scripts by global class name.
class AfterInstall
{
    private const JOBS = [
        'WalletPassesPushPendingUpdates' => ['Wallet Passes: push pending updates', '*/5 * * * *'],
        'WalletPassesExpirePasses' => ['Wallet Passes: expire passes', '15 * * * *'],
    ];

    private const TAB_LIST = ['WalletPass'];

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

        $this->createDataDirectory();
        $this->createScheduledJobs($entityManager);

        $configWriter = $injectableFactory->create(ConfigWriter::class);

        // Default values for the settings page (never overwrite an existing value on upgrade).
        $defaults = [
            'walletAppleEnabled' => false,
            'walletApplePushEnabled' => true,
            'walletGoogleEnabled' => false,
            'walletGoogleLanguage' => 'fr',
            'walletLogRetentionDays' => 180,
        ];

        foreach ($defaults as $key => $value) {
            if (!$config->has($key)) {
                $configWriter->set($key, $value);
            }
        }

        $tabList = $config->get('tabList') ?? [];

        if (empty($params['isUpgrade'])) {
            foreach (self::TAB_LIST as $scope) {
                if (!in_array($scope, $tabList, true)) {
                    $tabList[] = $scope;
                }
            }

            $configWriter->set('tabList', $tabList);
        }

        $configWriter->save();

        /** @var DataManager $dataManager */
        $dataManager = $container->get('dataManager');
        $dataManager->clearCache();
    }

    private function createDataDirectory(): void
    {
        $dir = 'data/wallet-passes';

        if (!is_dir($dir)) {
            mkdir($dir, 0700, true);
        }

        if (!is_file($dir . '/.htaccess')) {
            file_put_contents($dir . '/.htaccess', "Require all denied\nDeny from all\n");
        }
    }

    private function createScheduledJobs(EntityManager $entityManager): void
    {
        foreach (self::JOBS as $job => [$name, $scheduling]) {
            $existing = $entityManager
                ->getRDBRepository('ScheduledJob')
                ->where(['job' => $job])
                ->findOne();

            if ($existing) {
                continue;
            }

            $entityManager->createEntity('ScheduledJob', [
                'name' => $name,
                'job' => $job,
                'status' => 'Active',
                'scheduling' => $scheduling,
            ]);
        }
    }
}
