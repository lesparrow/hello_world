define('advanced-crosstab:views/advanced-crosstab/modals/dimension', ['views/modal', 'advanced-crosstab:lib/schema'], function (ModalView, Schema) {

    const GRANULARITIES = ['year', 'quarter', 'yearMonth', 'week', 'day', 'month', 'quarterNumber', 'dayOfWeek'];

    /**
     * Row/column dimension editor: a field (from the relationship tree) or a record formula,
     * date grouping, label, sorting and Top/Bottom N.
     *
     * Options: entityType, dimension, measures [{key, label}], onApply(dimension).
     */
    return class extends ModalView {

        className = 'dialog dialog-record'

        templateContent = `
            <div class="acx-modal-form">
                <div class="btn-group acx-source-switch" role="group">
                    <button type="button" class="btn btn-default" data-action="setSource" data-source="field">
                        <span class="fas fa-sitemap"></span> {{translate 'Field' scope='AdvancedCrosstab'}}</button>
                    <button type="button" class="btn btn-default" data-action="setSource" data-source="formula">
                        <span class="fas fa-square-root-alt"></span> {{translate 'Formula' scope='AdvancedCrosstab'}}</button>
                </div>
                <div data-role="field-section" class="row">
                    <div class="col-sm-6">
                        <label class="control-label">{{translate 'Field' scope='AdvancedCrosstab'}}</label>
                        <div class="acx-selected-path" data-role="selected-path"></div>
                        <div class="acx-tree-box" data-role="tree">{{{tree}}}</div>
                    </div>
                </div>
                <div data-role="formula-section" class="hidden">
                    <div data-role="formula">{{{formula}}}</div>
                </div>
                <div class="row acx-dimension-settings" data-role="settings">
                    <div class="col-sm-3 form-group" data-role="granularity-group">
                        <label class="control-label">{{translate 'Date grouping' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="granularity"></select>
                    </div>
                    <div class="col-sm-3 form-group">
                        <label class="control-label">{{translate 'Label' scope='AdvancedCrosstab'}}</label>
                        <input type="text" class="form-control" data-name="label" maxlength="150">
                    </div>
                    <div class="col-sm-3 form-group">
                        <label class="control-label">{{translate 'Sort by' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="sortBy"></select>
                        <select class="form-control acx-mt" data-name="sortMeasure"></select>
                        <select class="form-control acx-mt" data-name="sortDirection"></select>
                    </div>
                    <div class="col-sm-3 form-group">
                        <label class="control-label">{{translate 'Top / Bottom N' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="limitType"></select>
                        <input type="number" class="form-control acx-mt" data-name="limitCount" min="1" max="10000">
                        <select class="form-control acx-mt" data-name="limitMeasure"></select>
                    </div>
                </div>
            </div>
        `

        setup() {
            this.schema = new Schema(this);
            this.entityType = this.options.entityType;
            this.dimension = Espo.Utils.cloneDeep(this.options.dimension || {type: 'field'});
            this.dimension.type = this.dimension.type || 'field';

            this.headerText = this.translate(this.options.dimension ? 'Edit dimension' : 'Add dimension', 'labels', 'AdvancedCrosstab');

            this.buttonList = [
                {name: 'apply', label: 'Apply', style: 'primary', onClick: () => this.apply()},
                {name: 'cancel', label: 'Cancel', onClick: () => this.close()},
            ];

            this.addActionHandler('setSource', (e, target) => this.setSource(target.dataset.source));

            this.createView('tree', 'advanced-crosstab:views/advanced-crosstab/field-tree', {
                selector: '[data-role="tree"]',
                entityType: this.entityType,
                purpose: 'dimension',
                onSelect: (path, info) => {
                    this.dimension.path = path;
                    this.updateSelected();
                },
            });

            this.createView('formula', 'advanced-crosstab:views/advanced-crosstab/formula-builder', {
                selector: '[data-role="formula"]',
                entityType: this.entityType,
                kind: 'record',
                value: this.dimension.formula || '',
            });
        }

        afterRender() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const options = (list, selected) => list.map(([value, label]) =>
                `<option value="${this.escapeString(value)}"${value === selected ? ' selected' : ''}>${this.escapeString(label)}</option>`).join('');

            const t = (label, category = 'labels') => this.translate(label, category, 'AdvancedCrosstab');
            const measures = (this.options.measures || []).map(m => [m.key, m.label]);
            const sort = this.dimension.sort || {};
            const limit = this.dimension.limit || {};

            $('granularity').innerHTML = options(GRANULARITIES.map(g => [g, t(g, 'granularities')]), this.dimension.granularity || 'yearMonth');
            $('label').value = this.dimension.label || '';
            $('sortBy').innerHTML = options([['natural', t('Natural order')], ['label', t('Label')], ['measure', t('Measure')]], sort.by || 'natural');
            $('sortMeasure').innerHTML = options(measures, sort.measure);
            $('sortDirection').innerHTML = options([['asc', t('Ascending')], ['desc', t('Descending')]],
                sort.direction || (sort.by === 'measure' ? 'desc' : 'asc'));
            $('limitType').innerHTML = options([['', t('All')], ['top', t('Top N')], ['bottom', t('Bottom N')]], limit.type || '');
            $('limitCount').value = limit.count || 10;
            $('limitMeasure').innerHTML = options(measures, limit.measure);

            const sync = () => {
                $('sortMeasure').classList.toggle('hidden', $('sortBy').value !== 'measure');
                $('limitCount').classList.toggle('hidden', !$('limitType').value);
                $('limitMeasure').classList.toggle('hidden', !$('limitType').value);
            };

            $('sortBy').addEventListener('change', () => {
                if ($('sortBy').value === 'measure') {
                    $('sortDirection').value = 'desc';
                }

                sync();
            });
            $('limitType').addEventListener('change', sync);
            sync();

            this.setSource(this.dimension.type);
        }

        setSource(source) {
            this.dimension.type = source;

            this.element.querySelectorAll('[data-action="setSource"]').forEach(button =>
                button.classList.toggle('active', button.dataset.source === source));

            this.element.querySelector('[data-role="field-section"]').classList.toggle('hidden', source !== 'field');
            this.element.querySelector('[data-role="formula-section"]').classList.toggle('hidden', source !== 'formula');

            this.updateSelected();
        }

        updateSelected() {
            const pathElement = this.element.querySelector('[data-role="selected-path"]');
            const isField = this.dimension.type === 'field';
            const resolved = isField && this.dimension.path ? this.schema.resolvePath(this.entityType, this.dimension.path) : null;

            pathElement.innerHTML = this.dimension.path ?
                `<span class="label label-primary">${this.escapeString(this.schema.getPathLabel(this.entityType, this.dimension.path))}</span>` :
                `<span class="text-muted">${this.translate('Select a field below', 'labels', 'AdvancedCrosstab')}</span>`;

            const isDate = resolved && Schema.DATE_TYPES.includes(resolved.type);

            this.element.querySelector('[data-role="granularity-group"]').classList.toggle('hidden', !isDate);
        }

        async apply() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const dimension = {id: this.dimension.id, type: this.dimension.type};

            if (dimension.type === 'field') {
                if (!this.dimension.path) {
                    Espo.Ui.warning(this.translate('Select a field below', 'labels', 'AdvancedCrosstab'));

                    return;
                }

                dimension.path = this.dimension.path;

                const resolved = this.schema.resolvePath(this.entityType, dimension.path);

                if (Schema.DATE_TYPES.includes(resolved.type)) {
                    dimension.granularity = $('granularity').value;
                }
            } else {
                const formulaView = this.getView('formula');

                if (!await formulaView.validate()) {
                    Espo.Ui.warning(this.translate('Fix the formula first', 'labels', 'AdvancedCrosstab'));

                    return;
                }

                dimension.formula = formulaView.getValue();
            }

            const label = $('label').value.trim();

            if (label) {
                dimension.label = label;
            }

            if ($('sortBy').value !== 'natural' || $('sortDirection').value !== 'asc') {
                dimension.sort = {by: $('sortBy').value, direction: $('sortDirection').value};

                if (dimension.sort.by === 'measure') {
                    dimension.sort.measure = $('sortMeasure').value;
                }
            }

            if ($('limitType').value) {
                dimension.limit = {
                    type: $('limitType').value,
                    count: Math.max(1, parseInt($('limitCount').value) || 10),
                    measure: $('limitMeasure').value,
                };
            }

            if ((dimension.sort && dimension.sort.by === 'measure' && !dimension.sort.measure) ||
                (dimension.limit && !dimension.limit.measure)) {
                Espo.Ui.warning(this.translate('Select a measure', 'labels', 'AdvancedCrosstab'));

                return;
            }

            this.options.onApply(dimension);
            this.close();
        }
    };
});
