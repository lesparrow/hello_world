/**
 * Bottom panel on Contact / Account / Lead: passes of the record with their Wallet link and QR code.
 */
define('wallet-passes:views/wallet-pass/panels/related-passes', ['view'], (View) => {

    const linkMap = {Contact: 'contactId', Account: 'accountId', Lead: 'leadId'};

    return class extends View {

        templateContent = `
            {{#if isLoading}}<div class="text-muted">…</div>{{/if}}
            {{#unless isLoading}}
                {{#if list.length}}
                <table class="table table-bordered-inside no-margin wallet-related-passes">
                    <tbody>
                    {{#each list}}
                        <tr>
                            <td>
                                <a href="#WalletPass/view/{{id}}">{{name}}</a>
                                <div class="small text-muted">{{templateName}} · {{statusLabel}}</div>
                            </td>
                            <td class="wallet-link-cell">
                                {{#if walletLink}}
                                <a href="{{walletLink}}" target="_blank" rel="noopener">{{walletLink}}</a>
                                <button class="btn btn-link btn-sm" data-action="walletCopy" data-value="{{walletLink}}"
                                    title="{{translate 'Copy' scope='WalletPass'}}"><span class="far fa-copy"></span></button>
                                {{/if}}
                            </td>
                            <td style="width: 90px;">
                                {{#if walletQrCodeUrl}}
                                <a href="{{walletQrCodeUrl}}" target="_blank" rel="noopener">
                                    <img src="{{walletQrCodeUrl}}&size=128" width="64" height="64" alt="QR" loading="lazy">
                                </a>
                                {{/if}}
                            </td>
                        </tr>
                    {{/each}}
                    </tbody>
                </table>
                {{else}}
                <div class="text-muted">{{translate 'No Data'}}</div>
                {{/if}}
            {{/unless}}
        `

        isLoading = true
        list = []

        data() {
            return {
                isLoading: this.isLoading,
                list: this.list.map(item => ({
                    ...item,
                    statusLabel: this.getLanguage().translateOption(item.status, 'status', 'WalletPass'),
                })),
            };
        }

        setup() {
            this.addActionHandler('walletCopy', (e, target) => {
                navigator.clipboard.writeText(target.dataset.value)
                    .then(() => Espo.Ui.success(this.translate('linkCopied', 'messages', 'WalletPass')));
            });

            this.wait(this.load());

            this.listenTo(this.model, 'after:relate after:unrelate', () => {
                this.load().then(() => this.isRendered() && this.reRender());
            });
        }

        /**
         * @returns {Promise}
         */
        load() {
            const attribute = linkMap[this.model.entityType];

            if (!attribute || !this.getAcl().checkScope('WalletPass', 'read')) {
                this.isLoading = false;

                return Promise.resolve();
            }

            return Espo.Ajax.getRequest('WalletPass', {
                select: 'id,name,status,templateName,templateId,walletLink,walletQrCodeUrl',
                maxSize: 20,
                orderBy: 'createdAt',
                order: 'desc',
                where: [{type: 'equals', attribute: attribute, value: this.model.id}],
            }).then(response => {
                this.isLoading = false;
                this.list = response.list || [];
            }).catch(() => this.isLoading = false);
        }
    };
});
