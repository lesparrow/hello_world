define('advanced-crosstab:views/advanced-crosstab/result/kpi', ['view'], function (View) {

    /**
     * KPI cards: grand total of each visible measure (computed by the database at the total level,
     * so ratios such as margin % are exact).
     *
     * Options: result, formatter, measures (optional list of keys), onDrillDown.
     */
    return class extends View {

        templateContent = `<div class="acx-kpis" data-role="kpis"></div>`

        afterRender() {
            const result = this.options.result;
            const total = (result.cells['[]'] || {})['[]'] || [];
            const keys = this.options.measures;

            const cards = result.valueColumns
                .map((column, index) => ({column, index, measure: result.measures.find(m => m.key === column.measure)}))
                .filter(item => item.column.variant === 'value' && (!keys || !keys.length || keys.includes(item.measure.key)))
                .map(item => `
                    <div class="acx-kpi${item.measure.drillable ? ' acx-clickable' : ''}" data-measure="${this.escapeString(item.measure.key)}">
                        <div class="acx-kpi-label">${this.escapeString(item.measure.label)}</div>
                        <div class="acx-kpi-value" title="${this.escapeString(this.options.formatter.format(total[item.index], item.measure.format))}">
                            ${this.escapeString(this.options.formatter.compact(total[item.index], item.measure.format))}</div>
                    </div>
                `);

            const container = this.element.querySelector('[data-role="kpis"]');

            container.innerHTML = cards.join('');

            container.addEventListener('click', e => {
                const card = e.target.closest('.acx-kpi.acx-clickable');

                if (card && this.options.onDrillDown) {
                    this.options.onDrillDown({rowPath: [], columnPath: [], measure: card.dataset.measure});
                }
            });
        }
    };
});
