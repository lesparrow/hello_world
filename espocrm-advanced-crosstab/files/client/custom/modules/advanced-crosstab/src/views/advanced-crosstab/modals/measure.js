define('advanced-crosstab:views/advanced-crosstab/modals/measure', ['views/modal', 'advanced-crosstab:lib/formatter'], function (ModalView, Formatter) {

    const AGGREGATIONS = ['SUM', 'COUNT', 'COUNT_DISTINCT', 'AVG', 'MIN', 'MAX'];
    const FORMATS = ['number', 'integer', 'decimal', 'percent', 'currency', 'duration'];

    /**
     * Measure editor.
     *
     * - native:    aggregation of a record formula (a field or an expression such as `amount * quantity`),
     *              with an optional condition (WHERE);
     * - aggregate: formula over aggregates, e.g. (SUM(revenue) - SUM(cost)) / SUM(revenue) * 100;
     * - display:   formula over other measures, evaluated after aggregation.
     *
     * Options: entityType, measure, kind, measures (other measures [{key, label}]), onApply(measure).
     */
    return class extends ModalView {

        className = 'dialog dialog-record'

        templateContent = `
            <div class="acx-modal-form">
                <div class="row">
                    <div class="col-sm-5 form-group">
                        <label class="control-label">{{translate 'Label' scope='AdvancedCrosstab'}} *</label>
                        <input type="text" class="form-control" data-name="label" maxlength="150">
                    </div>
                    <div class="col-sm-3 form-group">
                        <label class="control-label" title="{{translate 'keyTooltip' category='messages' scope='AdvancedCrosstab'}}">
                            {{translate 'Key' scope='AdvancedCrosstab'}} *</label>
                        <input type="text" class="form-control" data-name="key" maxlength="50" spellcheck="false">
                    </div>
                    <div class="col-sm-4 form-group" data-role="aggregation-group">
                        <label class="control-label">{{translate 'Aggregation' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="aggregation"></select>
                    </div>
                </div>
                <div class="form-group">
                    <label class="control-label" data-role="formula-label"></label>
                    <div data-role="formula">{{{formula}}}</div>
                </div>
                <div class="form-group" data-role="condition-group">
                    <label class="control-label">
                        <input type="checkbox" data-name="hasCondition">
                        {{translate 'Only records where (condition)' scope='AdvancedCrosstab'}}
                    </label>
                    <div data-role="condition">{{{condition}}}</div>
                </div>
                <div class="row">
                    <div class="col-sm-2 form-group">
                        <label class="control-label">{{translate 'Format' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="formatType"></select>
                    </div>
                    <div class="col-sm-2 form-group">
                        <label class="control-label">{{translate 'Decimals' scope='AdvancedCrosstab'}}</label>
                        <input type="number" class="form-control" data-name="decimals" min="0" max="10" placeholder="auto">
                    </div>
                    <div class="col-sm-2 form-group" data-role="currency-group">
                        <label class="control-label">{{translate 'Currency' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="currency"></select>
                    </div>
                    <div class="col-sm-2 form-group">
                        <label class="control-label">{{translate 'Prefix' scope='AdvancedCrosstab'}}</label>
                        <input type="text" class="form-control" data-name="prefix" maxlength="20">
                    </div>
                    <div class="col-sm-2 form-group">
                        <label class="control-label">{{translate 'Suffix' scope='AdvancedCrosstab'}}</label>
                        <input type="text" class="form-control" data-name="suffix" maxlength="20">
                    </div>
                    <div class="col-sm-2 form-group">
                        <label class="control-label">{{translate 'Visible' scope='AdvancedCrosstab'}}</label>
                        <div><input type="checkbox" data-name="visible"></div>
                    </div>
                </div>
                <div class="row">
                    <div class="col-sm-4 form-group">
                        <label class="control-label">{{translate 'Compare with' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="compare"></select>
                    </div>
                    <div class="col-sm-4 form-group" data-role="compare-mode-group">
                        <label class="control-label">{{translate 'Comparison' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="compareMode"></select>
                    </div>
                </div>
            </div>
        `

        setup() {
            this.formatter = new Formatter(this);
            this.measure = Espo.Utils.cloneDeep(this.options.measure || {
                kind: this.options.kind || 'native',
                aggregation: 'SUM',
                format: {type: 'number'},
            });
            this.kind = this.measure.kind || 'native';
            this.isNew = !this.options.measure;

            this.headerText = this.translate(this.isNew ? 'Add measure' : 'Edit measure', 'labels', 'AdvancedCrosstab') +
                ' · ' + this.translate(this.kind, 'measureKinds', 'AdvancedCrosstab');

            this.buttonList = [
                {name: 'apply', label: 'Apply', style: 'primary', onClick: () => this.apply()},
                {name: 'cancel', label: 'Cancel', onClick: () => this.close()},
            ];

            const formulaKind = {native: 'record', aggregate: 'aggregate', display: 'display'}[this.kind];

            this.createView('formula', 'advanced-crosstab:views/advanced-crosstab/formula-builder', {
                selector: '[data-role="formula"]',
                entityType: this.options.entityType,
                kind: formulaKind,
                value: this.kind === 'native' ? (this.measure.expression || '') : (this.measure.formula || ''),
                measures: this.options.measures || [],
                formatter: this.formatter,
                format: this.measure.format,
            });

            if (this.kind !== 'display') {
                this.createView('condition', 'advanced-crosstab:views/advanced-crosstab/formula-builder', {
                    selector: '[data-role="condition"]',
                    entityType: this.options.entityType,
                    kind: 'condition',
                    value: this.measure.condition || '',
                });
            }
        }

        afterRender() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const t = (label, category = 'labels') => this.translate(label, category, 'AdvancedCrosstab');
            const options = (list, selected) => list.map(([value, label]) =>
                `<option value="${this.escapeString(value)}"${value === selected ? ' selected' : ''}>${this.escapeString(label)}</option>`).join('');

            const format = this.measure.format || {};
            const currencyList = this.getConfig().get('currencyList') || [this.getConfig().get('defaultCurrency')];

            $('label').value = this.measure.label || '';
            $('key').value = this.measure.key || '';
            $('aggregation').innerHTML = options(AGGREGATIONS.map(a => [a, t(a, 'aggregations')]), this.measure.aggregation || 'SUM');
            $('formatType').innerHTML = options(FORMATS.map(f => [f, t(f, 'formats')]), format.type || 'number');
            $('decimals').value = format.decimals ?? '';
            $('currency').innerHTML = options([['', t('Default')]].concat(currencyList.filter(Boolean).map(c => [c, c])), format.currency || '');
            $('prefix').value = format.prefix || '';
            $('suffix').value = format.suffix || '';
            $('visible').checked = !this.measure.hidden;
            $('compare').innerHTML = options([['', t('Nothing')], ['previous', t('Previous period')], ['previousYear', t('Same period last year')]],
                this.measure.compare || '');
            $('compareMode').innerHTML = options([['percent', t('Change %')], ['difference', t('Difference')]], this.measure.compareMode || 'percent');

            const conditionGroup = this.element.querySelector('[data-role="condition-group"]');
            const conditionBox = this.element.querySelector('[data-role="condition"]');

            conditionGroup.classList.toggle('hidden', this.kind === 'display');
            $('hasCondition').checked = !!this.measure.condition;
            conditionBox.classList.toggle('hidden', !this.measure.condition);
            $('hasCondition').addEventListener('change', () => conditionBox.classList.toggle('hidden', !$('hasCondition').checked));

            this.element.querySelector('[data-role="aggregation-group"]').classList.toggle('hidden', this.kind !== 'native');

            const updateFormulaLabel = () => {
                const label = this.kind === 'native' ?
                    ($('aggregation').value === 'COUNT' ? t('Count records (optional expression)') : t('Value (field or record formula)')) :
                    (this.kind === 'aggregate' ? t('Aggregate formula') : t('Display formula'));

                this.element.querySelector('[data-role="formula-label"]').textContent = label;
            };

            $('aggregation').addEventListener('change', updateFormulaLabel);
            updateFormulaLabel();

            const syncFormat = () => {
                this.element.querySelector('[data-role="currency-group"]').classList.toggle('hidden', $('formatType').value !== 'currency');
                this.element.querySelector('[data-role="compare-mode-group"]').classList.toggle('hidden', !$('compare').value);
            };

            $('formatType').addEventListener('change', syncFormat);
            $('compare').addEventListener('change', syncFormat);
            syncFormat();

            // Derive the key from the label for new measures.
            let keyEdited = !this.isNew;

            $('key').addEventListener('input', () => keyEdited = true);
            $('label').addEventListener('input', () => {
                if (!keyEdited) {
                    $('key').value = this.labelToKey($('label').value);
                }
            });
        }

        labelToKey(label) {
            let key = label
                .normalize('NFD').replace(/[̀-ͯ]/g, '')
                .replace(/[^a-zA-Z0-9]+(.)?/g, (m, c) => c ? c.toUpperCase() : '')
                .replace(/^[^a-zA-Z_]+/, '');

            key = key.charAt(0).toLowerCase() + key.slice(1);

            return key.slice(0, 50) || 'measure';
        }

        async apply() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const t = label => this.translate(label, 'labels', 'AdvancedCrosstab');

            const label = $('label').value.trim();
            const key = $('key').value.trim();

            if (!label) {
                Espo.Ui.warning(t('Label is required'));

                return;
            }

            if (!/^[a-zA-Z_][a-zA-Z0-9_]{0,49}$/.test(key) || ['id', 'null', 'true', 'false'].includes(key.toLowerCase())) {
                Espo.Ui.warning(t('Invalid key'));

                return;
            }

            if ((this.options.usedKeys || []).includes(key)) {
                Espo.Ui.warning(t('Key already used'));

                return;
            }

            const measure = {key, label, kind: this.kind};
            const formulaView = this.getView('formula');
            const formula = formulaView.getValue();

            if (this.kind === 'native') {
                measure.aggregation = $('aggregation').value;

                if (formula) {
                    if (!await formulaView.validate()) {
                        Espo.Ui.warning(t('Fix the formula first'));

                        return;
                    }

                    measure.expression = formula;
                } else if (measure.aggregation !== 'COUNT') {
                    Espo.Ui.warning(t('Select a field or enter a formula'));

                    return;
                }
            } else {
                if (!formula || !await formulaView.validate()) {
                    Espo.Ui.warning(t('Fix the formula first'));

                    return;
                }

                measure.formula = formula;
            }

            if (this.kind !== 'display' && $('hasCondition').checked) {
                const conditionView = this.getView('condition');
                const condition = conditionView.getValue();

                if (condition) {
                    if (!await conditionView.validate()) {
                        Espo.Ui.warning(t('Fix the condition first'));

                        return;
                    }

                    measure.condition = condition;
                }
            }

            measure.format = {type: $('formatType').value};

            if ($('decimals').value !== '') {
                measure.format.decimals = Math.max(0, Math.min(10, parseInt($('decimals').value)));
            }

            if (measure.format.type === 'currency' && $('currency').value) {
                measure.format.currency = $('currency').value;
            }

            if ($('prefix').value) {
                measure.format.prefix = $('prefix').value;
            }

            if ($('suffix').value) {
                measure.format.suffix = $('suffix').value;
            }

            if (!$('visible').checked) {
                measure.hidden = true;
            }

            if ($('compare').value) {
                measure.compare = $('compare').value;
                measure.compareMode = $('compareMode').value;
            }

            this.options.onApply(measure);
            this.close();
        }
    };
});
