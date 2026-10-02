define('advanced-crosstab:views/advanced-crosstab/fields/entity-type', ['views/fields/varchar'], function (VarcharFieldView) {

    /**
     * Data source entity type, displayed with its translated name.
     */
    return class extends VarcharFieldView {

        getValueForDisplay() {
            const value = this.model.get(this.name);

            return value ? this.translate(value, 'scopeNamesPlural') : value;
        }
    };
});
