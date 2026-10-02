/**
 * Side panel: Wallet-style preview. Works on WalletPass (server-rendered values)
 * and on WalletPassTemplate (live, from the model being edited).
 */
define('wallet-passes:views/wallet-pass/panels/preview',
    ['view', 'wallet-passes:preview-renderer'], (View, Renderer) => {

    return class extends View {

        templateContent = '<div class="wallet-preview-container">{{{previewHtml}}}</div>'

        previewData = null

        data() {
            if (!this.previewData) {
                const message = this.translate('previewError', 'messages', 'WalletPass');

                return {previewHtml: `<div class="text-muted">${this.escapeString(message)}</div>`};
            }

            return {
                previewHtml: Renderer.render(this.previewData, s => this.translate(s, 'labels', 'WalletPass')),
            };
        }

        setup() {
            this.isTemplate = this.model.entityType === 'WalletPassTemplate';

            if (this.isTemplate) {
                this.previewData = Renderer.fromTemplateModel(this.model);

                this.listenTo(this.model, 'change', () => {
                    this.previewData = Renderer.fromTemplateModel(this.model);

                    if (this.isRendered()) {
                        this.reRender();
                    }
                });

                return;
            }

            // Render only once the server-side preview is loaded (no race with the first render).
            this.wait(this.fetchPreview());

            this.listenTo(this.model, 'sync', () => {
                this.fetchPreview().then(() => this.isRendered() && this.reRender());
            });
        }

        /**
         * @returns {Promise}
         */
        fetchPreview() {
            if (!this.model.id) {
                return Promise.resolve();
            }

            return Espo.Ajax.getRequest(`WalletPasses/pass/${encodeURIComponent(this.model.id)}/preview`)
                .then(data => this.previewData = data)
                .catch(() => this.previewData = null);
        }

        afterRender() {
            if (this.previewData) {
                Renderer.drawBarcode(this.$el.get(0), this.previewData);
            }
        }
    };
});
