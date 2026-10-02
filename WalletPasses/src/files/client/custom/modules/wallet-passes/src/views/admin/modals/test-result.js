define('wallet-passes:views/admin/modals/test-result', ['views/modal'], (ModalView) => {

    return class extends ModalView {

        templateContent = `
            <p class="{{#if allOk}}text-success{{else}}text-danger{{/if}}">
                {{#if allOk}}{{translate 'walletTestOk' category='messages' scope='Settings'}}
                {{else}}{{translate 'walletTestFailed' category='messages' scope='Settings'}}{{/if}}
            </p>
            <table class="table table-bordered-inside table-condensed">
                {{#each report}}
                <tr>
                    <td style="width: 24px;">
                        {{#if ok}}<span class="fas fa-check text-success"></span>
                        {{else}}<span class="fas fa-times text-danger"></span>{{/if}}
                    </td>
                    <td class="text-muted small" style="width: 110px;">{{section}}</td>
                    <td>{{check}}</td>
                    <td class="small" style="word-break: break-word;">{{message}}</td>
                </tr>
                {{/each}}
            </table>
        `

        data() {
            const report = this.options.report || [];

            return {
                report: report,
                allOk: report.every(item => item.ok || item.check === 'Enabled'),
            };
        }

        setup() {
            this.headerText = this.translate('Test Configuration', 'labels', 'Settings');
            this.buttonList = [{name: 'cancel', label: 'Close'}];
        }
    };
});
