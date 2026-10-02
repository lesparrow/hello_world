define('advanced-crosstab:views/advanced-crosstab/modals/drill-down', ['views/modal'], function (ModalView) {

    /**
     * Records behind an aggregated cell, shown with EspoCRM's standard list view
     * (sorting, pagination, links to record detail). Records come from the drill-down endpoint, which applies
     * the crosstab's ACL restrictions, filters and the cell's row/column conditions.
     *
     * Options: entityType, title, payload {id?, definition?, rowPath, columnPath, measure}.
     */
    return class extends ModalView {

        className = 'dialog dialog-record'

        backdrop = true

        templateContent = `
            <div class="acx-drill-summary small text-muted">{{conditions}}</div>
            <div class="list-container">{{{list}}}</div>
        `

        data() {
            return {conditions: this.options.conditions || ''};
        }

        setup() {
            this.headerText = this.options.title;

            this.buttonList = [{name: 'close', label: 'Close', onClick: () => this.close()}];

            this.wait(
                this.getCollectionFactory().create(this.options.entityType).then(collection => {
                    collection.url = 'AdvancedCrosstab/action/drillDown';
                    collection.data = {payload: JSON.stringify(this.options.payload)};
                    collection.maxSize = this.getConfig().get('recordsPerPageSmall') || 20;

                    return this.createView('list', 'views/record/list', {
                        selector: '.list-container',
                        collection: collection,
                        layoutName: 'listSmall',
                        checkboxes: false,
                        displayTotalCount: true,
                        buttonsDisabled: true,
                        rowActionsDisabled: true,
                        skipBuildRows: true,
                    }).then(view => {
                        view.getSelectAttributeList(attributes => {
                            if (attributes) {
                                if (!attributes.includes('name')) {
                                    attributes.push('name');
                                }

                                collection.data.select = attributes.join(',');
                            }

                            this.whenRendered().then(() => {
                                Espo.Ui.notify(this.translate('pleaseWait', 'messages'));
                                collection.fetch().then(() => Espo.Ui.notify(false));
                            });
                        });
                    });
                })
            );
        }
    };
});
