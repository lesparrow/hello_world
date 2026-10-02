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

        $this->enableCollaborators($container);

        $container->get('dataManager')->clearCache();
    }

    /**
     * Collaborators (sharing a crosstab with users) exist since EspoCRM 9.0. They are enabled the way the Entity
     * Manager does it, so the extension still installs on EspoCRM 8.3+.
     */
    private function enableCollaborators(Container $container): void
    {
        $version = (string) $container->get('config')->get('version');

        if (!preg_match('/^\d/', $version) || version_compare($version, '9.0.0', '<')) {
            return;
        }

        $metadata = $container->get('metadata');

        if ($metadata->get(['entityDefs', 'AdvancedCrosstab', 'links', 'collaborators'])) {
            return;
        }

        $metadata->set('scopes', 'AdvancedCrosstab', ['collaborators' => true]);

        $metadata->set('entityDefs', 'AdvancedCrosstab', [
            'fields' => [
                'collaborators' => [
                    'type' => 'linkMultiple',
                    'view' => 'views/fields/collaborators',
                    'maxCount' => 50,
                ],
            ],
            'links' => [
                'collaborators' => [
                    'type' => 'hasMany',
                    'entity' => 'User',
                    'relationName' => 'entityCollaborator',
                    'layoutRelationshipsDisabled' => true,
                    'readOnly' => true,
                ],
            ],
        ]);

        $metadata->set('entityAcl', 'AdvancedCrosstab', [
            'links' => [
                'collaborators' => ['readOnly' => true],
            ],
        ]);

        $metadata->save();

        $container->get('dataManager')->rebuild(['AdvancedCrosstab']);
    }
}
