define('advanced-crosstab:views/advanced-crosstab/filter-builder', ['view', 'advanced-crosstab:lib/schema', 'advanced-crosstab:lib/operators'], function (View, Schema, Operators) {

    /**
     * Nested filter editor: AND / OR / NOT groups, field conditions (including related entity fields at any depth)
     * and record formula conditions. Produces the definition `filter` tree; the server compiles it with ACL.
     *
     * Options: entityType, filter, onChange(filter).
     */
    return class extends View {

        templateContent = `<div class="acx-filter-builder" data-role="root"></div>`

        setup() {
            this.schema = new Schema(this);
            this.filter = Espo.Utils.cloneDeep(this.options.filter) || {type: 'and', items: []};

            if (!['and', 'or', 'not'].includes(this.filter.type)) {
                this.filter = {type: 'and', items: [this.filter]};
            }

            this.addActionHandler('addCondition', (e, target) => this.addCondition(target.dataset.node));
            this.addActionHandler('addGroup', (e, target) => this.addItem(target.dataset.node, {type: 'or', items: []}));
            this.addActionHandler('addFormula', (e, target) => this.addItem(target.dataset.node, {type: 'formula', formula: ''}));
            this.addActionHandler('removeNode', (e, target) => this.removeNode(target.dataset.node));
            this.addActionHandler('changeField', (e, target) => this.changeField(target.dataset.node));
            this.addActionHandler('selectRecords', (e, target) => this.selectRecords(target.dataset.node));
            this.addActionHandler('removeRecord', (e, target) => this.removeRecord(target.dataset.node, target.dataset.id));
        }

        afterRender() {
            this.root = this.element.querySelector('[data-role="root"]');
            this.root.addEventListener('change', e => this.onInputChange(e));
            this.refresh();
        }

        getFilter() {
            return this.filter.items.length ? this.filter : null;
        }

        refresh() {
            this.root.innerHTML = this.renderGroup(this.filter, '', true);
        }

        notify() {
            if (this.options.onChange) {
                this.options.onChange(this.getFilter());
            }
        }

        /** Node by dotted index path ('' = root, '0.1' = second item of first item). */
        getNode(id) {
            let node = this.filter;

            for (const index of id === '' ? [] : id.split('.')) {
                node = node.items[parseInt(index)];
            }

            return node;
        }

        getParent(id) {
            const parts = id.split('.');
            const index = parseInt(parts.pop());

            return {parent: this.getNode(parts.join('.')), index};
        }

        t(label, category = 'labels') {
            return this.translate(label, category, 'AdvancedCrosstab');
        }

        renderGroup(group, id, isRoot) {
            const options = ['and', 'or', 'not'].map(type =>
                `<option value="${type}"${group.type === type ? ' selected' : ''}>${this.escapeString(this.t(type, 'filterGroups'))}</option>`).join('');

            const items = group.items.map((item, i) => {
                const childId = id === '' ? String(i) : id + '.' + i;

                if (item.type === 'and' || item.type === 'or' || item.type === 'not') {
                    return `<li>${this.renderGroup(item, childId, false)}</li>`;
                }

                return `<li>${item.type === 'formula' ? this.renderFormula(item, childId) : this.renderCondition(item, childId)}</li>`;
            }).join('');

            return `
                <div class="acx-filter-group${isRoot ? ' acx-filter-root' : ''}">
                    <div class="acx-filter-group-header">
                        <select class="form-control input-sm acx-inline-select" data-node="${id}" data-input="groupType">${options}</select>
                        <div class="btn-group btn-group-xs pull-right">
                            <button type="button" class="btn btn-default" data-action="addCondition" data-node="${id}"
                                title="${this.escapeString(this.t('Add condition'))}"><span class="fas fa-plus"></span></button>
                            <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown"><span class="caret"></span></button>
                            <ul class="dropdown-menu pull-right">
                                <li><a role="button" data-action="addCondition" data-node="${id}">${this.escapeString(this.t('Add condition'))}</a></li>
                                <li><a role="button" data-action="addGroup" data-node="${id}">${this.escapeString(this.t('Add group'))}</a></li>
                                <li><a role="button" data-action="addFormula" data-node="${id}">${this.escapeString(this.t('Add formula condition'))}</a></li>
                                ${isRoot ? '' : `<li class="divider"></li><li><a role="button" data-action="removeNode" data-node="${id}">${this.escapeString(this.translate('Remove'))}</a></li>`}
                            </ul>
                        </div>
                    </div>
                    <ul class="acx-filter-items">${items || `<li class="text-muted small acx-filter-empty">${this.escapeString(this.t('No filters'))}</li>`}</ul>
                </div>
            `;
        }

        renderFormula(item, id) {
            return `
                <div class="acx-filter-item">
                    <div class="acx-filter-item-header">
                        <span class="fas fa-square-root-alt text-muted"></span>
                        <span class="small">${this.escapeString(this.t('Formula'))}</span>
                        <a role="button" class="pull-right text-muted" data-action="removeNode" data-node="${id}"><span class="fas fa-times"></span></a>
                    </div>
                    <textarea class="form-control input-sm acx-filter-formula" rows="2" spellcheck="false"
                        data-node="${id}" data-input="formula" placeholder="amount > 10000 AND account.industry == 'Retail'">${this.escapeString(item.formula || '')}</textarea>
                    <div class="small" data-role="formula-status" data-node="${id}"></div>
                </div>
            `;
        }

        renderCondition(item, id) {
            const resolved = this.schema.resolvePath(this.options.entityType, item.path);
            const type = resolved.type;
            const operators = Operators.forType(type);

            const operatorOptions = operators.map(op =>
                `<option value="${op}"${op === item.operator ? ' selected' : ''}>${this.escapeString(this.t(op, 'operators'))}</option>`).join('');

            return `
                <div class="acx-filter-item${resolved.valid ? '' : ' has-error'}">
                    <div class="acx-filter-item-header">
                        <a role="button" data-action="changeField" data-node="${id}" class="acx-filter-field" title="${this.escapeString(item.path)}">
                            ${this.escapeString(this.schema.getPathLabel(this.options.entityType, item.path))}</a>
                        <a role="button" class="pull-right text-muted" data-action="removeNode" data-node="${id}"><span class="fas fa-times"></span></a>
                    </div>
                    <select class="form-control input-sm" data-node="${id}" data-input="operator">${operatorOptions}</select>
                    <div class="acx-filter-value">${this.renderValue(item, id, type)}</div>
                </div>
            `;
        }

        renderValue(item, id, type) {
            const op = item.operator;
            const value = item.value;
            const attr = `data-node="${id}" data-input="value"`;

            if (Operators.hasNoValue(op)) {
                return '';
            }

            if (Operators.isDays(op)) {
                return `<input type="number" min="0" class="form-control input-sm" ${attr} value="${this.escapeString(value ?? 7)}">`;
            }

            if (Schema.DATE_TYPES.includes(type)) {
                if (Operators.isRange(op)) {
                    const list = Array.isArray(value) ? value : [];

                    return `<input type="date" class="form-control input-sm" ${attr} data-index="0" value="${this.escapeString(list[0] || '')}">
                        <input type="date" class="form-control input-sm" ${attr} data-index="1" value="${this.escapeString(list[1] || '')}">`;
                }

                return `<input type="date" class="form-control input-sm" ${attr} value="${this.escapeString(value || '')}">`;
            }

            if (type === 'enum') {
                const options = this.schema.getEnumOptions(this.options.entityType, item.path);
                const selected = Array.isArray(value) ? value : [value];
                const multiple = Operators.isList(op);

                return `<select class="form-control input-sm" ${attr} ${multiple ? `multiple size="${Math.min(6, options.length)}"` : ''}>
                    ${options.map(o => `<option value="${this.escapeString(o.value)}"${selected.includes(o.value) ? ' selected' : ''}>${this.escapeString(o.label)}</option>`).join('')}
                </select>`;
            }

            if (type === 'link' || type === 'id') {
                const ids = Array.isArray(value) ? value : [];
                const names = item.valueNames || {};

                return `<div class="acx-filter-records">
                    ${ids.map(recordId => `<span class="label label-default">${this.escapeString(names[recordId] || recordId)}
                        <a role="button" data-action="removeRecord" data-node="${id}" data-id="${this.escapeString(recordId)}">&times;</a></span>`).join(' ')}
                    <button type="button" class="btn btn-default btn-xs" data-action="selectRecords" data-node="${id}">
                        <span class="fas fa-search"></span> ${this.escapeString(this.t('Select records'))}</button>
                </div>`;
            }

            const inputType = Schema.NUMERIC_TYPES.includes(type) ? 'number' : 'text';

            if (Operators.isRange(op)) {
                const list = Array.isArray(value) ? value : [];

                return `<input type="${inputType}" step="any" class="form-control input-sm" ${attr} data-index="0" value="${this.escapeString(list[0] ?? '')}">
                    <input type="${inputType}" step="any" class="form-control input-sm" ${attr} data-index="1" value="${this.escapeString(list[1] ?? '')}">`;
            }

            if (Operators.isList(op)) {
                return `<input type="text" class="form-control input-sm" ${attr} data-list="1"
                    placeholder="${this.escapeString(this.t('Comma-separated values'))}" value="${this.escapeString((Array.isArray(value) ? value : []).join(', '))}">`;
            }

            return `<input type="${inputType}" step="any" class="form-control input-sm" ${attr} value="${this.escapeString(value ?? '')}">`;
        }

        onInputChange(e) {
            const input = e.target;
            const id = input.dataset.node;

            if (id === undefined || !input.dataset.input) {
                return;
            }

            const node = this.getNode(id);

            switch (input.dataset.input) {
                case 'groupType':
                    node.type = input.value;
                    break;

                case 'operator': {
                    const wasList = Operators.isList(node.operator) || Operators.isRange(node.operator);

                    node.operator = input.value;

                    if (wasList !== (Operators.isList(node.operator) || Operators.isRange(node.operator))) {
                        node.value = null;
                    }

                    if (Operators.isDays(node.operator)) {
                        node.value = 7;
                    }

                    this.refresh();
                    break;
                }

                case 'formula':
                    node.formula = input.value;
                    this.validateFormula(id, input.value);

                    return;

                case 'value':
                    node.value = this.readValue(node, input);
                    break;
            }

            this.notify();
        }

        readValue(node, input) {
            const type = this.schema.resolvePath(this.options.entityType, node.path).type;
            const numeric = Schema.NUMERIC_TYPES.includes(type);
            const cast = v => numeric && v !== '' ? Number(v) : v;

            if (input.multiple) {
                return Array.from(input.selectedOptions).map(o => o.value);
            }

            if (input.dataset.list) {
                return input.value.split(',').map(v => v.trim()).filter(v => v !== '').map(cast);
            }

            if (input.dataset.index !== undefined) {
                const list = Array.isArray(node.value) ? node.value.slice() : [null, null];

                list[parseInt(input.dataset.index)] = cast(input.value);

                return list;
            }

            if (Operators.isDays(node.operator)) {
                return Math.max(0, parseInt(input.value) || 0);
            }

            if (Operators.isList(node.operator)) {
                return [input.value];
            }

            return cast(input.value);
        }

        async validateFormula(id, formula) {
            const status = this.root.querySelector(`[data-role="formula-status"][data-node="${id}"]`);

            if (!formula.trim()) {
                status.innerHTML = '';

                return;
            }

            const result = await Espo.Ajax.postRequest('AdvancedCrosstab/action/validateFormula', {
                entityType: this.options.entityType,
                formula: formula,
                kind: 'condition',
                joins: Schema.getCustomJoins(this.options.entityType),
            });

            status.className = 'small ' + (result.valid ? 'text-success' : 'text-danger');
            status.textContent = result.valid ?
                '✓ ' + this.t('Matching records') + ': ' + result.preview.count :
                result.error;

            if (result.valid) {
                this.notify();
            }
        }

        addItem(groupId, item) {
            this.getNode(groupId).items.push(item);
            this.refresh();

            if (item.type !== 'formula' && item.type !== 'or' && item.type !== 'and') {
                this.notify();
            }
        }

        addCondition(groupId) {
            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/field-picker', {
                entityType: this.options.entityType,
                purpose: 'any',
                onSelect: (path, info) => {
                    const operator = Operators.forType(info.type)[0];

                    this.addItem(groupId, {
                        type: 'condition',
                        path: path,
                        operator: operator,
                        value: Operators.isDays(operator) ? 7 : null,
                    });
                },
            }).then(view => view.render());
        }

        changeField(id) {
            this.createView('dialog', 'advanced-crosstab:views/advanced-crosstab/modals/field-picker', {
                entityType: this.options.entityType,
                purpose: 'any',
                onSelect: (path, info) => {
                    const node = this.getNode(id);

                    node.path = path;
                    node.operator = Operators.forType(info.type)[0];
                    node.value = null;
                    delete node.valueNames;

                    this.refresh();
                    this.notify();
                },
            }).then(view => view.render());
        }

        removeNode(id) {
            const {parent, index} = this.getParent(id);

            parent.items.splice(index, 1);
            this.refresh();
            this.notify();
        }

        selectRecords(id) {
            const node = this.getNode(id);
            const resolved = this.schema.resolvePath(this.options.entityType, node.path);
            const entityType = resolved.type === 'id' ? resolved.entityType :
                this.schema.getLinkTarget(resolved.entityType, resolved.field);

            if (!entityType) {
                return;
            }

            this.createView('dialog', 'views/modals/select-records', {
                entityType: entityType,
                multiple: true,
                createButton: false,
                onSelect: models => {
                    const ids = Array.isArray(node.value) ? node.value.slice() : [];

                    node.valueNames = node.valueNames || {};

                    for (const model of models) {
                        if (!ids.includes(model.id)) {
                            ids.push(model.id);
                        }

                        node.valueNames[model.id] = model.get('name') || model.id;
                    }

                    node.value = ids;
                    this.refresh();
                    this.notify();
                },
            }).then(view => view.render());
        }

        removeRecord(id, recordId) {
            const node = this.getNode(id);

            node.value = (node.value || []).filter(v => v !== recordId);
            this.refresh();
            this.notify();
        }
    };
});
