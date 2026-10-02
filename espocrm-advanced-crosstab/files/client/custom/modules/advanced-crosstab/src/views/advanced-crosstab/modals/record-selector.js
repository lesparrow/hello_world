define('advanced-crosstab:views/advanced-crosstab/modals/record-selector', ['views/modal', 'advanced-crosstab:lib/schema'], function (ModalView, Schema) {

    const ORDER_EXCLUDED_TYPES = ['text', 'bool', 'personName'];
    const PREFERRED_ORDER_FIELDS = ['closeDate', 'dateStart', 'date', 'dateEnd', 'createdAt'];

    /**
     * Record selector: for each record of the owner, ONE record of a to-many relation is picked by a rule
     * (FIRST / LAST / MIN / MAX by a field, EARLIEST / LATEST by creation date), optionally among the records
     * matching a condition. All the fields read through the selector come from that same record.
     *
     * Options: rootEntityType, from (owner path, '' = data source), link (preselected relation), selector (edited),
     * usedNames (names taken by other selectors and custom links), onApply(selector).
     */
    return class extends ModalView {

        templateContent = `
            <div class="acx-modal-form acx-selector-form">
                <p class="text-muted small">{{translate 'selectorHelp' category='messages' scope='AdvancedCrosstab'}}</p>
                <div class="row">
                    <div class="col-sm-6 form-group">
                        <label class="control-label" data-role="owner-label"></label>
                        <select class="form-control" data-name="link"></select>
                    </div>
                    <div class="col-sm-6 form-group">
                        <label class="control-label">{{translate 'Selection rule' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="rule"></select>
                    </div>
                </div>
                <div class="row">
                    <div class="col-sm-6 form-group">
                        <label class="control-label">{{translate 'Order by' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="orderBy"></select>
                    </div>
                    <div class="col-sm-6 form-group">
                        <label class="control-label">{{translate 'Direction' scope='AdvancedCrosstab'}}</label>
                        <div class="form-control-static" data-role="direction"></div>
                    </div>
                </div>
                <div class="form-group">
                    <label class="control-label">{{translate 'Only among records where' scope='AdvancedCrosstab'}}
                        <span class="text-muted small">({{translate 'optional' scope='AdvancedCrosstab'}})</span></label>
                    <div data-role="condition">{{{condition}}}</div>
                </div>
                <div class="row">
                    <div class="col-sm-6 form-group">
                        <label class="control-label">{{translate 'Label' scope='AdvancedCrosstab'}}</label>
                        <input type="text" class="form-control" data-name="label" maxlength="100">
                    </div>
                    <div class="col-sm-6 form-group">
                        <label class="control-label">{{translate 'Key' scope='AdvancedCrosstab'}}</label>
                        <input type="text" class="form-control" data-name="name" maxlength="40" spellcheck="false">
                    </div>
                </div>
                <div class="acx-selector-explain" data-role="explain"></div>
            </div>
        `

        setup() {
            this.schema = new Schema(this);
            this.root = this.options.rootEntityType;
            this.existing = this.options.selector || null;
            this.from = this.existing ? (this.existing.from || '') : (this.options.from || '');
            this.ownerType = this.from ? this.schema.resolvePath(this.root, this.from + '.id').entityType : this.root;

            this.headerText = this.translate(this.existing ? 'Edit record selector' : 'Record selector', 'labels', 'AdvancedCrosstab');

            this.buttonList = [
                {name: 'apply', label: 'Apply', style: 'primary', onClick: () => this.apply()},
                {name: 'cancel', label: 'Cancel', onClick: () => this.close()},
            ];

            this.relations = this.schema.getToManyLinkList(this.ownerType)
                .map(link => ({name: link.name, entityType: link.entityType, label: link.label}))
                .concat(this.from ? [] : Schema.getCustomJoins(this.root)
                    .filter(join => join.foreignField !== 'id' && !join.from)
                    .map(join => ({name: join.name, entityType: join.entityType, label: this.schema.getCustomJoinLabel(join) + ' (' +
                        this.translate('custom link', 'labels', 'AdvancedCrosstab') + ')'})));

            this.link = this.existing ? this.existing.link : (this.options.link || (this.relations[0] || {}).name);
        }

        t(label, category = 'labels') {
            return this.translate(label, category, 'AdvancedCrosstab');
        }

        afterRender() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const options = (list, selected) => list.map(([value, label]) =>
                `<option value="${this.escapeString(value)}"${value === selected ? ' selected' : ''}>${this.escapeString(label)}</option>`).join('');

            this.element.querySelector('[data-role="owner-label"]').textContent =
                this.t('Relation of') + ' ' + (this.from ? this.schema.getPathLabel(this.root, this.from) :
                    this.schema.translateEntity(this.ownerType, false));

            if (!this.relations.length) {
                this.element.querySelector('.acx-selector-form').innerHTML =
                    `<div class="alert alert-info">${this.escapeString(this.t('noToManyRelation', 'messages'))}</div>`;

                return;
            }

            $('link').innerHTML = options(this.relations.map(r => {
                const entity = this.schema.translateEntity(r.entityType);

                return [r.name, r.label === entity ? r.label : r.label + ' → ' + entity];
            }), this.link);
            $('rule').innerHTML = options(Schema.SELECTOR_RULES.map(rule =>
                [rule, this.t(rule, 'selectorRules') + ' — ' + this.t('selectorRuleHint.' + rule, 'messages')]), this.existing ? this.existing.rule : 'LAST');

            if (this.existing) {
                $('label').value = this.existing.label || '';
                $('name').value = this.existing.name;
            }

            $('link').addEventListener('change', () => this.onRelationChange(true));
            $('rule').addEventListener('change', () => {
                this.syncOrderBy(true);
                this.explain();
            });
            $('orderBy').addEventListener('change', () => this.explain());
            $('label').addEventListener('input', () => this.explain());

            this.onRelationChange(false);
        }

        getTarget() {
            const relation = this.relations.find(r => r.name === this.element.querySelector('[data-name="link"]').value);

            return relation ? relation.entityType : null;
        }

        onRelationChange(reset) {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);

            this.link = $('link').value;

            if (reset || !this.existing) {
                $('name').value = this.uniqueName();
            }

            this.syncOrderBy(reset);
            this.createConditionView(reset ? '' : (this.existing && this.existing.condition) || '');
            this.explain();
        }

        /**
         * Fields the related records can be ordered by; a date field is proposed for FIRST / LAST, a number for MIN / MAX.
         */
        syncOrderBy(reset) {
            const select = this.element.querySelector('[data-name="orderBy"]');
            const rule = this.element.querySelector('[data-name="rule"]').value;
            const target = this.getTarget();
            const fields = this.schema.getFieldList(target, 'dimension').filter(f => !ORDER_EXCLUDED_TYPES.includes(f.type));
            const current = !reset && this.existing ? (this.existing.orderBy || 'createdAt') : select.value;

            let selected = fields.some(f => f.name === current) ? current : null;

            if (!selected || reset) {
                const byType = types => fields.find(f => types.includes(f.type));

                if (rule === 'LATEST' || rule === 'EARLIEST') {
                    selected = 'createdAt';
                } else if (rule === 'MIN' || rule === 'MAX') {
                    selected = (fields.find(f => f.name === 'amount') || byType(Schema.NUMERIC_TYPES) || fields[0] || {}).name;
                } else {
                    selected = (PREFERRED_ORDER_FIELDS.map(name => fields.find(f => f.name === name)).find(Boolean) ||
                        byType(Schema.DATE_TYPES) || fields[0] || {}).name;
                }
            }

            select.innerHTML = fields.map(f => `<option value="${this.escapeString(f.name)}"${f.name === selected ? ' selected' : ''}>` +
                `${this.escapeString(f.label)} (${this.escapeString(f.type)})</option>`).join('');
        }

        createConditionView(value) {
            this.clearView('condition');

            this.createView('condition', 'advanced-crosstab:views/advanced-crosstab/formula-builder', {
                selector: '[data-role="condition"]',
                entityType: this.getTarget(),
                kind: 'condition',
                value: value,
                noCustomJoins: true,
            }).then(view => view.render());
        }

        explain() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const target = this.getTarget();
            const rule = $('rule').value;
            const orderBy = $('orderBy').value || 'createdAt';
            const descending = Schema.isDescendingRule(rule);
            const relation = this.relations.find(r => r.name === $('link').value);

            this.element.querySelector('[data-role="direction"]').innerHTML = descending ?
                `<span class="fas fa-sort-amount-down"></span> DESC — ${this.escapeString(this.t('highest value first'))}` :
                `<span class="fas fa-sort-amount-up"></span> ASC — ${this.escapeString(this.t('lowest value first'))}`;

            const owner = this.from ? this.schema.getPathLabel(this.root, this.from) : this.schema.translateEntity(this.ownerType, false);
            const orderLabel = this.schema.getPathLabel(target, orderBy);
            const name = $('name').value || 'selector';

            this.element.querySelector('[data-role="explain"]').innerHTML = `
                <div class="acx-selector-flow">
                    <span class="acx-sel-step"><span class="fas fa-cube"></span> ${this.escapeString(owner)}</span>
                    <span class="acx-sel-arrow">→</span>
                    <span class="acx-sel-step"><span class="fas fa-layer-group"></span> ${this.escapeString(relation ? relation.label : '')} [*]</span>
                    <span class="acx-sel-arrow">→</span>
                    <span class="acx-sel-step acx-sel-pick"><span class="fas fa-filter"></span>
                        ${this.escapeString(this.t(rule, 'selectorRules'))} · ${this.escapeString(orderLabel)} ${descending ? '↓' : '↑'} [1]</span>
                    <span class="acx-sel-arrow">→</span>
                    <span class="acx-sel-step"><span class="fas fa-list"></span> ${this.escapeString(name)}.<em>${this.escapeString(this.t('field'))}</em></span>
                </div>
                <div class="small text-muted acx-mt">${this.escapeString(this.t('selectorExplain', 'messages')
                    .replace('{owner}', owner)
                    .replace('{relation}', relation ? relation.label : '')
                    .replace('{order}', orderLabel)
                    .replace('{direction}', descending ? 'DESC' : 'ASC'))}</div>
                <code class="small acx-selector-sql">ORDER BY ${this.escapeString(orderBy)} ${descending ? 'DESC' : 'ASC'}, id ${descending ? 'DESC' : 'ASC'} LIMIT 1</code>
            `;
        }

        uniqueName() {
            const link = this.element.querySelector('[data-name="link"]').value || 'record';
            const rule = this.element.querySelector('[data-name="rule"]').value || 'LAST';
            const used = this.options.usedNames || [];
            const fields = this.getMetadata().get(['entityDefs', this.root, 'fields']) || {};
            const links = this.getMetadata().get(['entityDefs', this.root, 'links']) || {};
            const base = rule.toLowerCase() + link.charAt(0).toUpperCase() + link.slice(1).replace(/[^a-zA-Z0-9]/g, '');
            let name = base.slice(0, 36);
            let i = 2;

            while (used.includes(name) || name in fields || name in links) {
                name = base.slice(0, 36) + i++;
            }

            return name;
        }

        async apply() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);

            if (!$('link')) {
                this.close();

                return;
            }

            const name = $('name').value.trim();

            if (!/^[a-zA-Z][a-zA-Z0-9]{0,39}$/.test(name)) {
                Espo.Ui.warning(this.t('Invalid key'));

                return;
            }

            const fields = this.getMetadata().get(['entityDefs', this.root, 'fields']) || {};
            const links = this.getMetadata().get(['entityDefs', this.root, 'links']) || {};

            if ((this.options.usedNames || []).includes(name) || name in fields || name in links) {
                Espo.Ui.warning(this.t('Key already used'));

                return;
            }

            const conditionView = this.getView('condition');
            const condition = conditionView ? conditionView.getValue() : '';

            if (condition && !(await conditionView.validate())) {
                Espo.Ui.warning(this.t('Invalid formula'));

                return;
            }

            const selector = {
                name: name,
                link: $('link').value,
                rule: $('rule').value,
                orderBy: $('orderBy').value || 'createdAt',
            };

            if (this.from) {
                selector.from = this.from;
            }

            if (condition) {
                selector.condition = condition;
            }

            if ($('label').value.trim()) {
                selector.label = $('label').value.trim();
            }

            this.options.onApply(selector);
            this.close();
        }
    };
});
