<?php

use Espo\Core\Container;
use Espo\Core\Utils\Config\ConfigWriter;

class AfterUninstall
{
    public function run(Container $container): void
    {
        $config = $container->get('config');

        $tabList = array_values(array_filter(
            $config->get('tabList') ?? [],
            fn ($item) => $item !== 'AdvancedCrosstab'
        ));

        $configWriter = $container->get('injectableFactory')->create(ConfigWriter::class);
        $configWriter->set('tabList', $tabList);
        $configWriter->save();

        $container->get('dataManager')->clearCache();
    }
}
