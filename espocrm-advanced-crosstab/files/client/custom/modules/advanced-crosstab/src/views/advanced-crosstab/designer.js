define('advanced-crosstab:views/advanced-crosstab/designer', [
    'view',
    'advanced-crosstab:lib/schema',
    'advanced-crosstab:lib/operators',
    'advanced-crosstab:lib/styles',
], function (View, Schema, Operators, Styles) {

    const CHART_TYPES = ['column', 'bar', 'stackedBar', 'line', 'pie', 'donut'];
    const EXPORT_FORMATS = ['xlsx', 'csv', 'pdf'];

    /**
     * Crosstab designer and viewer (detail and edit page of AdvancedCrosstab records).
     *
     * Every change re-runs the crosstab (debounced); aggregation happens on the server.
     */
    return class extends View {

        templateContent = `
            <div class="acx-header">
                <a href="#AdvancedCrosstab" class="text-muted"><span class="fas fa-table-cells"></span>
                    {{translate 'AdvancedCrosstab' category='scopeNamesPlural'}}</a>
                <span class="text-muted">›</span>
                <input type="text" class="acx-name-input" data-name="name" maxlength="150"
                    placeholder="{{translate 'Untitled crosstab' scope='AdvancedCrosstab'}}">
                <span class="acx-dirty hidden" data-role="dirty">● {{translate 'Unsaved changes' scope='AdvancedCrosstab'}}</span>
                <div class="btn-group acx-workspace" data-role="workspace">
                    <button type="button" class="btn btn-default btn-sm" data-action="setWorkspace" data-workspace="design">
                        <span class="fas fa-table"></span> {{translate 'Design' scope='AdvancedCrosstab'}}</button>
                    <button type="button" class="btn btn-default btn-sm" data-action="setWorkspace" data-workspace="pipeline">
                        <span class="fas fa-project-diagram"></span> {{translate 'Pipeline' scope='AdvancedCrosstab'}}</button>
                </div>
                <div class="acx-header-buttons">
                    <div class="btn-group">
                        <button type="button" class="btn btn-default btn-icon" data-action="undo" disabled
                            title="{{translate 'Undo' scope='AdvancedCrosstab'}} (Ctrl+Z)"><span class="fas fa-undo"></span></button>
                        <button type="button" class="btn btn-default btn-icon" data-action="redo" disabled
                            title="{{translate 'Redo' scope='AdvancedCrosstab'}} (Ctrl+Shift+Z)"><span class="fas fa-redo"></span></button>
                    </div>
                    <button type="button" class="btn btn-default btn-icon acx-star hidden" data-action="toggleStar"
                        title="{{translate 'Favorite' scope='AdvancedCrosstab'}}"><span class="far fa-star"></span></button>
                    <button type="button" class="btn btn-primary" data-action="save" title="Ctrl+S">{{translate 'Save'}}</button>
                    <div class="btn-group">
                        <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown">
                            <span class="fas fa-ellipsis-h"></span></button>
                        <ul class="dropdown-menu pull-right" data-role="menu"></ul>
                    </div>
                </div>
            </div>
            <div class="acx-designer">
                <div class="acx-sidebar">
                    <div class="panel panel-default">
                        <div class="panel-body">
                            <div class="acx-properties-head hidden" data-role="properties-head"></div>
                            <div class="acx-section" data-stage="source">
                                <div class="acx-section-title">
                                    <span>{{translate 'Data source' scope='AdvancedCrosstab'}}</span>
                                    <a role="button" data-action="dataModel" title="{{translate 'Data model' scope='AdvancedCrosstab'}}">
                                        <span class="fas fa-project-diagram"></span> {{translate 'Data model' scope='AdvancedCrosstab'}}</a>
                                </div>
                                <select class="form-control" data-name="entityType"></select>
                            </div>
                            <div class="acx-section" data-role="joins" data-stage="lookups"></div>
                            <div class="acx-section" data-role="rows" data-stage="aggregate"></div>
                            <div class="acx-section" data-role="columns" data-stage="aggregate"></div>
                            <div class="acx-section" data-role="measures" data-stage="aggregate calculate lookups"></div>
                            <div class="acx-section" data-stage="filter">
                                <div class="acx-section-title">{{translate 'Filters' scope='AdvancedCrosstab'}}</div>
                                <div data-role="list-filters"></div>
                                <select class="form-control input-sm" data-name="primaryFilter"></select>
                                <div class="acx-mt" data-role="filters">{{{filters}}}</div>
                            </div>
                            <div class="acx-section" data-stage="output">
                                <div class="acx-section-title">{{translate 'Totals' scope='AdvancedCrosstab'}}</div>
                                <div class="checkbox"><label><input type="checkbox" data-option="rowTotals">
                                    {{translate 'Row totals' scope='AdvancedCrosstab'}}</label></div>
                                <div class="checkbox"><label><input type="checkbox" data-option="columnTotals">
                                    {{translate 'Column totals' scope='AdvancedCrosstab'}}</label></div>
                                <div class="checkbox"><label><input type="checkbox" data-option="subtotals">
                                    {{translate 'Subtotals' scope='AdvancedCrosstab'}}</label></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="acx-main">
                    <div class="panel panel-default">
                        <div class="panel-body">
                            <div class="acx-toolbar" data-role="toolbar">
                                <div class="btn-group" data-role="modes"></div>
                                <select class="form-control input-sm acx-inline-select hidden" data-name="chartType"></select>
                                <select class="form-control input-sm acx-inline-select hidden" data-name="chartMeasure"></select>
                                <select class="form-control input-sm acx-inline-select" data-name="layout"
                                    title="{{translate 'Layout' scope='AdvancedCrosstab'}}"></select>
                                <div class="btn-group btn-group-sm" data-role="table-tools">
                                    <button type="button" class="btn btn-default" data-action="expandAll"
                                        title="{{translate 'Expand all' scope='AdvancedCrosstab'}}"><span class="fas fa-plus-square"></span></button>
                                    <button type="button" class="btn btn-default" data-action="collapseAll"
                                        title="{{translate 'Collapse all' scope='AdvancedCrosstab'}}"><span class="fas fa-minus-square"></span></button>
                                </div>
                                <button type="button" class="btn btn-default btn-sm" data-action="fullscreen"
                                    title="{{translate 'Full screen' scope='AdvancedCrosstab'}}"><span class="fas fa-expand"></span></button>
                                <button type="button" class="btn btn-default btn-sm" data-action="refresh"
                                    title="{{translate 'Refresh' scope='AdvancedCrosstab'}}"><span class="fas fa-sync-alt"></span></button>
                                <span class="acx-info" data-role="info"></span>
                            </div>
                            <div data-role="guide"></div>
                            <div data-role="result"></div>
                            <div class="hidden" data-role="pipeline"></div>
                        </div>
                    </div>
                </div>
            </div>
        `

        setup() {
            Styles.ensure();

            this.schema = new Schema(this);
            this.entityTypeList = this.schema.getEntityTypeList();
            this.isNew = !this.model.id;

            this.definition = Espo.Utils.cloneDeep(this.model.get('definition')) || null;

            if (!this.definition || !this.definition.entityType) {
                this.definition = this.createDefaultDefinition(this.entityTypeList[0]);
            }

            this.definition.rows = this.definition.rows || [];
            this.definition.columns = this.definition.columns || [];
            this.definition.measures = this.definition.measures || [];
            this.definition.options = this.definition.options || {};
            this.definition.options.view = this.definition.options.view || {mode: 'table', chartType: 'column'};
            this.definition.joins = this.definition.joins || [];

            Schema.setCustomJoins(this.definition.entityType, this.definition.joins);

            this.dirty = this.isNew;
            this.result = null;
            this.error = null;
            this.requestId = 0;
            this.history = [JSON.stringify(this.definition)];
            this.historyIndex = 0;
            this.workspace = this.getStoredWorkspace();
            this.stage = null;

            const handlers = {
                save: () => this.save(),
                saveAs: () => this.saveAs(),
                properties: () => this.editProperties(),
                remove: () => this.removeRecord(),
                toggleStar: () => this.toggleStar(),
                refresh: () => this.run(true),
                expandAll: () => this.tableView()?.expandAll(true),
                collapseAll: () => this.tableView()?.expandAll(false),
                print: () => this.print(),
                undo: () => this.undo(),
                redo: () => this.redo(),
                showAllSections: () => this.selectStage(null),
                guideDataModel: () => this.openDataModel(),
                guidePipeline: () => this.setWorkspace('pipeline'),
            };

            for (const [name, handler] of Object.entries(handlers)) {
                this.addActionHandler(name, handler);
            }

            this.addActionHandler('exportResult', (e, target) => this.exportResult(target.dataset.format));
            this.addActionHandler('setMode', (e, target) => this.setViewOption('mode', target.dataset.mode));
            this.addActionHandler('addDimension', (e, target) => this.editDimension(target.dataset.axis, null));
            this.addActionHandler('editDimension', (e, target) => this.editDimension(target.dataset.axis, parseInt(target.dataset.index)));
            this.addActionHandler('removeDimension', (e, target) => this.removeItem(target.dataset.axis, parseInt(target.dataset.index)));
            this.addActionHandler('moveItem', (e, target) =>
                this.moveItem(target.dataset.axis, parseInt(target.dataset.index), parseInt(target.dataset.direction)));
            this.addActionHandler('swapAxes', () => this.swapAxes());
            this.addActionHandler('addMeasure', (e, target) => this.editMeasure(null, target.dataset.kind));
            this.addActionHandler('editMeasure', (e, target) => this.editMeasure(parseInt(target.dataset.index)));
            this.addActionHandler('removeMeasure', (e, target) => this.removeItem('measures', parseInt(target.dataset.index)));
            this.addActionHandler('toggleMeasure', (e, target) => this.toggleMeasure(parseInt(target.dataset.index)));
            this.addActionHandler('quickMeasure', () => this.quickMeasure());
            this.addActionHandler('dataModel', () => this.openDataModel());
            this.addActionHandler('addJoin', () => this.openCustomJoin(''));
            this.addActionHandler('removeJoin', (e, target) => this.removeCustomJoin(target.dataset.name));
            this.addActionHandler('removeListFilters', () => {
                this.definition.listWhere = null;
                this.renderListFilters();
                this.markChanged();
            });
            this.addActionHandler('fullscreen', () => this.toggleFullscreen());
            this.addActionHandler('setWorkspace', (e, target) => this.setWorkspace(target.dataset.workspace));

            this.listenTo(this.model, 'change:isStarred', () => this.updateStar());

            this.setupFilterView();
        }

        /**
         * A new crosstab, from the entity's preset when one is defined in metadata
         * (clientDefs.{Entity}.advancedCrosstab = {rows, columns, measures, filter, options}).
         */
        createDefaultDefinition(entityType) {
            const preset = Espo.Utils.cloneDeep(this.getMetadata().get(['clientDefs', entityType, 'advancedCrosstab']) || {});

            return {
                entityType: entityType,
                rows: preset.rows || [],
                columns: preset.columns || [],
                measures: preset.measures ||
                    [{key: 'count', label: this.translate('Count', 'labels', 'AdvancedCrosstab'), kind: 'native', aggregation: 'COUNT'}],
                filter: preset.filter || null,
                joins: preset.joins || [],
                options: {
                    rowTotals: true,
                    columnTotals: true,
                    subtotals: true,
                    ...(preset.options || {}),
                    view: {mode: 'table', chartType: 'column', layout: 'compact', ...((preset.options || {}).view || {})},
                },
            };
        }

        setupFilterView() {
            this.createView('filters', 'advanced-crosstab:views/advanced-crosstab/filter-builder', {
                selector: '[data-role="filters"]',
                entityType: this.definition.entityType,
                filter: this.definition.filter,
                onChange: filter => {
                    this.definition.filter = filter;
                    this.markChanged();
                },
            });
        }

        afterRender() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);

            $('name').value = this.model.get('name') || '';
            $('name').addEventListener('input', () => this.markChanged(false));

            $('entityType').innerHTML = this.entityTypeList.map(scope =>
                `<option value="${scope}"${scope === this.definition.entityType ? ' selected' : ''}>${this.escapeString(this.schema.translateEntity(scope))}</option>`).join('');

            $('entityType').addEventListener('change', () => this.changeEntityType($('entityType').value));

            this.element.querySelectorAll('[data-option]').forEach(input => {
                input.checked = this.definition.options[input.dataset.option] !== false;
                input.addEventListener('change', () => {
                    this.definition.options[input.dataset.option] = input.checked;
                    this.markChanged();
                });
            });

            $('primaryFilter').addEventListener('change', () => {
                this.definition.primaryFilter = $('primaryFilter').value || null;
                this.markChanged();
            });

            $('chartType').addEventListener('change', () => this.setViewOption('chartType', $('chartType').value));
            $('layout').addEventListener('change', () => this.setViewOption('layout', $('layout').value));

            // Inline aggregation change on measure chips.
            this.element.querySelector('[data-role="measures"]').addEventListener('change', e => {
                const select = e.target.closest('[data-measure-aggregation]');

                if (!select) {
                    return;
                }

                this.definition.measures[parseInt(select.dataset.measureAggregation)].aggregation = select.value;
                this.renderMeasureList();
                this.markChanged();
            });

            this.escapeHandler = e => this.onKeyDown(e);

            document.addEventListener('keydown', this.escapeHandler);
            $('chartMeasure').addEventListener('change', () => this.setViewOption('chartMeasure', $('chartMeasure').value));

            this.setupChipDragging();

            this.renderMenu();
            this.renderPanels();
            this.updateStar();
            this.updateDirty();
            this.updateHistoryButtons();
            this.setWorkspace(this.workspace, true);
            this.run();
        }

        t(label, category = 'labels') {
            return this.translate(label, category, 'AdvancedCrosstab');
        }

        renderMenu() {
            const item = (action, label, icon, data = '') =>
                `<li><a role="button" data-action="${action}" ${data}><span class="${icon} fa-fw"></span> ${this.escapeString(label)}</a></li>`;

            const canEdit = this.isNew || this.getAcl().checkModel(this.model, 'edit');
            const canDelete = !this.isNew && this.getAcl().checkModel(this.model, 'delete');
            const canCreate = this.getAcl().check('AdvancedCrosstab', 'create');

            this.element.querySelector('[data-action="save"]').classList.toggle('hidden', !canEdit);

            this.element.querySelector('[data-role="menu"]').innerHTML = [
                canCreate ? item('saveAs', this.t('Save as…'), 'far fa-copy') : '',
                !this.isNew && canEdit ? item('properties', this.t('Rename & share…'), 'fas fa-share-alt') : '',
                '<li class="divider"></li>',
                ...EXPORT_FORMATS.map(format => item('exportResult', this.t('Export') + ' ' + format.toUpperCase(), 'fas fa-file-export', `data-format="${format}"`)),
                item('print', this.t('Print'), 'fas fa-print'),
                canDelete ? '<li class="divider"></li>' + item('remove', this.translate('Remove'), 'fas fa-trash') : '',
            ].join('');
        }

        renderPanels() {
            this.renderGuide();
            this.renderDimensionList('rows');
            this.renderDimensionList('columns');
            this.renderMeasureList();
            this.renderJoins();
            this.renderPrimaryFilters();
            this.renderListFilters();
            this.renderViewControls();
        }

        /**
         * Filters received from an EspoCRM list view (search panel). Applied by the server; can be removed.
         */
        renderListFilters() {
            const container = this.element.querySelector('[data-role="list-filters"]');
            const list = this.definition.listWhere || [];

            container.innerHTML = list.length ? `
                <div class="acx-chip acx-list-filter">
                    <span class="acx-chip-body">
                        <span class="acx-chip-label"><span class="fas fa-filter"></span>
                            ${this.escapeString(this.t('List filters'))} (${list.length})</span>
                        <span class="acx-chip-meta" title="${this.escapeString(JSON.stringify(list))}">${this.escapeString(this.describeWhere(list))}</span>
                    </span>
                    <span class="acx-chip-actions"><a role="button" data-action="removeListFilters"
                        title="${this.escapeString(this.translate('Remove'))}"><span class="fas fa-times"></span></a></span>
                </div>` : '';
        }

        describeWhere(list) {
            return list.map(item => {
                if (item.type === 'primary') {
                    return this.translate(item.value, 'presetFilters', this.definition.entityType);
                }

                if (item.type === 'bool') {
                    return (item.value || []).map(v => this.translate(v, 'boolFilters', this.definition.entityType)).join(', ');
                }

                if (item.type === 'textFilter') {
                    return '"' + item.value + '"';
                }

                return item.attribute ? this.schema.translateField(this.definition.entityType, item.attribute) : item.type;
            }).join(' · ');
        }

        renderPrimaryFilters() {
            const select = this.element.querySelector('[data-name="primaryFilter"]');
            const list = (this.getMetadata().get(['clientDefs', this.definition.entityType, 'filterList']) || [])
                .map(item => typeof item === 'string' ? item : item.name)
                .filter(Boolean);

            select.innerHTML = `<option value="">${this.escapeString(this.t('All records'))}</option>` + list.map(name =>
                `<option value="${this.escapeString(name)}"${name === this.definition.primaryFilter ? ' selected' : ''}>` +
                this.escapeString(this.translate(name, 'presetFilters', this.definition.entityType)) + '</option>').join('');

            select.classList.toggle('hidden', !list.length);
        }

        describeDimension(dimension) {
            if (dimension.type === 'formula') {
                return {label: dimension.label || this.t('Formula'), meta: dimension.formula};
            }

            const label = dimension.label || this.schema.getPathLabel(this.definition.entityType, dimension.path);
            const meta = [dimension.path];

            if (dimension.granularity) {
                meta.push(this.t(dimension.granularity, 'granularities'));
            }

            if (dimension.limit) {
                meta.push((dimension.limit.type === 'top' ? 'Top ' : 'Bottom ') + dimension.limit.count);
            }

            return {label, meta: meta.join(' · ')};
        }

        chipActions(axis, index, length, extra = '') {
            return `<span class="acx-chip-actions">${extra}
                ${index > 0 ? `<a role="button" data-action="moveItem" data-axis="${axis}" data-index="${index}" data-direction="-1"
                    title="${this.escapeString(this.t('Move up'))}"><span class="fas fa-arrow-up"></span></a>` : ''}
                ${index < length - 1 ? `<a role="button" data-action="moveItem" data-axis="${axis}" data-index="${index}" data-direction="1"
                    title="${this.escapeString(this.t('Move down'))}"><span class="fas fa-arrow-down"></span></a>` : ''}
                <a role="button" data-action="${axis === 'measures' ? 'removeMeasure' : 'removeDimension'}" data-axis="${axis}" data-index="${index}"
                    title="${this.escapeString(this.translate('Remove'))}"><span class="fas fa-times"></span></a>
            </span>`;
        }

        renderDimensionList(axis) {
            const list = this.definition[axis];
            const container = this.element.querySelector(`[data-role="${axis}"]`);

            const items = list.map((dimension, index) => {
                const {label, meta} = this.describeDimension(dimension);

                return `<li class="acx-chip" draggable="true" data-drag-axis="${axis}" data-drag-index="${index}">
                    <span class="acx-chip-grip fas fa-grip-vertical"></span>
                    <span class="acx-chip-body" data-action="editDimension" data-axis="${axis}" data-index="${index}">
                        <span class="acx-chip-label">${this.escapeString(label)}</span>
                        <span class="acx-chip-meta">${this.escapeString(meta || '')}</span>
                    </span>
                    ${this.chipActions(axis, index, list.length)}
                </li>`;
            }).join('');

            container.innerHTML = `
                <div class="acx-section-title">
                    <span>${this.escapeString(this.t(axis === 'rows' ? 'Rows' : 'Columns'))}</span>
                    <span>
                        ${axis === 'columns' ? `<a role="button" data-action="swapAxes" title="${this.escapeString(this.t('Swap rows and columns'))}">
                            <span class="fas fa-exchange-alt"></span></a>&nbsp;` : ''}
                        <a role="button" data-action="addDimension" data-axis="${axis}" title="${this.escapeString(this.t('Add'))}">
                            <span class="fas fa-plus"></span></a>
                    </span>
                </div>
                <ul class="acx-chips" data-drop-axis="${axis}">${items}</ul>
                ${list.length ? '' : `<div class="acx-empty-hint acx-drop-zone" data-drop-axis="${axis}">${this.escapeString(this.t(axis === 'rows' ? 'No rows' : 'No columns'))}</div>`}
            `;
        }

        describeMeasure(measure) {
            if (measure.kind === 'related') {
                const condition = measure.condition ? ' WHERE ' + measure.condition : '';

                return measure.aggregation + '(' + this.getRelatedLabel(measure) + ': ' + (measure.expression || 'id') + ')' + condition;
            }

            if (measure.kind === 'native') {
                const condition = measure.condition ? ' WHERE ' + measure.condition : '';

                return measure.aggregation + '(' + (measure.expression || 'id') + ')' + condition;
            }

            return (measure.kind === 'display' ? '= ' : '') + measure.formula + (measure.condition ? ' WHERE ' + measure.condition : '');
        }

        renderMeasureList() {
            const list = this.definition.measures;
            const container = this.element.querySelector('[data-role="measures"]');

            const items = list.map((measure, index) => {
                const aggregationList = measure.kind === 'related' ?
                    ['SUM', 'COUNT', 'AVG', 'MIN', 'MAX'] :
                    ['SUM', 'COUNT', 'COUNT_DISTINCT', 'AVG', 'MIN', 'MAX'];

                const aggregation = measure.kind === 'native' || measure.kind === 'related' ?
                    `<select class="acx-chip-select" data-measure-aggregation="${index}" title="${this.escapeString(this.t('Aggregation'))}">` +
                    aggregationList.map(a =>
                        `<option value="${a}"${a === measure.aggregation ? ' selected' : ''}>${this.escapeString(this.t(a, 'aggregations'))}</option>`).join('') +
                    '</select>' : '';

                const eye = aggregation + `<a role="button" data-action="toggleMeasure" data-index="${index}"
                    title="${this.escapeString(this.t('Show / hide'))}"><span class="far fa-eye${measure.hidden ? '-slash' : ''}"></span></a>`;

                return `<li class="acx-chip${measure.hidden ? ' acx-hidden-measure' : ''}" draggable="true"
                    data-drag-axis="measures" data-drag-index="${index}">
                    <span class="acx-chip-grip fas fa-grip-vertical"></span>
                    <span class="acx-chip-body" data-action="editMeasure" data-index="${index}">
                        <span class="acx-chip-label">${this.escapeString(measure.label)}</span>
                        <span class="acx-chip-meta" title="${this.escapeString(this.describeMeasure(measure))}">${this.escapeString(this.describeMeasure(measure))}</span>
                    </span>
                    ${this.chipActions('measures', index, list.length, eye)}
                </li>`;
            }).join('');

            container.innerHTML = `
                <div class="acx-section-title">
                    <span>${this.escapeString(this.t('Measures'))}</span>
                    <span class="dropdown">
                        <a role="button" class="dropdown-toggle" data-toggle="dropdown" title="${this.escapeString(this.t('Add'))}">
                            <span class="fas fa-plus"></span></a>
                        <ul class="dropdown-menu pull-right">
                            <li><a role="button" data-action="quickMeasure"><span class="fas fa-bolt fa-fw"></span> ${this.escapeString(this.t('Field value…'))}</a></li>
                            <li class="divider"></li>
                            <li><a role="button" data-action="addMeasure" data-kind="native">${this.escapeString(this.t('native', 'measureKinds'))}</a></li>
                            <li><a role="button" data-action="addMeasure" data-kind="aggregate">${this.escapeString(this.t('aggregate', 'measureKinds'))}</a></li>
                            <li><a role="button" data-action="addMeasure" data-kind="display">${this.escapeString(this.t('display', 'measureKinds'))}</a></li>
                        </ul>
                    </span>
                </div>
                <ul class="acx-chips" data-drop-axis="measures">${items}</ul>
            `;
        }

        renderViewControls() {
            const view = this.definition.options.view;
            const visibleMeasures = this.definition.measures.filter(m => !m.hidden);

            this.element.querySelector('[data-role="modes"]').innerHTML = [
                ['table', 'fas fa-table'], ['chart', 'fas fa-chart-bar'], ['kpi', 'fas fa-tachometer-alt'],
            ].map(([mode, icon]) => `<button type="button" class="btn btn-default btn-sm${view.mode === mode ? ' active' : ''}"
                data-action="setMode" data-mode="${mode}"><span class="${icon}"></span> ${this.escapeString(this.t(mode, 'modes'))}</button>`).join('');

            const chartType = this.element.querySelector('[data-name="chartType"]');
            const chartMeasure = this.element.querySelector('[data-name="chartMeasure"]');

            chartType.innerHTML = CHART_TYPES.map(type =>
                `<option value="${type}"${type === (view.chartType || 'column') ? ' selected' : ''}>${this.escapeString(this.t(type, 'chartTypes'))}</option>`).join('');
            chartMeasure.innerHTML = visibleMeasures.map(m =>
                `<option value="${this.escapeString(m.key)}"${m.key === view.chartMeasure ? ' selected' : ''}>${this.escapeString(m.label)}</option>`).join('');

            chartType.classList.toggle('hidden', view.mode !== 'chart');
            chartMeasure.classList.toggle('hidden', view.mode !== 'chart' || visibleMeasures.length < 2);

            const layout = this.element.querySelector('[data-name="layout"]');

            layout.innerHTML = ['compact', 'tabular'].map(item =>
                `<option value="${item}"${item === (view.layout || 'compact') ? ' selected' : ''}>${this.escapeString(this.t(item, 'layouts'))}</option>`).join('');
            layout.classList.toggle('hidden', view.mode !== 'table');
            this.element.querySelector('[data-role="table-tools"]').classList.toggle('hidden', view.mode !== 'table');
        }

        setViewOption(name, value) {
            this.definition.options.view[name] = value;
            this.renderViewControls();
            this.markChanged(false);
            this.renderResult();
        }

        changeEntityType(entityType) {
            const options = this.definition.options;

            this.definition = this.createDefaultDefinition(entityType);

            Schema.setCustomJoins(entityType, this.definition.joins);
            this.definition.options = {...options, view: options.view};

            this.clearView('filters');
            this.setupFilterView();
            this.getView('filters').render();

            this.renderPanels();
            this.markChanged();
        }

        markChanged(rerun = true) {
            this.dirty = true;
            this.updateDirty();
            this.pushHistory();
            this.renderGuide();
            this.refreshPipeline();

            if (rerun) {
                clearTimeout(this.runTimeout);
                this.runTimeout = setTimeout(() => this.run(), 350);
            }
        }

        updateDirty() {
            this.element.querySelector('[data-role="dirty"]').classList.toggle('hidden', !this.dirty);
            this.getRouter().confirmLeaveOut = this.dirty && !this.isNew;
        }

        updateStar() {
            const button = this.element && this.element.querySelector('[data-action="toggleStar"]');

            if (!button) {
                return;
            }

            const starred = !!this.model.get('isStarred');

            button.classList.toggle('hidden', this.isNew || !this.model.has('isStarred'));
            button.classList.toggle('active', starred);
            button.querySelector('span').className = (starred ? 'fas' : 'far') + ' fa-star';
        }

        async toggleStar() {
            const starred = !!this.model.get('isStarred');
            const url = `AdvancedCrosstab/${this.model.id}/starSubscription`;

            await (starred ? Espo.Ajax.deleteRequest(url) : Espo.Ajax.putRequest(url));

            this.model.set('isStarred', !starred, {sync: true});
        }

        // --- Dimensions & measures --------------------------------------------------------------------------

        measureOptions(exceptIndex = null) {
            return this.definition.measures
                .filter((m, i) => i !== exceptIndex)
                .map(m => ({key: m.key, label: m.label}));
        }

        nextDimensionId(axis) {
            const prefix = axis === 'rows' ? 'r' : 'c';
            const used = this.definition.rows.concat(this.definition.columns).map(d => d.id);
            let i = 0;

            while (used.includes(prefix + i)) {
                i++;
            }

            return prefix + i;
        }

        editDimension(axis, index) {
            const list = this.definition[axis];
            const existing = index === null ? null : list[index];

            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/dimension', {
                entityType: this.definition.entityType,
                dimension: existing,
                measures: this.measureOptions(),
                onApply: dimension => {
                    dimension.id = existing ? existing.id : this.nextDimensionId(axis);

                    if (existing) {
                        list[index] = dimension;
                    } else {
                        list.push(dimension);
                    }

                    this.renderDimensionList(axis);
                    this.markChanged();
                },
            }).then(view => view.render());
        }

        editMeasure(index, kind) {
            const existing = index === null ? null : this.definition.measures[index];
            const position = index === null ? this.definition.measures.length : index;

            const related = existing && existing.kind === 'related' ? this.getRelatedTarget(existing) : null;

            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/measure', {
                entityType: related ? related.entityType : this.definition.entityType,
                relatedLabel: related ? this.getRelatedLabel(existing) : null,
                measure: existing,
                kind: kind,
                // Display formulas may reference the measures defined before them.
                measures: this.definition.measures.slice(0, position).map(m => ({key: m.key, label: m.label})),
                usedKeys: this.definition.measures.filter((m, i) => i !== index).map(m => m.key),
                onApply: measure => {
                    if (existing) {
                        this.renameMeasureReferences(existing.key, measure.key);
                        this.definition.measures[index] = measure;
                    } else {
                        this.definition.measures.push(measure);
                    }

                    this.renderMeasureList();
                    this.renderViewControls();
                    this.markChanged();
                },
            }).then(view => view.render());
        }

        renameMeasureReferences(oldKey, newKey) {
            if (oldKey === newKey) {
                return;
            }

            for (const dimension of this.definition.rows.concat(this.definition.columns)) {
                if (dimension.sort && dimension.sort.measure === oldKey) {
                    dimension.sort.measure = newKey;
                }

                if (dimension.limit && dimension.limit.measure === oldKey) {
                    dimension.limit.measure = newKey;
                }
            }
        }

        toggleMeasure(index) {
            const measure = this.definition.measures[index];

            if (!measure.hidden && this.definition.measures.filter(m => !m.hidden).length === 1) {
                Espo.Ui.warning(this.t('At least one measure must be visible'));

                return;
            }

            measure.hidden = !measure.hidden;

            this.renderMeasureList();
            this.renderViewControls();
            this.markChanged();
        }

        removeItem(axis, index) {
            const list = this.definition[axis];

            if (axis === 'measures') {
                const key = list[index].key;
                const usedBy = this.definition.rows.concat(this.definition.columns)
                    .some(d => (d.sort && d.sort.measure === key) || (d.limit && d.limit.measure === key));

                if (list.length === 1 || usedBy) {
                    Espo.Ui.warning(this.t(list.length === 1 ? 'At least one measure is required' : 'Measure is used for sorting'));

                    return;
                }
            }

            list.splice(index, 1);
            this.renderPanels();
            this.markChanged();
        }

        moveItem(axis, index, direction) {
            const list = this.definition[axis];
            const target = index + direction;

            if (target < 0 || target >= list.length) {
                return;
            }

            [list[index], list[target]] = [list[target], list[index]];

            this.renderPanels();
            this.markChanged();
        }

        swapAxes() {
            [this.definition.rows, this.definition.columns] = [this.definition.columns, this.definition.rows];

            this.renderPanels();
            this.markChanged();
        }

        // --- Running -----------------------------------------------------------------------------------------

        /**
         * The definition sent to the server: incomplete filter conditions are left out.
         */
        getRunDefinition() {
            const clean = node => {
                if (!node) {
                    return null;
                }

                if (['and', 'or', 'not'].includes(node.type)) {
                    const items = node.items.map(clean).filter(Boolean);

                    return items.length ? {type: node.type, items} : null;
                }

                if (node.type === 'formula') {
                    return node.formula && node.formula.trim() ? {type: 'formula', formula: node.formula} : null;
                }

                const value = node.value;
                const empty = value === null || value === undefined || value === '' ||
                    (Array.isArray(value) && (!value.length || value.some(v => v === null || v === '')));

                if (!Operators.hasNoValue(node.operator) && empty) {
                    return null;
                }

                const condition = {type: 'condition', path: node.path, operator: node.operator, value: value};

                // Record names, kept for display only.
                if (node.valueNames) {
                    condition.valueNames = node.valueNames;
                }

                return condition;
            };

            const definition = Espo.Utils.cloneDeep(this.definition);

            definition.filter = clean(definition.filter);

            return definition;
        }

        getSource() {
            return this.dirty || this.isNew ? {definition: this.getRunDefinition()} : {id: this.model.id};
        }

        async run(noCache = false) {
            const requestId = ++this.requestId;
            const source = this.getSource();
            const info = this.element.querySelector('[data-role="info"]');

            info.innerHTML = '<span class="fas fa-spinner fa-spin"></span>';

            let result;

            try {
                result = source.id ?
                    await Espo.Ajax.postRequest(`AdvancedCrosstab/${source.id}/run`, {noCache}) :
                    await Espo.Ajax.postRequest('AdvancedCrosstab/action/run', {definition: source.definition, noCache});
            } catch (e) {
                if (requestId === this.requestId) {
                    const reason = e && e.getResponseHeader ? e.getResponseHeader('X-Status-Reason') : null;

                    this.error = reason || this.t('Error');
                    this.result = null;
                    this.refreshPipeline();
                    info.innerHTML = '';
                    this.element.querySelector('[data-role="result"]').innerHTML =
                        `<div class="alert alert-danger">${this.escapeString(reason || this.t('Error'))}</div>`;

                    if (e) {
                        e.errorIsHandled = true;
                    }
                }

                return;
            }

            // A newer request was sent meanwhile.
            if (requestId !== this.requestId) {
                return;
            }

            this.result = result;
            this.resultSource = source;
            this.error = null;
            this.refreshPipeline();

            info.textContent = (result.fromCache ? this.t('Cached') + ' · ' : '') +
                result.queryCount + ' ' + this.t('queries') + ' · ' + result.durationMs + ' ms';

            this.renderResult();
        }

        renderResult() {
            if (!this.result) {
                return;
            }

            const view = this.definition.options.view;

            this.createView('result', 'advanced-crosstab:views/advanced-crosstab/result/panel', {
                selector: '[data-role="result"]',
                result: this.result,
                mode: view.mode,
                chartType: view.chartType,
                chartMeasure: view.chartMeasure,
                layout: view.layout,
                source: this.resultSource,
            }).then(panel => panel.render());
        }

        tableView() {
            const panel = this.getView('result');

            return panel ? panel.getTableView() : null;
        }

        // --- Persistence ---------------------------------------------------------------------------------------

        getName() {
            return this.element.querySelector('[data-name="name"]').value.trim();
        }

        async save() {
            const name = this.getName();

            if (!name) {
                Espo.Ui.warning(this.t('Enter a name'));
                this.element.querySelector('[data-name="name"]').focus();

                return;
            }

            Espo.Ui.notifyWait();

            await this.model.save({name: name, definition: this.getRunDefinition()}, {patch: !this.isNew});

            Espo.Ui.success(this.translate('Saved'));

            this.dirty = false;
            this.updateDirty();

            if (this.isNew) {
                this.getRouter().navigate(`#AdvancedCrosstab/view/${this.model.id}`, {trigger: true});
            }
        }

        async saveAs() {
            const model = await this.getModelFactory().create('AdvancedCrosstab');

            model.set({
                name: (this.getName() || this.t('Untitled crosstab')) + ' (' + this.t('copy') + ')',
                description: this.model.get('description'),
                definition: this.getRunDefinition(),
            });

            this.createView('dialog', 'views/modals/edit', {
                scope: 'AdvancedCrosstab',
                model: model,
                layoutName: 'detailSmall',
            }).then(view => {
                view.render();

                this.listenToOnce(view, 'after:save', () => {
                    this.getRouter().navigate(`#AdvancedCrosstab/view/${model.id}`, {trigger: true});
                });
            });
        }

        editProperties() {
            this.createView('dialog', 'views/modals/edit', {
                scope: 'AdvancedCrosstab',
                id: this.model.id,
                layoutName: 'detailSmall',
            }).then(view => {
                view.render();

                this.listenToOnce(view, 'after:save', model => {
                    this.model.set({name: model.get('name'), description: model.get('description')});
                    this.element.querySelector('[data-name="name"]').value = model.get('name');
                });
            });
        }

        async removeRecord() {
            await this.confirm(this.translate('removeRecordConfirmation', 'messages'));

            await this.model.destroy();

            this.getRouter().confirmLeaveOut = false;
            this.getRouter().navigate('#AdvancedCrosstab', {trigger: true});
        }

        // --- Export --------------------------------------------------------------------------------------------

        async exportResult(format) {
            const source = this.getSource();
            const title = this.getName() || this.t('Untitled crosstab');

            Espo.Ui.notifyWait();

            const response = source.id ?
                await Espo.Ajax.postRequest(`AdvancedCrosstab/${source.id}/export`, {format, title}) :
                await Espo.Ajax.postRequest('AdvancedCrosstab/action/export', {definition: source.definition, format, title});

            if (response.async) {
                Espo.Ui.notify(this.t('exportScheduled', 'messages'), 'success', 6000);

                return;
            }

            Espo.Ui.notify(false);

            window.location = this.getBasePath() + '?entryPoint=download&id=' + response.attachmentId;
        }

        print() {
            const body = this.element.querySelector('[data-role="result"]');
            const styles = document.getElementById('advanced-crosstab-styles');
            const win = window.open('', '_blank');

            if (!win) {
                return;
            }

            win.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>${this.escapeString(this.getName())}</title>
                <style>${styles ? styles.textContent : ''}
                    body { font-family: Arial, sans-serif; font-size: 11px; color: #000; background: #fff; margin: 16px; }
                    table { border-collapse: collapse; } th, td { border: 1px solid #bbb; padding: 2px 6px; }
                    .acx-table-wrap { max-height: none !important; overflow: visible !important; }
                    .acx-toggle { display: none; } thead th { position: static !important; }
                </style></head><body><h3>${this.escapeString(this.getName())}</h3>${body.innerHTML}</body></html>`);
            win.document.close();
            win.focus();
            setTimeout(() => win.print(), 300);
        }

        /**
         * One-click measure from a field: SUM for numeric fields, COUNT (non-empty values) otherwise.
         */
        quickMeasure() {
            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/field-picker', {
                entityType: this.definition.entityType,
                purpose: 'any',
                onSelect: (path, info) => this.addMeasureFromPath(path, info),
            }).then(view => view.render());
        }

        addMeasureFromPath(path, info) {
            const numeric = Schema.NUMERIC_TYPES.includes(info.type);
            const used = this.definition.measures.map(m => m.key);
            let key = path.replace(/\.(.)/g, (m, c) => c.toUpperCase()).replace(/[^a-zA-Z0-9_]/g, '');
            let i = 2;

            while (used.includes(key) || ['id', 'null', 'true', 'false'].includes(key.toLowerCase())) {
                key = key.replace(/\d+$/, '') + i++;
        }

        const measure = {
            key: key,
            label: info.label,
            kind: 'native',
            aggregation: numeric ? 'SUM' : 'COUNT',
            expression: path,
        };

        if (info.type === 'currency') {
            measure.format = {type: 'currency'};
        }

        this.definition.measures.push(measure);
        this.renderMeasureList();
        this.renderViewControls();
        this.markChanged();
        }

        addDimensionFromPath(axis, path, info) {
            const dimension = {id: this.nextDimensionId(axis), type: 'field', path: path};

            if (Schema.DATE_TYPES.includes(info.type)) {
                dimension.granularity = 'yearMonth';
            }

            this.definition[axis].push(dimension);
            this.renderDimensionList(axis);
            this.markChanged();
        }

        addFilterFromPath(path, info) {
            const operator = Operators.forType(info.type)[0];

            this.getView('filters').addItem('', {
                type: 'condition',
                path: path,
                operator: operator,
                value: Operators.isDays(operator) ? 7 : null,
            });
        }

        /**
         * Where each field path is used, for the data model view: {path: ['R', 'C', 'M', 'F']}.
         */
        getPathUsage() {
            const usage = {};
            const add = (path, mark) => {
                if (!path) {
                    return;
                }

                usage[path] = usage[path] || [];

                if (!usage[path].includes(mark)) {
                    usage[path].push(mark);
                }
            };

            this.definition.rows.forEach(d => add(d.path, 'R'));
            this.definition.columns.forEach(d => add(d.path, 'C'));
            this.definition.measures.forEach(m => add(m.expression && /^[a-zA-Z0-9.]+$/.test(m.expression) ? m.expression : null, 'M'));

            const walk = node => {
                if (!node) {
                    return;
                }

                if (node.items) {
                    node.items.forEach(walk);
                }

                if (node.type === 'condition') {
                    add(node.path, 'F');
                }
            };

            walk(this.definition.filter);

            return usage;
        }

        /**
         * Visual data model (MCD): entity boxes and associations; fields go to rows, columns, measures, filters.
         */
        openDataModel() {
            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/data-model', {
                entityType: this.definition.entityType,
                getUsage: () => this.getPathUsage(),
                getJoins: () => this.definition.joins,
                onAddJoin: (from, callback) => this.openCustomJoin(from, callback),
                onUse: (target, path, info) => {
                    if (target === 'related') {
                        this.addRelatedMeasure(info.link, info.from || '', path, info);
                    } else if (target === 'rows' || target === 'columns') {
                        this.addDimensionFromPath(target, path, info);
                    } else if (target === 'measures') {
                        this.addMeasureFromPath(path, info);
                    } else {
                        this.addFilterFromPath(path, info);
                    }
                },
                onChangeSource: entityType => {
                    this.element.querySelector('[data-name="entityType"]').value = entityType;
                    this.changeEntityType(entityType);
                },
            }).then(view => view.render());
        }

        // --- Links to any entity and related measures ---------------------------------------------------------------

        renderJoins() {
            const container = this.element.querySelector('[data-role="joins"]');
            const joins = this.definition.joins;

            const items = joins.map(join => {
                const fromLabel = (join.from ? this.schema.getPathLabel(this.definition.entityType, join.from) + ' › ' : '') +
                    this.schema.translateField(join.from ?
                        this.schema.resolvePath(this.definition.entityType, join.from + '.id').entityType :
                        this.definition.entityType, join.localField);
                const toLabel = this.schema.translateEntity(join.entityType, false) + ' › ' +
                    this.schema.translateField(join.entityType, join.foreignField);

                return `<li class="acx-chip acx-join-chip">
                    <span class="acx-chip-body">
                        <span class="acx-chip-label"><span class="fas fa-link"></span> ${this.escapeString(this.schema.getCustomJoinLabel(join))}</span>
                        <span class="acx-chip-meta" title="${this.escapeString(fromLabel + ' = ' + toLabel)}">${this.escapeString(fromLabel + ' = ' + toLabel)}</span>
                    </span>
                    <span class="acx-chip-actions"><a role="button" data-action="removeJoin" data-name="${this.escapeString(join.name)}"
                        title="${this.escapeString(this.translate('Remove'))}"><span class="fas fa-times"></span></a></span>
                </li>`;
            }).join('');

            container.innerHTML = `
                <div class="acx-section-title">
                    <span>${this.escapeString(this.t('Links'))}</span>
                    <a role="button" data-action="addJoin" title="${this.escapeString(this.t('Link another entity'))}">
                        <span class="fas fa-plus"></span></a>
                </div>
                <ul class="acx-chips">${items}</ul>
                ${joins.length ? '' : `<div class="acx-empty-hint">${this.escapeString(this.t('No custom links'))}</div>`}
            `;
        }

        openCustomJoin(from, callback) {
            // Own key: it can open on top of the data model dialog.
            this.createView('joinDialog', 'advanced-crosstab:views/advanced-crosstab/modals/custom-join', {
                rootEntityType: this.definition.entityType,
                from: from || '',
                joins: this.definition.joins,
                onApply: join => {
                    this.definition.joins.push(join);
                    Schema.setCustomJoins(this.definition.entityType, this.definition.joins);
                    this.renderJoins();
                    this.markChanged();

                    if (callback) {
                        callback(join);
                    }
                },
            }).then(view => view.render());
        }

        removeCustomJoin(name) {
            const used = new RegExp('(^|[^a-zA-Z0-9_])' + name + '\\.');
            const definition = Espo.Utils.cloneDeep(this.definition);

            delete definition.joins;

            const json = JSON.stringify(definition);

            if (used.test(json) || definition.measures.some(m => m.kind === 'related' && m.link === name) ||
                this.definition.joins.some(j => j.from && (j.from === name || j.from.startsWith(name + '.')))) {
                Espo.Ui.warning(this.t('Custom link is in use'));

                return;
            }

            this.definition.joins = this.definition.joins.filter(j => j.name !== name);
            Schema.setCustomJoins(this.definition.entityType, this.definition.joins);
            this.renderJoins();
            this.markChanged();
        }

        /**
         * The entity type and label of a related measure's link (to-many link or custom link).
         */
        getRelatedTarget(measure) {
            const join = this.schema.getCustomJoin(this.definition.entityType, measure.link);

            if (join) {
                return {entityType: join.entityType, label: this.schema.getCustomJoinLabel(join)};
            }

            const owner = measure.from ?
                this.schema.resolvePath(this.definition.entityType, measure.from + '.id').entityType :
                this.definition.entityType;
            const link = this.schema.getToManyLinkList(owner).find(item => item.name === measure.link);

            return link ? {entityType: link.entityType, label: link.label} : {entityType: owner, label: measure.link};
        }

        getRelatedLabel(measure) {
            return (measure.from ? this.schema.getPathLabel(this.definition.entityType, measure.from) + ' › ' : '') +
                this.getRelatedTarget(measure).label;
        }

        /**
         * Aggregation over related records (one-to-many, many-to-many or custom link): SUM for numbers, COUNT otherwise.
         */
        addRelatedMeasure(link, from, path, info) {
            const numeric = Schema.NUMERIC_TYPES.includes(info.type);
            const used = this.definition.measures.map(m => m.key);
            let key = (link + '_' + path).replace(/\.(.)/g, (m, c) => c.toUpperCase()).replace(/[^a-zA-Z0-9_]/g, '');
            let i = 2;

            while (used.includes(key)) {
                key = key.replace(/\d+$/, '') + i++;
            }

            const measure = {
                key: key,
                label: info.relatedLabel + ' › ' + (path === 'id' ? this.t('Count') : info.label),
                kind: 'related',
                link: link,
                aggregation: numeric ? 'SUM' : 'COUNT',
            };

            if (from) {
                measure.from = from;
            }

            if (path !== 'id') {
                measure.expression = path;
            }

            if (info.type === 'currency') {
                measure.format = {type: 'currency'};
            }

            this.definition.measures.push(measure);
            this.renderMeasureList();
            this.renderViewControls();
            this.markChanged();
        }

        // --- Workspace: design / pipeline (ETL) --------------------------------------------------------------------

        getStoredWorkspace() {
            try {
                return localStorage.getItem('advancedCrosstab.workspace') === 'pipeline' ? 'pipeline' : 'design';
            } catch (e) {
                return 'design';
            }
        }

        setWorkspace(workspace, initial = false) {
            this.workspace = workspace === 'pipeline' ? 'pipeline' : 'design';

            try {
                localStorage.setItem('advancedCrosstab.workspace', this.workspace);
            } catch (e) {}

            const isPipeline = this.workspace === 'pipeline';

            this.element.querySelectorAll('[data-action="setWorkspace"]').forEach(button =>
                button.classList.toggle('active', button.dataset.workspace === this.workspace));

            ['toolbar', 'result', 'guide'].forEach(role =>
                this.element.querySelector(`[data-role="${role}"]`).classList.toggle('hidden', isPipeline));
            this.element.querySelector('[data-role="pipeline"]').classList.toggle('hidden', !isPipeline);
            this.element.classList.toggle('acx-pipeline-mode', isPipeline);

            if (!isPipeline) {
                this.selectStage(null);

                if (!initial) {
                    // Charts measure their container: redraw now that it is visible.
                    this.renderResult();
                }

                return;
            }

            if (this.getView('pipeline')) {
                this.getView('pipeline').refresh();

                return;
            }

            this.createView('pipeline', 'advanced-crosstab:views/advanced-crosstab/pipeline', {
                selector: '[data-role="pipeline"]',
                getDefinition: () => this.definition,
                getRunDefinition: () => this.getRunDefinition(),
                getResult: () => this.result,
                getError: () => this.error,
                selected: this.stage,
                onSelect: stage => this.selectStage(stage),
                onComponent: name => this.addComponent(name),
            }).then(view => view.render());
        }

        refreshPipeline() {
            const view = this.workspace === 'pipeline' ? this.getView('pipeline') : null;

            if (view) {
                view.refresh();
            }
        }

        /**
         * The sidebar becomes the properties panel of the selected pipeline step: only its sections are shown.
         */
        selectStage(stage) {
            this.stage = stage;

            const head = this.element.querySelector('[data-role="properties-head"]');

            this.element.querySelectorAll('.acx-sidebar [data-stage]').forEach(section => {
                section.classList.toggle('acx-stage-hidden', !!stage && !section.dataset.stage.split(' ').includes(stage));
            });

            head.classList.toggle('hidden', !stage);
            head.innerHTML = stage ? `
                <span><span class="fas fa-sliders-h"></span> ${this.escapeString(this.t('Properties'))} ·
                    <strong>${this.escapeString(this.t('stage.' + stage, 'messages'))}</strong></span>
                <a role="button" data-action="showAllSections">${this.escapeString(this.t('Show all'))}</a>` : '';
        }

        /**
         * Palette components of the pipeline view.
         */
        addComponent(name) {
            const actions = {
                join: () => this.openCustomJoin(''),
                related: () => this.openDataModel(),
                filter: () => this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/field-picker', {
                    entityType: this.definition.entityType,
                    purpose: 'any',
                    onSelect: (path, info) => {
                        this.addFilterFromPath(path, info);
                        this.selectStage('filter');
                    },
                }).then(view => view.render()),
                calculated: () => this.editMeasure(null, 'aggregate'),
                row: () => this.editDimension('rows', null),
                column: () => this.editDimension('columns', null),
                measure: () => this.quickMeasure(),
            };

            if (actions[name]) {
                actions[name]();
            }
        }

        // --- Undo / redo ---------------------------------------------------------------------------------------

        pushHistory() {
            const snapshot = JSON.stringify(this.definition);

            if (this.restoring || snapshot === this.history[this.historyIndex]) {
                return;
            }

            this.history = this.history.slice(0, this.historyIndex + 1);
            this.history.push(snapshot);

            if (this.history.length > 100) {
                this.history.shift();
            }

            this.historyIndex = this.history.length - 1;
            this.updateHistoryButtons();
        }

        undo() {
            this.restoreHistory(this.historyIndex - 1);
        }

        redo() {
            this.restoreHistory(this.historyIndex + 1);
        }

        restoreHistory(index) {
            // Filter edits are debounced in the filter builder: record the pending state first.
            this.pushHistory();

            if (index < 0 || index >= this.history.length) {
                return;
            }

            const previousEntityType = this.definition.entityType;

            this.historyIndex = index;
            this.definition = JSON.parse(this.history[index]);

            Schema.setCustomJoins(this.definition.entityType, this.definition.joins);

            this.restoring = true;

            this.clearView('filters');
            this.setupFilterView();
            this.getView('filters').render();

            if (previousEntityType !== this.definition.entityType) {
                this.element.querySelector('[data-name="entityType"]').value = this.definition.entityType;
            }

            this.element.querySelectorAll('[data-option]').forEach(input => {
                input.checked = this.definition.options[input.dataset.option] !== false;
            });

            this.renderPanels();
            this.selectStage(this.stage);
            this.markChanged();
            this.restoring = false;
            this.updateHistoryButtons();
        }

        updateHistoryButtons() {
            const undo = this.element.querySelector('[data-action="undo"]');
            const redo = this.element.querySelector('[data-action="redo"]');

            if (undo) {
                undo.disabled = this.historyIndex <= 0;
                redo.disabled = this.historyIndex >= this.history.length - 1;
            }
        }

        // --- Keyboard shortcuts ----------------------------------------------------------------------------------

        onKeyDown(e) {
            if (!this.element || !document.body.contains(this.element)) {
                return;
            }

            if (e.key === 'Escape' && this.element.classList.contains('acx-fullscreen')) {
                this.toggleFullscreen();

                return;
            }

            const ctrl = e.ctrlKey || e.metaKey;

            // Shortcuts are for the designer page, not for its dialogs.
            if (!ctrl || document.querySelector('.modal.in, .modal.show')) {
                return;
            }

            const key = e.key.toLowerCase();
            const inField = e.target.closest && e.target.closest('input, textarea, select, [contenteditable]');

            if (key === 's') {
                e.preventDefault();

                if (!this.element.querySelector('[data-action="save"]').classList.contains('hidden')) {
                    this.save();
                }

                return;
            }

            if (key === 'enter') {
                e.preventDefault();
                this.run(true);

                return;
            }

            if (inField) {
                return;
            }

            if (key === 'z' && !e.shiftKey) {
                e.preventDefault();
                this.undo();
            } else if ((key === 'z' && e.shiftKey) || key === 'y') {
                e.preventDefault();
                this.redo();
            }
        }

        // --- Drag and drop of chips -------------------------------------------------------------------------------

        /**
         * Rows and columns chips can be reordered and moved between the two axes; measures can be reordered.
         */
        setupChipDragging() {
            const sidebar = this.element.querySelector('.acx-sidebar');
            let dragged = null;

            const clearMarks = () => sidebar.querySelectorAll('.acx-drop-before, .acx-drop-target')
                .forEach(el => el.classList.remove('acx-drop-before', 'acx-drop-target'));

            const accepts = axis => dragged &&
                (dragged.axis === 'measures' ? axis === 'measures' : axis === 'rows' || axis === 'columns');

            sidebar.addEventListener('dragstart', e => {
                const chip = e.target.closest && e.target.closest('[data-drag-axis]');

                if (!chip) {
                    return;
                }

                dragged = {axis: chip.dataset.dragAxis, index: parseInt(chip.dataset.dragIndex)};
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', 'acx-chip');
                setTimeout(() => chip.classList.add('acx-chip-dragging'), 0);
            });

            sidebar.addEventListener('dragend', () => {
                dragged = null;
                clearMarks();
                sidebar.querySelectorAll('.acx-chip-dragging').forEach(el => el.classList.remove('acx-chip-dragging'));
            });

            sidebar.addEventListener('dragover', e => {
                const zone = e.target.closest && e.target.closest('[data-drop-axis]');

                if (!zone || !accepts(zone.dataset.dropAxis)) {
                    return;
                }

                e.preventDefault();
                clearMarks();

                const chip = e.target.closest('[data-drag-axis]');

                (chip || zone).classList.add(chip ? 'acx-drop-before' : 'acx-drop-target');
            });

            sidebar.addEventListener('drop', e => {
                const zone = e.target.closest && e.target.closest('[data-drop-axis]');

                if (!zone || !accepts(zone.dataset.dropAxis)) {
                    return;
                }

                e.preventDefault();

                const chip = e.target.closest('[data-drag-axis]');
                const targetAxis = zone.dataset.dropAxis;
                const targetIndex = chip ? parseInt(chip.dataset.dragIndex) : this.definition[targetAxis].length;

                this.moveChip(dragged.axis, dragged.index, targetAxis, targetIndex);
                dragged = null;
                clearMarks();
            });
        }

        moveChip(fromAxis, fromIndex, toAxis, toIndex) {
            const source = this.definition[fromAxis];
            const target = this.definition[toAxis];
            const [item] = source.splice(fromIndex, 1);

            if (fromAxis === toAxis && fromIndex < toIndex) {
                toIndex--;
            }

            target.splice(Math.min(toIndex, target.length), 0, item);

            if (fromAxis !== toAxis) {
                item.id = this.nextDimensionId(toAxis);
            }

            if (fromAxis === toAxis && fromIndex === toIndex) {
                return;
            }

            this.renderPanels();
            this.selectStage(this.stage);
            this.markChanged();
        }

        // --- Empty state ---------------------------------------------------------------------------------------------

        renderGuide() {
            const container = this.element.querySelector('[data-role="guide"]');

            if (!container) {
                return;
            }

            const d = this.definition;

            if (d.rows.length || d.columns.length) {
                container.innerHTML = '';

                return;
            }

            const step = (n, text, action, icon, data = '') => `
                <li><span class="acx-guide-step">${n}</span>
                    <span>${this.escapeString(this.t(text, 'messages'))}</span>
                    ${action ? `<button type="button" class="btn btn-default btn-xs" data-action="${action}" ${data}>
                        <span class="${icon}"></span></button>` : ''}
                </li>`;

            container.innerHTML = `
                <div class="acx-guide">
                    <div class="acx-guide-title"><span class="fas fa-lightbulb"></span> ${this.escapeString(this.t('guide.title', 'messages'))}</div>
                    <ol>
                        ${step(1, 'guide.source', 'guideDataModel', 'fas fa-project-diagram')}
                        ${step(2, 'guide.rows', 'addDimension', 'fas fa-plus', 'data-axis="rows"')}
                        ${step(3, 'guide.columns', 'addDimension', 'fas fa-plus', 'data-axis="columns"')}
                        ${step(4, 'guide.measures', 'quickMeasure', 'fas fa-bolt')}
                        ${step(5, 'guide.pipeline', 'guidePipeline', 'fas fa-stream')}
                    </ol>
                    <div class="small text-muted">${this.escapeString(this.t('guide.shortcuts', 'messages'))}</div>
                </div>`;
        }

        toggleFullscreen() {
            const on = this.element.classList.toggle('acx-fullscreen');
            const icon = this.element.querySelector('[data-action="fullscreen"] span');

            icon.className = 'fas fa-' + (on ? 'compress' : 'expand');
            document.body.classList.toggle('acx-body-fullscreen', on);

            // Charts adapt to the new width.
            window.dispatchEvent(new Event('resize'));
        }

        onRemove() {
            document.removeEventListener('keydown', this.escapeHandler);
            document.body.classList.remove('acx-body-fullscreen');

            this.getRouter().confirmLeaveOut = false;
            clearTimeout(this.runTimeout);
        }
    };
});
