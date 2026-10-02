/**
 * Modal of the "Send Wallet passes" mass action: pass template + optional e-mail template.
 */
define('wallet-passes:views/wallet-pass/modals/send-passes', ['views/modal', 'model'], (ModalView, Model) => {

    return class extends ModalView {

        className = 'dialog dialog-record'

        templateContent = `
            <div class="panel panel-default no-side-margin"><div class="panel-body">
                <div class="cell form-group" data-name="template">
                    <label class="control-label">{{translate 'Pass Template'}} *</label>
                    <div class="field" data-name="template">{{{templateField}}}</div>
                </div>
                <div class="cell form-group" data-name="emailTemplate">
                    <label class="control-label">{{translate 'Email Template'}}</label>
                    <div class="field" data-name="emailTemplate">{{{emailTemplateField}}}</div>
                    <p class="small text-muted margin-top-sm">{{translate 'walletEmailHint' category='messages'}}</p>
                </div>
                <div class="cell form-group" data-name="skipExisting">
                    <div class="field" data-name="skipExisting">{{{skipExistingField}}}</div>
                    <span class="small">{{translate 'Skip holders who already have an active pass'}}</span>
                </div>
            </div></div>
        `

        setup() {
            this.headerText = this.translate('Send Wallet passes');

            this.buttonList = [
                {name: 'send', label: 'Send', style: 'danger'},
                {name: 'cancel', label: 'Cancel'},
            ];

            this.formModel = new Model();
            this.formModel.set({skipExisting: true});

            this.createView('templateField', 'views/fields/link', {
                selector: '.field[data-name="template"]',
                model: this.formModel,
                mode: 'edit',
                foreignScope: 'WalletPassTemplate',
                defs: {name: 'template', params: {required: true}},
            });

            this.createView('emailTemplateField', 'views/fields/link', {
                selector: '.field[data-name="emailTemplate"]',
                model: this.formModel,
                mode: 'edit',
                foreignScope: 'EmailTemplate',
                defs: {name: 'emailTemplate'},
            });

            this.createView('skipExistingField', 'views/fields/bool', {
                selector: '.field[data-name="skipExisting"]',
                model: this.formModel,
                mode: 'edit',
                defs: {name: 'skipExisting'},
            });
        }

        // noinspection JSUnusedGlobalSymbols
        actionSend() {
            ['templateField', 'emailTemplateField', 'skipExistingField'].forEach(key => {
                this.formModel.set(this.getView(key).fetch());
            });

            const templateId = this.formModel.get('templateId');

            if (!templateId) {
                Espo.Ui.error(this.translate('walletTemplateRequired', 'messages'));

                return;
            }

            this.disableButton('send');
            Espo.Ui.notify(' ... ');

            Espo.Ajax.postRequest('MassAction', {
                entityType: this.options.entityType,
                action: 'walletSendPasses',
                params: this.options.params,
                data: {
                    templateId: templateId,
                    emailTemplateId: this.formModel.get('emailTemplateId') || null,
                    skipExisting: !!this.formModel.get('skipExisting'),
                },
            }, {timeout: 0}).then(result => {
                const count = result.count ?? 0;

                Espo.Ui.success(this.translate('walletPassesIssued', 'messages').replace('{count}', count));
                this.trigger('done');
                this.close();
            }).catch(() => this.enableButton('send'));
        }
    };
});
