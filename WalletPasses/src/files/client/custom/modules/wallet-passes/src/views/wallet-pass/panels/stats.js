/**
 * Side panel: devices, scans, pending update and QR code of the smart link.
 */
define('wallet-passes:views/wallet-pass/panels/stats', ['view'], (View) => {

    return class extends View {

        templateContent = `
            <div class="wallet-stats">
                <div class="wallet-stat">
                    <span class="wallet-stat-value">{{deviceCount}}</span>
                    <span class="wallet-stat-label">{{translate 'Registered Devices' scope='WalletPass'}}</span>
                </div>
                <div class="wallet-stat">
                    <span class="wallet-stat-value">{{scanCount}}</span>
                    <span class="wallet-stat-label">{{translate 'Scans' scope='WalletPass'}}</span>
                </div>
            </div>
            <div class="cell">
                <label class="control-label small">{{translate 'Last Scan' scope='WalletPass'}}</label>
                <div>{{#if lastScannedAt}}{{lastScannedAt}}{{else}}{{translate 'Never' scope='WalletPass'}}{{/if}}</div>
            </div>
            {{#if pushPending}}
            <div class="cell text-warning">
                <span class="fas fa-sync-alt"></span> {{translate 'Update Pending' scope='WalletPass'}}
            </div>
            {{/if}}
            {{#if walletQrCodeUrl}}
            <div class="cell wallet-stats-qr">
                <img src="{{walletQrCodeUrl}}" alt="QR" loading="lazy">
            </div>
            {{/if}}
        `

        data() {
            const lastScannedAt = this.model.get('lastScannedAt');

            return {
                deviceCount: this.model.get('deviceCount') || 0,
                scanCount: this.model.get('scanCount') || 0,
                lastScannedAt: lastScannedAt ? this.getDateTime().toDisplay(lastScannedAt) : null,
                pushPending: this.model.get('pushPending'),
                walletQrCodeUrl: this.model.get('walletQrCodeUrl'),
            };
        }

        setup() {
            this.listenTo(this.model, 'sync', () => this.isRendered() && this.reRender());
        }
    };
});
