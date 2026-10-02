/**
 * Detail view actions of WalletPass: links modal, .pkpass download, Google link copy, forced push.
 */
define('wallet-passes:handlers/wallet-pass/detail-actions', ['action-handler'], (ActionHandler) => {

    return class extends ActionHandler {

        showLinks() {
            this.view.createView('walletLinks', 'wallet-passes:views/wallet-pass/modals/links', {
                model: this.view.model,
            }, view => view.render());
        }

        downloadPkpass() {
            const link = this.view.model.get('walletLink');

            if (!link) {
                Espo.Ui.error(this.view.translate('appleNotConfigured', 'messages', 'WalletPass'));

                return;
            }

            // Signed public link forced to the Apple platform: no session cookie needed for the download.
            window.location.href = link + '&p=apple';
        }

        copyGoogleLink() {
            Espo.Ui.notify(' ... ');

            this.fetchLinks().then(links => {
                Espo.Ui.notify(false);

                if (!links.googleUrl) {
                    Espo.Ui.error(links.googleError || this.view.translate('googleNotConfigured', 'messages', 'WalletPass'));

                    return;
                }

                navigator.clipboard.writeText(links.googleUrl)
                    .then(() => Espo.Ui.success(this.view.translate('linkCopied', 'messages', 'WalletPass')));
            });
        }

        pushUpdate() {
            Espo.Ui.notify(' ... ');

            Espo.Ajax.postRequest(`WalletPasses/pass/${encodeURIComponent(this.view.model.id)}/push`)
                .then(result => {
                    result.success ?
                        Espo.Ui.success(this.view.translate('pushDone', 'messages', 'WalletPass')) :
                        Espo.Ui.warning(this.view.translate('pushPartial', 'messages', 'WalletPass'));

                    this.view.model.fetch();
                });
        }

        // noinspection JSUnusedGlobalSymbols
        isEditAllowed() {
            return this.view.getAcl().check(this.view.model, 'edit');
        }

        fetchLinks() {
            return Espo.Ajax.postRequest(`WalletPasses/pass/${encodeURIComponent(this.view.model.id)}/links`);
        }
    };
});
