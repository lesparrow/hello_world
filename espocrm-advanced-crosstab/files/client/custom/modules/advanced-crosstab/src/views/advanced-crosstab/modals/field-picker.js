define('advanced-crosstab:views/advanced-crosstab/modals/field-picker', ['views/modal'], function (ModalView) {

    /**
     * Options: entityType, purpose, onSelect(path, info).
     */
    return class extends ModalView {

        templateContent = `<div data-role="tree" class="acx-tree-box acx-tree-box-tall">{{{tree}}}</div>`

        backdrop = true

        setup() {
            this.headerText = this.translate('Select field', 'labels', 'AdvancedCrosstab');

            this.createView('tree', 'advanced-crosstab:views/advanced-crosstab/field-tree', {
                selector: '[data-role="tree"]',
                entityType: this.options.entityType,
                purpose: this.options.purpose || 'dimension',
                onSelect: (path, info) => {
                    this.options.onSelect(path, info);
                    this.close();
                },
            });
        }
    };
});
