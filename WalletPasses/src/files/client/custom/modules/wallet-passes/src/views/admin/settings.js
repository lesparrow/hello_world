/**
 * Administration → Wallet Passes → Wallet Settings.
 * Standard settings record (config params) + "Test configuration" button.
 */
define('wallet-passes:views/admin/settings', ['views/settings/record/edit'], (SettingsEditRecordView) => {

    return class extends SettingsEditRecordView {

        layoutName = 'walletPassesSettings'

        saveAndContinueEditingAction = false

        setup() {
            super.setup();

            this.addButton({
                name: 'walletTest',
                label: this.translate('Test Configuration', 'labels', 'Settings'),
                style: 'default',
            });

            this.controlVisibility();
            this.listenTo(this.model, 'change:walletAppleEnabled change:walletGoogleEnabled', () => this.controlVisibility());
        }

        controlVisibility() {
            const apple = ['walletApplePushEnabled', 'walletAppleTeamId', 'walletApplePassTypeId',
                'walletAppleCertificate', 'walletAppleWwdr', 'walletAppleWebServiceUrl', 'walletApplePushType'];
            const google = ['walletGoogleIssuerId', 'walletGoogleServiceAccount', 'walletGoogleOrigins',
                'walletGoogleLanguage'];

            apple.forEach(f => this.model.get('walletAppleEnabled') ? this.showField(f) : this.hideField(f));
            google.forEach(f => this.model.get('walletGoogleEnabled') ? this.showField(f) : this.hideField(f));

            this.model.get('walletAppleEnabled') ?
                this.setFieldRequired('walletAppleTeamId') : this.setFieldNotRequired('walletAppleTeamId');
            this.model.get('walletAppleEnabled') ?
                this.setFieldRequired('walletApplePassTypeId') : this.setFieldNotRequired('walletApplePassTypeId');
            this.model.get('walletGoogleEnabled') ?
                this.setFieldRequired('walletGoogleIssuerId') : this.setFieldNotRequired('walletGoogleIssuerId');
        }

        // noinspection JSUnusedGlobalSymbols
        actionWalletTest() {
            if (this.isChanged) {
                Espo.Ui.warning(this.translate('walletSaveFirst', 'messages', 'Settings'));

                return;
            }

            Espo.Ui.notify(' ... ');

            Espo.Ajax.postRequest('WalletPasses/settings/test', {}, {timeout: 60000}).then(result => {
                Espo.Ui.notify(false);

                this.createView('walletTestResult', 'wallet-passes:views/admin/modals/test-result', {
                    report: result.report,
                }, view => view.render());
            });
        }
    };
});
