<?php

namespace Espo\Modules\AdvancedCrosstab\Jobs;

use Espo\Core\Acl;
use Espo\Core\AclManager;
use Espo\Core\Binding\BindingContainerBuilder;
use Espo\Core\InjectableFactory;
use Espo\Core\Job\Job;
use Espo\Core\Job\Job\Data;
use Espo\Core\Utils\Language;
use Espo\Entities\Notification;
use Espo\Entities\User;
use Espo\Modules\AdvancedCrosstab\Engine\Definition\DefinitionParser;
use Espo\Modules\AdvancedCrosstab\Engine\Pivot\PivotEngine;
use Espo\Modules\AdvancedCrosstab\Tools\Export\ExportService;
use Espo\ORM\EntityManager;
use RuntimeException;

/**
 * Generates a large export in the background, with the ACL of the user who requested it,
 * then notifies that user with a download link.
 */
class ExportJob implements Job
{
    public function __construct(
        private EntityManager $entityManager,
        private InjectableFactory $injectableFactory,
        private AclManager $aclManager,
        private Language $language,
    ) {}

    public function run(Data $data): void
    {
        $userId = $data->get('userId');
        $user = $userId ? $this->entityManager->getRDBRepositoryByClass(User::class)->getById($userId) : null;

        if (!$user || !$user->isActive()) {
            throw new RuntimeException("Advanced Crosstab export: user not found or inactive.");
        }

        $binding = BindingContainerBuilder::create()
            ->bindInstance(User::class, $user)
            ->bindInstance(Acl::class, $this->aclManager->createUserAcl($user))
            ->build();

        $parser = $this->injectableFactory->createWithBinding(DefinitionParser::class, $binding);
        $engine = $this->injectableFactory->createWithBinding(PivotEngine::class, $binding);
        $exportService = $this->injectableFactory->createWithBinding(ExportService::class, $binding);

        $definition = $parser->parse($data->get('definition'));
        $title = (string) $data->get('title');

        $attachmentId = $exportService->generate($engine->run($definition), (string) $data->get('format'), $title);

        $message = str_replace(
            ['{title}', '{url}'],
            [$title, '?entryPoint=download&id=' . $attachmentId],
            $this->language->translateLabel('exportReady', 'messages', 'AdvancedCrosstab')
        );

        $notification = $this->entityManager->getRDBRepositoryByClass(Notification::class)->getNew();

        $notification
            ->setType(Notification::TYPE_MESSAGE)
            ->setMessage($message)
            ->setUserId($user->getId());

        $this->entityManager->saveEntity($notification);
    }
}
