define('advanced-crosstab:views/advanced-crosstab/field-tree', ['view', 'advanced-crosstab:lib/schema'], function (View, Schema) {

    const TYPE_ICONS = {
        enum: 'fas fa-list-ul',
        varchar: 'fas fa-font',
        text: 'fas fa-align-left',
        bool: 'far fa-check-square',
        int: 'fas fa-hashtag',
        float: 'fas fa-hashtag',
        currency: 'fas fa-coins',
        date: 'far fa-calendar',
        datetime: 'far fa-clock',
        datetimeOptional: 'far fa-calendar-alt',
        link: 'fas fa-link',
        personName: 'fas fa-user',
        duration: 'fas fa-hourglass-half',
        id: 'fas fa-key',
    };

    /**
     * Searchable tree of the fields of an entity and of its related entities (many-to-one links),
     * expanded lazily, up to Schema.MAX_DEPTH levels.
     *
     * Options: entityType, purpose ('dimension' | 'numeric' | 'any'), onSelect(path, info).
     */
    return class extends View {

        templateContent = `
            <div class="acx-tree">
                <div class="acx-tree-search">
                    <input type="search" class="form-control input-sm" data-name="search"
                        placeholder="{{translate 'Search fields' scope='AdvancedCrosstab'}}" autocomplete="off">
                </div>
                <ul class="acx-tree-list" data-role="root"></ul>
            </div>
        `

        setup() {
            this.schema = new Schema(this);
            this.entityType = this.options.entityType;
            this.purpose = this.options.purpose || 'any';

            this.addActionHandler('toggleLink', (e, target) => this.toggleLink(target.closest('li')));
            this.addActionHandler('pickField', (e, target) => this.pick(target.dataset.path));
        }

        afterRender() {
            this.rootList = this.element.querySelector('[data-role="root"]');
            this.searchInput = this.element.querySelector('[data-name="search"]');

            this.rootList.innerHTML = this.buildLevel(this.entityType, '', 0);

            let timeout;

            this.searchInput.addEventListener('input', () => {
                clearTimeout(timeout);
                timeout = setTimeout(() => this.search(this.searchInput.value.trim()), 150);
            });

            setTimeout(() => this.searchInput.focus(), 50);
        }

        buildLevel(entityType, prefix, depth) {
            const html = [];

            const fields = this.schema.getFieldList(entityType, this.purpose);

            if (this.purpose === 'any' && depth === 0) {
                html.push(this.fieldItem('id', 'ID', 'id'));
            }

            for (const field of fields) {
                html.push(this.fieldItem(prefix + field.name, field.label, field.type));
            }

            const customJoins = depth === 0 && !this.options.noCustomJoins ? Schema.getCustomJoins(this.entityType) : [];
            const selectors = depth === 0 && !this.options.noCustomJoins ? Schema.getSelectors(this.entityType) : [];

            for (const selector of selectors) {
                const target = this.schema.getSelectorTarget(this.entityType, selector);

                if (!target) {
                    continue;
                }

                html.push(`
                    <li class="acx-tree-link acx-tree-selector" data-path="${this.escapeString(selector.name)}"
                        data-entity-type="${this.escapeString(target)}" data-depth="1">
                        <a role="button" data-action="toggleLink" title="${this.escapeString(this.schema.describeSelectorRule(this.entityType, selector))}">
                            <span class="fas fa-caret-right acx-caret"></span>
                            <span class="acx-selector-badge">1</span>
                            ${this.escapeString(this.schema.getSelectorLabel(this.entityType, selector))}
                            <span class="text-muted small">${this.escapeString(this.translate('selected record', 'labels', 'AdvancedCrosstab'))}</span>
                        </a>
                        <ul class="acx-tree-list hidden"></ul>
                    </li>
                `);
            }

            for (const join of customJoins) {
                html.push(`
                    <li class="acx-tree-link acx-tree-custom" data-path="${this.escapeString(join.name)}"
                        data-entity-type="${this.escapeString(join.entityType)}" data-depth="1">
                        <a role="button" data-action="toggleLink">
                            <span class="fas fa-caret-right acx-caret"></span>
                            <span class="fas fa-link acx-custom-link-icon"></span>
                            ${this.escapeString(this.schema.getCustomJoinLabel(join))}
                            <span class="text-muted small">${this.escapeString(this.translate('custom link', 'labels', 'AdvancedCrosstab'))}</span>
                        </a>
                        <ul class="acx-tree-list hidden"></ul>
                    </li>
                `);
            }

            if (depth < Schema.MAX_DEPTH) {
                for (const link of this.schema.getLinkList(entityType)) {
                    html.push(`
                        <li class="acx-tree-link" data-path="${this.escapeString(prefix + link.name)}"
                            data-entity-type="${this.escapeString(link.entityType)}" data-depth="${depth + 1}">
                            <a role="button" data-action="toggleLink">
                                <span class="fas fa-caret-right acx-caret"></span>
                                <span class="fas fa-sitemap text-muted"></span>
                                ${this.escapeString(link.label)}
                                <span class="text-muted small">${this.escapeString(this.schema.translateEntity(link.entityType, false))}</span>
                            </a>
                            <ul class="acx-tree-list hidden"></ul>
                        </li>
                    `);
                }
            }

            if (!html.length) {
                html.push(`<li class="text-muted small acx-tree-empty">${this.translate('No fields', 'labels', 'AdvancedCrosstab')}</li>`);
            }

            return html.join('');
        }

        fieldItem(path, label, type, hint) {
            const icon = TYPE_ICONS[type] || 'fas fa-circle';

            return `
                <li class="acx-tree-field">
                    <a role="button" data-action="pickField" data-path="${this.escapeString(path)}" title="${this.escapeString(path)}">
                        <span class="${icon} text-muted acx-type-icon"></span>
                        ${this.escapeString(label)}
                        ${hint ? `<span class="text-muted small">${this.escapeString(hint)}</span>` : ''}
                    </a>
                </li>
            `;
        }

        toggleLink(li) {
            const list = li.querySelector(':scope > ul');
            const caret = li.querySelector(':scope > a .acx-caret');

            if (!list.dataset.loaded) {
                list.innerHTML = this.buildLevel(li.dataset.entityType, li.dataset.path + '.', parseInt(li.dataset.depth));
                list.dataset.loaded = '1';
            }

            const isHidden = list.classList.toggle('hidden');

            caret.classList.toggle('fa-caret-right', isHidden);
            caret.classList.toggle('fa-caret-down', !isHidden);
        }

        /**
         * Flat search through the current entity and its relations (two levels deep).
         */
        search(text) {
            if (!text) {
                this.rootList.innerHTML = this.buildLevel(this.entityType, '', 0);

                return;
            }

            const needle = text.toLowerCase();
            const results = [];

            const walk = (entityType, prefix, labelPrefix, depth) => {
                for (const field of this.schema.getFieldList(entityType, this.purpose)) {
                    const label = labelPrefix + field.label;

                    if (label.toLowerCase().includes(needle) || (prefix + field.name).toLowerCase().includes(needle)) {
                        results.push({path: prefix + field.name, label: label, type: field.type});
                    }
                }

                if (depth < 2) {
                    for (const link of this.schema.getLinkList(entityType)) {
                        walk(link.entityType, prefix + link.name + '.', labelPrefix + link.label + ' › ', depth + 1);
                    }
                }
            };

            walk(this.entityType, '', '', 0);

            for (const join of this.options.noCustomJoins ? [] : Schema.getCustomJoins(this.entityType)) {
                walk(join.entityType, join.name + '.', this.schema.getCustomJoinLabel(join) + ' › ', 1);
            }

            for (const selector of this.options.noCustomJoins ? [] : Schema.getSelectors(this.entityType)) {
                const target = this.schema.getSelectorTarget(this.entityType, selector);

                if (target) {
                    walk(target, selector.name + '.', this.schema.getSelectorLabel(this.entityType, selector) + ' › ', 1);
                }
            }

            this.rootList.innerHTML = results.length ?
                results.slice(0, 200).map(item => this.fieldItem(item.path, item.label, item.type)).join('') :
                `<li class="text-muted small acx-tree-empty">${this.translate('No fields', 'labels', 'AdvancedCrosstab')}</li>`;
        }

        pick(path) {
            const resolved = this.schema.resolvePath(this.entityType, path);

            if (this.options.onSelect) {
                this.options.onSelect(path, {
                    ...resolved,
                    label: this.schema.getPathLabel(this.entityType, path),
                });
            }
        }
    };
});
