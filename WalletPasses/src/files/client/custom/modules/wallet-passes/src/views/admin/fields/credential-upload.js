/**
 * Upload widget for secret credentials (.p12, WWDR, Google service account JSON).
 * Files are sent to POST WalletPasses/settings/upload/{kind}, validated server side and stored
 * encrypted outside the web root — they never become a Settings attribute.
 */
define('wallet-passes:views/admin/fields/credential-upload', ['views/fields/base'], (BaseFieldView) => {

    return class extends BaseFieldView {

        detailTemplateContent = '<div class="wallet-credential"></div>'
        editTemplateContent = '<div class="wallet-credential"></div>'
        listTemplateContent = '<div class="wallet-credential"></div>'

        detailTemplate = 'wallet-passes:fields/wallet-field-list/detail'
        editTemplate = 'wallet-passes:fields/wallet-field-list/edit'
        listTemplate = 'wallet-passes:fields/wallet-field-list/list'

        status = null

        setup() {
            super.setup();

            const defs = this.getMetadata().get(['entityDefs', 'Settings', 'fields', this.name]) || {};

            this.kind = defs.credentialKind;
            this.accept = defs.accept || '';
            this.withPassword = !!defs.withPassword;

            this.addActionHandler('walletUpload', () => this.upload());
            this.addActionHandler('walletRemove', () => this.remove());

            this.wait(this.loadStatus());
        }

        /**
         * @returns {Promise}
         */
        loadStatus() {
            return Espo.Ajax.getRequest('WalletPasses/settings/status').then(status => {
                this.status = status[this.kind] || {uploaded: false};
            });
        }

        refreshStatus() {
            this.loadStatus().then(() => this.isRendered() && this.reRender());
        }

        afterRender() {
            super.afterRender();

            const $c = this.$el.find('.wallet-field-list-container, .wallet-credential').first();
            const t = label => this.translate(label, 'labels', 'Settings');
            const s = this.status;

            let html = '';

            if (!s) {
                html = '<span class="text-muted">…</span>';
            } else if (!s.uploaded) {
                html = `<span class="text-muted">${t('Not uploaded')}</span>`;
            } else if (s.error) {
                html = `<span class="text-danger">${this.escapeString(s.error)}</span>`;
            } else {
                html = `<span class="${s.expired ? 'text-danger' : 'text-success'}">
                        <span class="fas fa-${s.expired ? 'exclamation-triangle' : 'check'}"></span>
                        ${this.escapeString(s.subject || t('Uploaded'))}</span>` +
                    (s.validTo ? `<div class="small text-muted">${t('Expires')}: ${this.escapeString(s.validTo)}</div>` : '') +
                    (s.uid ? `<div class="small text-muted">UID: ${this.escapeString(s.uid)}</div>` : '');
            }

            html += `<div class="wallet-credential-form margin-top-sm">
                    <input type="file" class="form-control input-sm" accept="${this.escapeString(this.accept)}">
                    ${this.withPassword ?
                        `<input type="password" class="form-control input-sm margin-top-sm" autocomplete="new-password"
                            placeholder="${t('Certificate password')}">` : ''}
                    <div class="margin-top-sm">
                        <button type="button" class="btn btn-default btn-sm" data-action="walletUpload">
                            <span class="fas fa-upload"></span> ${s && s.uploaded ? t('Replace') : t('Upload')}
                        </button>
                        ${s && s.uploaded ?
                            `<button type="button" class="btn btn-link btn-sm text-danger" data-action="walletRemove">
                                ${t('Remove')}</button>` : ''}
                    </div>
                </div>`;

            $c.html(html);
        }

        upload() {
            const input = this.$el.find('input[type="file"]').get(0);
            const file = input && input.files[0];

            if (!file) {
                return;
            }

            const reader = new FileReader();

            reader.onload = () => {
                const base64 = String(reader.result).split(',')[1] || '';
                const password = this.$el.find('input[type="password"]').val() || '';

                Espo.Ui.notify(' ... ');

                Espo.Ajax.postRequest(`WalletPasses/settings/upload/${this.kind}`, {
                    contents: base64,
                    password: password,
                }).then(() => {
                    Espo.Ui.success(this.translate('walletUploaded', 'messages', 'Settings'));
                    this.refreshStatus();
                });
            };

            reader.readAsDataURL(file);
        }

        remove() {
            this.confirm(this.translate('removeRecordConfirmation', 'messages'), () => {
                Espo.Ajax.postRequest(`WalletPasses/settings/upload/${this.kind}`, {delete: true}).then(() => {
                    Espo.Ui.success(this.translate('walletRemoved', 'messages', 'Settings'));
                    this.refreshStatus();
                });
            });
        }

        fetch() {
            return {};
        }

        validate() {
            return false;
        }
    };
});
