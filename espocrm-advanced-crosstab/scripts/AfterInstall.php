<?php

use Espo\Core\Container;
use Espo\Core\Utils\Config\ConfigWriter;

class AfterInstall
{
    public function run(Container $container): void
    {
        $config = $container->get('config');
        $tabList = $config->get('tabList') ?? [];

        if (!in_array('AdvancedCrosstab', $tabList, true)) {
            $tabList[] = 'AdvancedCrosstab';

            $configWriter = $container->get('injectableFactory')->create(ConfigWriter::class);
            $configWriter->set('tabList', $tabList);
            $configWriter->save();
        }

        $container->get('dataManager')->clearCache();
    }
}
