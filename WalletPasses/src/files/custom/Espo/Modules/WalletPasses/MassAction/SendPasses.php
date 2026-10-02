<?php

declare(strict_types=1);

namespace Espo\Modules\WalletPasses\MassAction;

use Espo\Core\Acl;
use Espo\Core\Exceptions\BadRequest;
use Espo\Core\Exceptions\Forbidden;
use Espo\Core\Mail\EmailSender;
use Espo\Core\MassAction\Data;
use Espo\Core\MassAction\MassAction;
use Espo\Core\MassAction\Params;
use Espo\Core\MassAction\QueryBuilder;
use Espo\Core\MassAction\Result;
use Espo\Core\Utils\DateTime as DateTimeUtil;
use Espo\Core\Utils\Log;
use Espo\Entities\Email;
use Espo\Entities\EmailTemplate;
use Espo\Modules\WalletPasses\Entities\WalletPass;
use Espo\Modules\WalletPasses\Entities\WalletPassTemplate;
use Espo\Modules\WalletPasses\Tools\PassIssuer;
use Espo\ORM\Entity;
use Espo\ORM\EntityManager;
use Espo\Tools\EmailTemplate\Data as EmailTemplateData;
use Espo\Tools\EmailTemplate\Params as EmailTemplateParams;
use Espo\Tools\EmailTemplate\Processor as EmailTemplateProcessor;
use Throwable;

/**
 * Mass action "Send Wallet passes" (Contact / Account / Lead list views).
 *
 * data: {
 *   templateId: string,            required — WalletPassTemplate
 *   emailTemplateId?: string,      optional — EmailTemplate sent to each holder; placeholders
 *                                  {WalletPass.walletLink}, {WalletPass.walletQrCodeUrl}, {WalletPass.serialNumber}
 *   skipExisting?: bool            do not issue a 2nd active pass from the same template
 * }
 *
 * The holder's "walletPassLink" (Contact) is also updated, so the link can be used in a regular
 * Campaign / Mass Email with the {Contact.walletPassLink} placeholder.
 */
class SendPasses implements MassAction
{
    public function __construct(
        private QueryBuilder $queryBuilder,
        private Acl $acl,
        private EntityManager $entityManager,
        private PassIssuer $issuer,
        private EmailSender $emailSender,
        private EmailTemplateProcessor $emailTemplateProcessor,
        private Log $log,
    ) {
    }

    public function process(Params $params, Data $data): Result
    {
        $entityType = $params->getEntityType();

        if (!isset(PassIssuer::HOLDER_LINK_MAP[$entityType])) {
            throw new BadRequest("Unsupported entity type '$entityType'.");
        }

        if (!$this->acl->checkScope(WalletPass::ENTITY_TYPE, Acl\Table::ACTION_CREATE)) {
            throw new Forbidden('No create access to WalletPass.');
        }

        $templateId = $data->get('templateId');

        if (!is_string($templateId) || $templateId === '') {
            throw new BadRequest('templateId is required.');
        }

        $template = $this->entityManager->getEntityById(WalletPassTemplate::ENTITY_TYPE, $templateId);

        if (!$template instanceof WalletPassTemplate || !$this->acl->checkEntityRead($template)) {
            throw new Forbidden('Template not accessible.');
        }

        $emailTemplate = null;
        $emailTemplateId = $data->get('emailTemplateId');

        if (is_string($emailTemplateId) && $emailTemplateId !== '') {
            $emailTemplate = $this->entityManager->getEntityById(EmailTemplate::ENTITY_TYPE, $emailTemplateId);

            if (!$emailTemplate instanceof EmailTemplate || !$this->acl->checkEntityRead($emailTemplate)) {
                throw new Forbidden('Email template not accessible.');
            }
        }

        $skipExisting = (bool) $data->get('skipExisting');
        $link = PassIssuer::HOLDER_LINK_MAP[$entityType];

        $collection = $this->entityManager
            ->getRDBRepository($entityType)
            ->clone($this->queryBuilder->build($params))
            ->sth()
            ->find();

        $ids = [];

        foreach ($collection as $holder) {
            if (!$this->acl->checkEntityRead($holder)) {
                continue;
            }

            if ($skipExisting && $this->hasActivePass($link, $holder, $templateId)) {
                continue;
            }

            try {
                $pass = $this->issuer->issue($template, $holder);
            } catch (Throwable $e) {
                $this->log->error("WalletPasses mass action: {$holder->getId()}: " . $e->getMessage());

                continue;
            }

            if ($entityType === 'Contact') {
                $this->updateHolderLink($holder, (string) $pass->get('walletLink'));
            }

            if ($emailTemplate) {
                $this->sendEmail($emailTemplate, $holder, $pass);
            }

            $ids[] = (string) $holder->getId();
        }

        return new Result(count($ids), $ids);
    }

    private function hasActivePass(string $link, Entity $holder, string $templateId): bool
    {
        return $this->entityManager
            ->getRDBRepository(WalletPass::ENTITY_TYPE)
            ->where([
                $link . 'Id' => $holder->getId(),
                'templateId' => $templateId,
                'status' => WalletPass::STATUS_ACTIVE,
            ])
            ->findOne() !== null;
    }

    private function updateHolderLink(Entity $holder, string $url): void
    {
        $this->entityManager->getQueryExecutor()->execute(
            $this->entityManager->getQueryBuilder()
                ->update()
                ->in($holder->getEntityType())
                ->set(['walletPassLink' => $url])
                ->where(['id' => $holder->getId()])
                ->build()
        );
    }

    private function sendEmail(EmailTemplate $emailTemplate, Entity $holder, WalletPass $pass): void
    {
        $address = $holder->get('emailAddress');

        if (!is_string($address) || $address === '' || $holder->get('emailAddressIsOptedOut')) {
            return;
        }

        try {
            $result = $this->emailTemplateProcessor->process(
                $emailTemplate,
                EmailTemplateParams::create()->withApplyAcl(true)->withCopyAttachments(true),
                EmailTemplateData::create()
                    ->withParent($holder)
                    ->withEmailAddress($address)
                    ->withEntityHash([
                        WalletPass::ENTITY_TYPE => $pass,
                        $holder->getEntityType() => $holder,
                    ])
            );

            $email = $this->entityManager->getNewEntity(Email::ENTITY_TYPE);
            assert($email instanceof Email);

            $email
                ->setSubject($result->getSubject())
                ->setBody($result->getBody())
                ->setIsHtml($result->isHtml())
                ->addToAddress($address);

            $email->set([
                'parentType' => $holder->getEntityType(),
                'parentId' => $holder->getId(),
                'attachmentsIds' => $result->getAttachmentIdList(),
            ]);

            $this->emailSender->create()->send($email);

            $email->set([
                'status' => Email::STATUS_SENT,
                'dateSent' => DateTimeUtil::getSystemNowString(),
            ]);

            $this->entityManager->saveEntity($email);
        } catch (Throwable $e) {
            $this->log->error("WalletPasses: e-mail to $address failed: " . $e->getMessage());
        }
    }
}
