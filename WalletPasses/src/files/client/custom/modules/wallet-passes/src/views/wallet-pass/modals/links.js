/**
 * Modal "Wallet links": smart link + QR code, Apple .pkpass link, Google "Save to Wallet" link.
 */
define('wallet-passes:views/wallet-pass/modals/links', ['views/modal'], (ModalView) => {

    return class extends ModalView {

        className = 'dialog dialog-record'

        templateContent = `
            {{#if isLoading}}<div class="text-muted">…</div>{{/if}}
            {{#unless isLoading}}
            <div class="row">
                <div class="col-sm-5 text-center">
                    <img class="wallet-links-qr" src="{{qrCodeDataUri}}" alt="QR">
                    <div class="margin-top">
                        <a class="btn btn-default btn-sm" href="{{qrCodeDataUri}}" download="{{fileName}}.png">
                            <span class="fas fa-download"></span> {{translate 'Download QR code' scope='WalletPass'}}
                        </a>
                    </div>
                </div>
                <div class="col-sm-7">
                    {{#each items}}
                    <div class="cell form-group">
                        <label class="control-label">{{label}}</label>
                        {{#if url}}
                        <div class="input-group">
                            <input class="form-control input-sm" readonly value="{{url}}">
                            <span class="input-group-btn">
                                <button class="btn btn-default btn-sm" data-action="walletCopy" data-value="{{url}}"
                                    title="{{translate 'Copy' scope='WalletPass'}}"><span class="far fa-copy"></span></button>
                                <a class="btn btn-default btn-sm" href="{{url}}" target="_blank" rel="noopener"
                                    title="{{translate 'Open' scope='WalletPass'}}"><span class="fas fa-external-link-alt"></span></a>
                            </span>
                        </div>
                        {{else}}
                        <div class="text-danger small">{{error}}</div>
                        {{/if}}
                    </div>
                    {{/each}}
                </div>
            </div>
            {{/unless}}
        `

        isLoading = true
        links = {}

        data() {
            const t = label => this.translate(label, 'labels', 'WalletPass');
            const notConfigured = t('Not configured');

            return {
                isLoading: this.isLoading,
                qrCodeDataUri: this.links.qrCodeDataUri,
                fileName: this.model.get('serialNumber'),
                items: [
                    {label: t('Smart link'), url: this.links.smartLink},
                    {label: t('Apple Wallet'), url: this.links.appleUrl, error: notConfigured},
                    {label: t('Google Wallet'), url: this.links.googleUrl, error: this.links.googleError || notConfigured},
                ],
            };
        }

        setup() {
            this.headerText = this.translate('Wallet Links', 'labels', 'WalletPass') + ' · ' + this.model.get('name');
            this.buttonList = [{name: 'cancel', label: 'Close'}];

            this.addActionHandler('walletCopy', (e, target) => {
                navigator.clipboard.writeText(target.dataset.value)
                    .then(() => Espo.Ui.success(this.translate('linkCopied', 'messages', 'WalletPass')));
            });

            this.wait(
                Espo.Ajax.postRequest(`WalletPasses/pass/${encodeURIComponent(this.model.id)}/links`)
                    .then(links => {
                        this.links = links;
                        this.isLoading = false;
                    })
            );
        }
    };
});
