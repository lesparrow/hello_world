define('advanced-crosstab:views/advanced-crosstab/result/panel', ['view', 'advanced-crosstab:lib/formatter'], function (View, Formatter) {

    /**
     * Displays one crosstab result as a table, a chart or KPI cards, without re-querying when switching,
     * and opens drill-downs.
     *
     * Options:
     * - result
     * - mode: 'table' | 'chart' | 'kpi'
     * - chartType, chartMeasure, kpiMeasures
     * - source: {id} or {definition} — identifies the crosstab for drill-down
     * - drillDown: bool
     * - height: available height (dashlets)
     */
    return class extends View {

        templateContent = `
            {{#if truncated}}<div class="alert alert-warning acx-alert">{{translate 'resultTruncated' category='messages' scope='AdvancedCrosstab'}}</div>{{/if}}
            {{#if empty}}<div class="acx-empty text-muted">{{translate 'No data' scope='AdvancedCrosstab'}}</div>{{/if}}
            <div data-role="body">{{{body}}}</div>
        `

        data() {
            const result = this.options.result;

            return {
                truncated: result.truncated,
                empty: !result.rows.length && !result.columns.length && !Object.keys(result.cells).length,
            };
        }

        setup() {
            this.formatter = new Formatter(this);
            this.setMode(this.options.mode || 'table', true);
        }

        setMode(mode, noRender) {
            this.mode = mode;

            const views = {
                table: 'advanced-crosstab:views/advanced-crosstab/result/table',
                chart: 'advanced-crosstab:views/advanced-crosstab/result/chart',
                kpi: 'advanced-crosstab:views/advanced-crosstab/result/kpi',
            };

            const promise = this.createView('body', views[mode] || views.table, {
                selector: '[data-role="body"]',
                result: this.options.result,
                formatter: this.formatter,
                chartType: this.options.chartType,
                measure: this.options.chartMeasure,
                height: this.options.height,
                measures: this.options.kpiMeasures,
                drillDown: this.options.drillDown !== false,
                onDrillDown: params => this.openDrillDown(params),
            });

            if (!noRender) {
                promise.then(view => view.render());
            }

            return promise;
        }

        getTableView() {
            return this.mode === 'table' ? this.getView('body') : null;
        }

        findLabels(nodes, path) {
            const labels = [];
            let level = nodes;

            for (const key of path) {
                const node = (level || []).find(n => n.k === key);

                labels.push(node ? node.l : key);
                level = node ? node.c : null;
            }

            return labels;
        }

        openDrillDown({rowPath, columnPath, measure}) {
            const result = this.options.result;
            const measureDefs = result.measures.find(m => m.key === measure);

            const conditions = []
                .concat(rowPath.map((key, i) => result.rowDimensions[i].label + ' = ' + this.findLabels(result.rows, rowPath)[i]))
                .concat(columnPath.map((key, i) => result.columnDimensions[i].label + ' = ' + this.findLabels(result.columns, columnPath)[i]));

            const title = (measureDefs ? measureDefs.label + ' · ' : '') +
                this.translate(result.entityType, 'scopeNamesPlural');

            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/drill-down', {
                entityType: result.entityType,
                title: title,
                conditions: conditions.length ? conditions.join('  ·  ') : this.translate('All records', 'labels', 'AdvancedCrosstab'),
                payload: {...this.options.source, rowPath, columnPath, measure},
            }).then(view => view.render());
        }
    };
});
