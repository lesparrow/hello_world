define('advanced-crosstab:views/dashlets/advanced-crosstab', ['views/dashlets/abstract/base', 'advanced-crosstab:lib/styles'], function (BaseDashletView, Styles) {

    /**
     * Dashboard panel showing a saved crosstab as a table, a chart or KPI cards.
     * Data is computed for the viewing user (their ACL), never the report author's.
     */
    return class extends BaseDashletView {

        name = 'AdvancedCrosstab'

        templateContent = `<div class="acx-dashlet-body" data-role="body"></div>`

        setup() {
            Styles.ensure();
        }

        setupActionList() {
            if (this.getOption('reportId')) {
                this.actionList.unshift({
                    name: 'openReport',
                    label: 'Open',
                    iconClass: 'fas fa-external-link-alt',
                    onClick: () => this.getRouter().navigate('#AdvancedCrosstab/view/' + this.getOption('reportId'), {trigger: true}),
                });
            }
        }

        afterAdding() {
            this.getContainerView().actionOptions();
        }

        afterRender() {
            const body = this.element.querySelector('[data-role="body"]');
            const reportId = this.getOption('reportId');

            if (!reportId) {
                body.innerHTML = `<div class="text-muted acx-empty">${this.escapeString(this.translate('selectReport', 'messages', 'AdvancedCrosstab'))}</div>`;

                return;
            }

            body.innerHTML = '<div class="text-muted acx-empty"><span class="fas fa-spinner fa-spin"></span></div>';

            Espo.Ajax.postRequest(`AdvancedCrosstab/${reportId}/run`, {})
                .then(result => {
                    if (!this.element) {
                        return;
                    }

                    const view = result.view || {};
                    const mode = this.getOption('displayMode') || view.mode || 'table';

                    this.createView('result', 'advanced-crosstab:views/advanced-crosstab/result/panel', {
                        selector: '[data-role="body"]',
                        result: result,
                        mode: mode,
                        chartType: view.chartType,
                        chartMeasure: view.chartMeasure,
                        source: {id: reportId},
                        height: body.clientHeight,
                    }).then(panel => panel.render());
                })
                .catch(xhr => {
                    if (xhr && xhr.status === 403) {
                        xhr.errorIsHandled = true;
                        body.innerHTML = `<div class="text-muted acx-empty">${this.escapeString(this.translate('Access denied'))}</div>`;
                    }
                });
        }
    };
});
