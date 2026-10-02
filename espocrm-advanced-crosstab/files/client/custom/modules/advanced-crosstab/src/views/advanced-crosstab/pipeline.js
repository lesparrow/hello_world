define('advanced-crosstab:views/advanced-crosstab/pipeline', ['view', 'advanced-crosstab:lib/schema'], function (View, Schema) {

    const STAGES = ['source', 'lookups', 'filter', 'calculate', 'aggregate', 'output'];

    const STAGE_ICONS = {
        source: 'fas fa-database',
        lookups: 'fas fa-link',
        filter: 'fas fa-filter',
        calculate: 'fas fa-calculator',
        aggregate: 'fas fa-layer-group',
        output: 'fas fa-table',
    };

    const COMPONENTS = [
        {name: 'join', icon: 'fas fa-link', stage: 'lookups'},
        {name: 'related', icon: 'fas fa-sigma', text: 'Σ', stage: 'lookups'},
        {name: 'filter', icon: 'fas fa-filter', stage: 'filter'},
        {name: 'calculated', icon: 'fas fa-calculator', stage: 'calculate'},
        {name: 'row', icon: 'fas fa-grip-lines', stage: 'aggregate'},
        {name: 'column', icon: 'fas fa-grip-lines-vertical', stage: 'aggregate'},
        {name: 'measure', icon: 'fas fa-bolt', stage: 'aggregate'},
    ];

    const PREVIEW_LIMIT = 30;

    /**
     * ETL-style view of a crosstab: Source → Lookups → Filter → Calculate → Aggregate → Output, with the number of
     * records flowing between steps (computed on the server under the user's ACL), a palette of components (click or
     * drag onto the canvas) and a data preview of the source and of the filtered records.
     *
     * Options: getDefinition(), getRunDefinition(), getResult(), getError(), selected, onSelect(stage),
     * onComponent(name).
     */
    return class extends View {

        templateContent = `
            <div class="acx-etl">
                <div class="acx-etl-palette">
                    <div class="acx-etl-palette-title">{{translate 'Components' scope='AdvancedCrosstab'}}</div>
                    <ul data-role="palette"></ul>
                    <div class="acx-etl-palette-hint small text-muted">{{translate 'paletteHint' category='messages' scope='AdvancedCrosstab'}}</div>
                </div>
                <div class="acx-etl-canvas" data-role="canvas"></div>
            </div>
            <div class="acx-etl-preview">
                <div class="acx-etl-preview-head">
                    <ul class="nav nav-tabs" data-role="preview-tabs">
                        <li data-stage="source"><a role="button" data-action="previewStage" data-stage="source">
                            <span class="fas fa-database"></span> {{translate 'Source data' scope='AdvancedCrosstab'}}</a></li>
                        <li data-stage="filtered"><a role="button" data-action="previewStage" data-stage="filtered">
                            <span class="fas fa-filter"></span> {{translate 'After filters' scope='AdvancedCrosstab'}}</a></li>
                    </ul>
                    <span class="acx-etl-preview-info small text-muted" data-role="preview-info"></span>
                </div>
                <div class="acx-etl-preview-body" data-role="preview"></div>
            </div>
        `

        setup() {
            this.schema = new Schema(this);
            this.selected = this.options.selected || null;
            this.previewStage = 'filtered';
            this.stats = {};
            this.previews = {};
            this.requestId = 0;

            this.addActionHandler('selectStage', (e, target) => this.select(target.closest('[data-stage]').dataset.stage));
            this.addActionHandler('component', (e, target) => this.options.onComponent(target.dataset.name));
            this.addActionHandler('previewStage', (e, target) => {
                this.previewStage = target.dataset.stage;
                this.renderPreview();
            });
        }

        afterRender() {
            this.canvas = this.element.querySelector('[data-role="canvas"]');

            this.element.querySelector('[data-role="palette"]').innerHTML = COMPONENTS.map(item => `
                <li draggable="true" data-component="${item.name}" data-action="component" data-name="${item.name}"
                    title="${this.escapeString(this.t('componentHint.' + item.name, 'messages'))}">
                    <span class="acx-etl-palette-icon acx-etl-${item.stage}">${item.text ?
                        `<strong>${item.text}</strong>` : `<span class="${item.icon}"></span>`}</span>
                    ${this.escapeString(this.t('component.' + item.name, 'messages'))}
                </li>`).join('');

            this.element.querySelectorAll('[data-component]').forEach(li => {
                li.addEventListener('dragstart', e => {
                    e.dataTransfer.setData('text/plain', 'acx-component:' + li.dataset.component);
                    e.dataTransfer.effectAllowed = 'copy';
                    this.canvas.classList.add('acx-drop-ready');
                });

                li.addEventListener('dragend', () => this.canvas.classList.remove('acx-drop-ready', 'acx-drop-over'));
            });

            this.canvas.addEventListener('dragover', e => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'copy';
                this.canvas.classList.add('acx-drop-over');
            });

            this.canvas.addEventListener('dragleave', e => {
                if (!this.canvas.contains(e.relatedTarget)) {
                    this.canvas.classList.remove('acx-drop-over');
                }
            });

            this.canvas.addEventListener('drop', e => {
                e.preventDefault();
                this.canvas.classList.remove('acx-drop-ready', 'acx-drop-over');

                const data = e.dataTransfer.getData('text/plain') || '';

                if (data.startsWith('acx-component:')) {
                    this.options.onComponent(data.substring('acx-component:'.length));
                }
            });

            this.renderCanvas();
            this.renderPreview();
            this.refresh();
        }

        t(label, category = 'labels') {
            return this.translate(label, category, 'AdvancedCrosstab');
        }

        select(stage) {
            this.selected = this.selected === stage ? null : stage;
            this.renderCanvas();
            this.options.onSelect(this.selected);
        }

        /**
         * Called by the designer after each change: redraws the steps, then reloads the record counts (debounced).
         */
        refresh() {
            if (!this.isRendered()) {
                return;
            }

            this.renderCanvas();

            clearTimeout(this.timeout);
            this.timeout = setTimeout(() => this.loadStats(), 400);
        }

        async loadStats() {
            const requestId = ++this.requestId;
            const definition = this.options.getRunDefinition();
            const fetch = stage => Espo.Ajax
                .postRequest('AdvancedCrosstab/action/preview', {definition, stage, limit: PREVIEW_LIMIT})
                .catch(e => {
                    if (e) {
                        e.errorIsHandled = true;
                    }

                    return {error: (e && e.getResponseHeader && e.getResponseHeader('X-Status-Reason')) || this.t('Error')};
                });

            this.loading = true;
            this.renderPreview();

            const [source, filtered] = await Promise.all([fetch('source'), fetch('filtered')]);

            if (requestId !== this.requestId || !this.isRendered()) {
                return;
            }

            this.loading = false;
            this.previews = {source, filtered};
            this.stats = {source: source.count, filtered: filtered.count};

            this.renderCanvas();
            this.renderPreview();
        }

        // --- Steps ------------------------------------------------------------------------------------------------

        /**
         * @return {Object.<string, {title: string, subtitle: string, items: string[], status: string}>}
         */
        describe() {
            const d = this.options.getDefinition();
            const entityType = d.entityType;
            const result = this.options.getResult();
            const error = this.options.getError();
            const customNames = (d.joins || []).map(j => j.name);

            // Many-to-one links travelled by fields (account, account.parent…).
            const linkPaths = new Set();
            const addPath = path => {
                if (!path || !/^[a-zA-Z0-9.]+$/.test(path)) {
                    return;
                }

                const parts = path.split('.');

                for (let i = 1; i < parts.length; i++) {
                    if (i === 1 && customNames.includes(parts[0])) {
                        continue;
                    }

                    linkPaths.add(parts.slice(0, i).join('.'));
                }
            };

            d.rows.concat(d.columns).forEach(dim => addPath(dim.path));
            d.measures.forEach(m => m.kind === 'native' && addPath(m.expression));

            const conditions = [];
            const walk = node => {
                if (!node) {
                    return;
                }

                (node.items || []).forEach(walk);

                if (node.type === 'condition' && node.path) {
                    addPath(node.path);
                    conditions.push(this.schema.getPathLabel(entityType, node.path) + ' ' + node.operator);
                }

                if (node.type === 'formula' && node.formula) {
                    conditions.push(node.formula);
                }
            };

            // Incomplete conditions are not applied: the cleaned filter is described.
            walk(this.options.getRunDefinition().filter);

            const related = d.measures.filter(m => m.kind === 'related');
            const lookups = [...linkPaths].sort().map(path => '⟶ ' + this.schema.getPathLabel(entityType, path))
                .concat((d.joins || []).map(j => '«join» ' + this.schema.getCustomJoinLabel(j)))
                .concat(related.map(m => 'Σ ' + m.label));

            if (d.primaryFilter) {
                conditions.unshift(this.translate(d.primaryFilter, 'presetFilters', entityType));
            }

            if ((d.listWhere || []).length) {
                conditions.unshift(this.t('List filters') + ' (' + d.listWhere.length + ')');
            }

            const calculated = d.measures
                .filter(m => m.kind === 'aggregate' || m.kind === 'display' ||
                    (m.kind === 'native' && (m.condition || (m.expression && !/^[a-zA-Z0-9.]+$/.test(m.expression)))))
                .map(m => (m.kind === 'display' ? '= ' : 'ƒ ') + m.label)
                .concat(d.rows.concat(d.columns).filter(dim => dim.type === 'formula').map(dim => 'ƒ ' + (dim.label || this.t('Formula'))));

            const dimLabel = dim => dim.label || (dim.type === 'formula' ? this.t('Formula') :
                this.schema.getPathLabel(entityType, dim.path)) + (dim.granularity ? ' (' + this.t(dim.granularity, 'granularities') + ')' : '');

            const aggregate = d.rows.map(dim => '≡ ' + dimLabel(dim))
                .concat(d.columns.map(dim => '⫴ ' + dimLabel(dim)))
                .concat(d.measures.filter(m => m.kind === 'native' || m.kind === 'related')
                    .map(m => m.aggregation + ' · ' + m.label));

            const view = d.options.view || {};
            const output = [
                this.t(view.mode || 'table', 'modes') + (view.mode === 'chart' ? ' · ' + this.t(view.chartType || 'column', 'chartTypes') :
                    view.mode === 'kpi' ? '' : ' · ' + this.t(view.layout || 'compact', 'layouts')),
            ];

            const totals = ['rowTotals', 'columnTotals', 'subtotals'].filter(name => d.options[name] !== false);

            if (totals.length) {
                output.push(totals.map(name => this.t({rowTotals: 'Row totals', columnTotals: 'Column totals', subtotals: 'Subtotals'}[name])).join(', '));
            }

            if (result) {
                output.push(result.durationMs + ' ms · ' + result.queryCount + ' ' + this.t('queries'));
            }

            const sourceError = this.previews.source && this.previews.source.error;
            const filteredError = this.previews.filtered && this.previews.filtered.error;

            return {
                source: {
                    title: this.schema.translateEntity(entityType),
                    items: [],
                    status: sourceError ? 'error' : (this.stats.source === 0 ? 'warn' : 'ok'),
                    message: sourceError,
                },
                lookups: {
                    items: lookups,
                    status: lookups.length ? 'ok' : 'idle',
                },
                filter: {
                    items: conditions,
                    status: filteredError ? 'error' : (!conditions.length ? 'idle' : (this.stats.filtered === 0 ? 'warn' : 'ok')),
                    message: filteredError,
                },
                calculate: {
                    items: calculated,
                    status: calculated.length ? 'ok' : 'idle',
                },
                aggregate: {
                    items: aggregate,
                    status: error ? 'error' : 'ok',
                    message: error,
                },
                output: {
                    items: output,
                    status: error ? 'error' : (result ? 'ok' : 'idle'),
                },
            };
        }

        countGroups(result) {
            if (!result || !result.rows) {
                return null;
            }

            const count = nodes => (nodes || []).reduce((sum, node) => sum + (node.c && node.c.length ? count(node.c) : 1), 0);

            // Cells of the grid: row groups × column groups.
            return Math.max(1, count(result.rows)) * Math.max(1, count(result.columns));
        }

        renderCanvas() {
            if (!this.canvas) {
                return;
            }

            const info = this.describe();
            const result = this.options.getResult();
            const groups = this.countGroups(result);
            const number = value => value === undefined || value === null ? '…' : Number(value).toLocaleString();

            // Records flowing out of each step.
            const flows = {
                source: number(this.stats.source) + ' ' + this.t('records'),
                lookups: number(this.stats.source) + ' ' + this.t('records'),
                filter: number(this.stats.filtered) + ' ' + this.t('records'),
                calculate: number(this.stats.filtered) + ' ' + this.t('records'),
                aggregate: (groups === null ? '…' : number(groups)) + ' ' + this.t('groups'),
            };

            const selectivity = this.stats.source ? Math.round(100 * (this.stats.filtered || 0) / this.stats.source) : null;

            const html = STAGES.map((stage, index) => {
                const item = info[stage];
                const shown = item.items.slice(0, 6);
                const more = item.items.length - shown.length;
                const metric = stage === 'source' ? number(this.stats.source) :
                    stage === 'filter' && selectivity !== null && item.items.length ? selectivity + ' %' :
                    stage === 'aggregate' && groups !== null ? number(groups) : '';

                const node = `
                    <div class="acx-etl-node acx-etl-${stage} acx-status-${item.status}${this.selected === stage ? ' active' : ''}"
                        data-stage="${stage}" data-action="selectStage" tabindex="0">
                        <div class="acx-etl-node-head">
                            <span class="acx-etl-node-icon"><span class="${STAGE_ICONS[stage]}"></span></span>
                            <span class="acx-etl-node-title">
                                <span class="acx-etl-step">${index + 1}. ${this.escapeString(this.t('stage.' + stage, 'messages'))}</span>
                                <strong title="${this.escapeString(item.title || this.t('stageHint.' + stage, 'messages'))}">${this.escapeString(item.title || this.t('stageHint.' + stage, 'messages'))}</strong>
                            </span>
                            <span class="acx-etl-status" title="${this.escapeString(this.t('status.' + item.status, 'messages'))}"></span>
                        </div>
                        ${metric ? `<div class="acx-etl-metric">${this.escapeString(metric)}
                            <span class="small text-muted">${this.escapeString(this.t('metric.' + stage, 'messages'))}</span></div>` : ''}
                        ${item.message ? `<div class="acx-etl-error small text-danger">${this.escapeString(item.message)}</div>` : ''}
                        <ul class="acx-etl-items">
                            ${shown.map(text => `<li title="${this.escapeString(text)}">${this.escapeString(text)}</li>`).join('')}
                            ${more > 0 ? `<li class="text-muted">+ ${more}</li>` : ''}
                            ${!item.items.length && stage !== 'source' ?
                                `<li class="text-muted acx-etl-passthrough">${this.escapeString(this.t('passthrough.' + stage, 'messages'))}</li>` : ''}
                        </ul>
                    </div>`;

                const arrow = index < STAGES.length - 1 ? `
                    <div class="acx-etl-flow"><span class="acx-etl-flow-label">${this.escapeString(flows[stage])}</span></div>` : '';

                return node + arrow;
            }).join('');

            this.canvas.innerHTML = `<div class="acx-etl-track">${html}</div>
                <div class="acx-etl-drop-hint">${this.escapeString(this.t('dropHint', 'messages'))}</div>`;
        }

        // --- Data preview -------------------------------------------------------------------------------------------

        renderPreview() {
            const body = this.element.querySelector('[data-role="preview"]');
            const infoElement = this.element.querySelector('[data-role="preview-info"]');

            if (!body) {
                return;
            }

            this.element.querySelectorAll('[data-role="preview-tabs"] li').forEach(li =>
                li.classList.toggle('active', li.dataset.stage === this.previewStage));

            const preview = this.previews[this.previewStage];

            if (!preview) {
                body.innerHTML = '<div class="acx-etl-loading"><span class="fas fa-spinner fa-spin"></span></div>';
                infoElement.textContent = '';

                return;
            }

            if (preview.error) {
                body.innerHTML = `<div class="alert alert-danger">${this.escapeString(preview.error)}</div>`;
                infoElement.textContent = '';

                return;
            }

            infoElement.textContent = (this.loading ? '⟳ ' : '') + this.t('previewInfo', 'messages')
                .replace('{shown}', preview.rows.length.toLocaleString())
                .replace('{count}', Number(preview.count).toLocaleString())
                .replace('{ms}', preview.durationMs);

            if (!preview.rows.length) {
                body.innerHTML = `<div class="acx-empty-hint">${this.escapeString(this.t('No records'))}</div>`;

                return;
            }

            const columns = preview.columns;
            const cell = value => value === null || value === undefined || value === '' ? '<span class="text-muted">∅</span>' :
                this.escapeString(typeof value === 'object' ? JSON.stringify(value) : String(value));

            body.innerHTML = `
                <table class="table table-condensed acx-etl-table">
                    <thead><tr>${columns.map(column => `<th title="${this.escapeString(column.path)}">
                        ${this.escapeString(column.label)}<div class="acx-etl-col-type">${this.escapeString(column.type || '')}</div></th>`).join('')}</tr></thead>
                    <tbody>${preview.rows.map(row => `<tr>${columns.map(column => `<td>${cell(row[column.key])}</td>`).join('')}</tr>`).join('')}</tbody>
                </table>`;
        }

        onRemove() {
            clearTimeout(this.timeout);
        }
    };
});
