define('advanced-crosstab:handlers/list-pivot', [], function () {

    /**
     * Adds a "Pivot" button to every entity list view (registered in clientDefs.Global.viewSetupHandlers.list).
     *
     * The crosstab opens with the list's current filters (search text, preset filter, "only my", field filters),
     * applied by the server with the user's ACL, and with the entity's default layout if one is defined in
     * metadata: clientDefs.{Entity}.advancedCrosstab = {rows, columns, measures, options}.
     */
    return class {

        constructor(view) {
            this.view = view;
        }

        process() {
            const view = this.view;
            const scope = view.scope;
            const metadata = view.getMetadata();
            const acl = view.getAcl();

            if (
                !scope ||
                scope === 'AdvancedCrosstab' ||
                !metadata.get(['scopes', scope, 'entity']) ||
                metadata.get(['clientDefs', scope, 'advancedCrosstab', 'disabled']) ||
                !acl.checkScope(scope, 'read') ||
                !acl.check('AdvancedCrosstab', 'create')
            ) {
                return;
            }

            view.addMenuItem('buttons', {
                name: 'advancedCrosstabPivot',
                iconHtml: '<span class="fas fa-table-cells"></span>',
                text: view.translate('Pivot', 'labels', 'AdvancedCrosstab'),
                title: view.translate('pivotButtonTitle', 'messages', 'AdvancedCrosstab'),
                style: 'default',
                onClick: () => this.open(),
            }, true);
        }

        open() {
            const view = this.view;
            const scope = view.scope;
            const defaults = Espo.Utils.cloneDeep(view.getMetadata().get(['clientDefs', scope, 'advancedCrosstab']) || {});

            let where = [];

            try {
                where = view.searchManager ? view.searchManager.getWhere() : (view.collection.getWhere() || []);
            } catch (e) {
                where = [];
            }

            const definition = {
                entityType: scope,
                rows: defaults.rows || [],
                columns: defaults.columns || [],
                measures: defaults.measures || [{
                    key: 'count',
                    label: view.translate('Count', 'labels', 'AdvancedCrosstab'),
                    kind: 'native',
                    aggregation: 'COUNT',
                }],
                filter: defaults.filter || null,
                listWhere: where.length ? where : null,
                options: {
                    rowTotals: true,
                    columnTotals: true,
                    subtotals: true,
                    ...(defaults.options || {}),
                    view: {mode: 'table', chartType: 'column', layout: 'compact', ...((defaults.options || {}).view || {})},
                },
            };

            const name = view.translate(scope, 'scopeNamesPlural') + ' · ' + view.translate('Pivot', 'labels', 'AdvancedCrosstab');

            view.getRouter().navigate('#AdvancedCrosstab/create', {trigger: false});
            view.getRouter().dispatch('AdvancedCrosstab', 'create', {
                attributes: {name: name, definition: definition},
                returnUrl: '#' + scope,
            });
        }
    };
});
