define('advanced-crosstab:views/advanced-crosstab/modals/data-model', ['views/modal', 'advanced-crosstab:lib/schema'], function (ModalView, Schema) {

    const BOX_WIDTH = 250;
    const COLUMN_GAP = 110;
    const TYPE_ICONS = {
        enum: 'fas fa-list-ul', varchar: 'fas fa-font', text: 'fas fa-align-left', bool: 'far fa-check-square',
        int: 'fas fa-hashtag', float: 'fas fa-hashtag', currency: 'fas fa-coins', date: 'far fa-calendar',
        datetime: 'far fa-clock', datetimeOptional: 'far fa-calendar-alt', link: 'fas fa-link',
        personName: 'fas fa-user', duration: 'fas fa-hourglass-half', id: 'fas fa-key',
    };

    /**
     * Visual data model, Merise MCD style: the data source entity, its many-to-one associations (opened on demand,
     * up to Schema.MAX_DEPTH levels) and its one-to-many associations. Any field of any opened entity can be sent to
     * the crosstab's rows, columns, measures or filters; the relation path (e.g. account.parent.industry) is built
     * from the boxes' positions in the model.
     *
     * One-to-many / many-to-many associations of the data source are listed (dashed) in its box: using them as
     * dimensions would duplicate rows, so the model offers to switch the data source to that entity instead.
     *
     * Options: entityType, getUsage(), onUse(target, path, info), onChangeSource(entityType).
     */
    return class extends ModalView {

        backdrop = true

        templateContent = `
            <div class="acx-model-toolbar">
                <span class="acx-model-legend"><span class="acx-legend-line"></span>
                    {{translate 'modelLegendManyToOne' category='messages' scope='AdvancedCrosstab'}}</span>
                <span class="acx-model-legend"><span class="acx-legend-line acx-dashed"></span>
                    {{translate 'modelLegendToMany' category='messages' scope='AdvancedCrosstab'}}</span>
                <span class="acx-model-legend"><span class="badge acx-use-badge">R</span><span class="badge acx-use-badge">C</span><span
                    class="badge acx-use-badge">M</span><span class="badge acx-use-badge">F</span>
                    {{translate 'modelLegendUsage' category='messages' scope='AdvancedCrosstab'}}</span>
                <button type="button" class="btn btn-default btn-sm" data-action="resetLayout">
                    <span class="fas fa-sitemap"></span> {{translate 'Reset layout' scope='AdvancedCrosstab'}}</button>
            </div>
            <div class="acx-model-viewport">
                <div class="acx-model-canvas" data-role="canvas">
                    <svg class="acx-model-links" data-role="links"></svg>
                </div>
            </div>
        `

        setup() {
            this.schema = new Schema(this);
            this.rootEntityType = this.options.entityType;
            this.headerText = this.translate('Data model', 'labels', 'AdvancedCrosstab') + ' · ' +
                this.schema.translateEntity(this.rootEntityType);

            this.buttonList = [{name: 'close', label: 'Close', onClick: () => this.close()}];

            /** @type {Object.<string, {path: string, entityType: string, depth: number, parent: ?string, link: ?string, x: number, y: number}>} */
            this.boxes = {};
            this.toManyLinks = this.schema.getToManyLinkList(this.rootEntityType);

            this.addActionHandler('toggleLink', (e, target) =>
                this.toggleLink(target.closest('[data-box]').dataset.box, target.dataset.link));
            this.addActionHandler('useField', (e, target) =>
                this.useField(target.dataset.use, target.closest('[data-box]').dataset.box, target.dataset.field));
            this.addActionHandler('closeBox', (e, target) => this.closeBox(target.closest('[data-box]').dataset.box));
            this.addActionHandler('changeSource', (e, target) => this.changeSource(target.dataset.entityType));
            this.addActionHandler('resetLayout', () => this.resetLayout());
        }

        afterRender() {
            const dialog = this.element.closest('.modal-dialog') || document.querySelector('.modal-dialog:last-of-type');

            if (dialog) {
                dialog.style.width = 'calc(100vw - 40px)';
                dialog.style.maxWidth = '1800px';
            }

            this.canvas = this.element.querySelector('[data-role="canvas"]');
            this.svg = this.element.querySelector('[data-role="links"]');

            this.canvas.addEventListener('input', e => {
                if (e.target.matches('[data-role="field-search"]')) {
                    this.filterFields(e.target);
                }
            });

            this.canvas.addEventListener('pointerdown', e => this.startDrag(e));

            this.resetLayout();
        }

        t(label, category = 'labels') {
            return this.translate(label, category, 'AdvancedCrosstab');
        }

        resetLayout() {
            const opened = Object.values(this.boxes).filter(box => box.path !== '').map(box => box.path);

            this.boxes = {};
            this.canvas.querySelectorAll('.acx-mbox').forEach(el => el.remove());

            this.addBox({path: '', entityType: this.rootEntityType, depth: 0, parent: null, link: null, x: 20, y: 20});

            // Re-open previously opened relations, parents first.
            opened.sort((a, b) => a.split('.').length - b.split('.').length).forEach(path => {
                const parts = path.split('.');
                const parentPath = parts.slice(0, -1).join('.');

                if (this.boxes[parentPath] && !this.boxes[path]) {
                    this.openLink(parentPath, parts[parts.length - 1]);
                }
            });

            this.drawLinks();
        }

        // --- Boxes ------------------------------------------------------------------------------------------------

        addBox(box) {
            this.boxes[box.path] = box;

            const element = document.createElement('div');

            element.className = 'acx-mbox' + (box.path === '' ? ' acx-mbox-root' : '');
            element.dataset.box = box.path;
            element.style.left = box.x + 'px';
            element.style.top = box.y + 'px';
            element.style.width = BOX_WIDTH + 'px';
            element.innerHTML = this.renderBox(box);

            this.canvas.appendChild(element);
            this.updateCanvasSize();

            return element;
        }

        renderBox(box) {
            const pathLabel = box.path ? this.schema.getPathLabel(this.rootEntityType, box.path) : this.t('Data source');
            const usage = this.options.getUsage();
            const prefix = box.path ? box.path + '.' : '';

            const fields = (box.path === '' ? [{name: 'id', type: 'id', label: 'ID'}] : [])
                .concat(this.schema.getFieldList(box.entityType, 'any'));

            const fieldItems = fields.map(field => {
                const path = prefix + field.name;
                const dimensionAllowed = field.type !== 'text';

                return `
                    <li data-field-label="${this.escapeString(field.label.toLowerCase() + ' ' + field.name.toLowerCase())}">
                        <span class="acx-mfield-name" title="${this.escapeString(path)}">
                            <span class="${TYPE_ICONS[field.type] || 'fas fa-circle'} text-muted acx-type-icon"></span>
                            ${this.escapeString(field.label)}
                            <span class="acx-use-badges" data-path="${this.escapeString(path)}">${this.badges(usage[path])}</span>
                        </span>
                        <span class="acx-mfield-actions">
                            ${dimensionAllowed ? this.useButton('rows', 'R', field.name) + this.useButton('columns', 'C', field.name) : ''}
                            ${this.useButton('measures', 'M', field.name)}
                            ${this.useButton('filters', 'F', field.name)}
                        </span>
                    </li>`;
            }).join('');

            const canDescend = box.depth < Schema.MAX_DEPTH;

            const linkItems = canDescend ? this.schema.getLinkList(box.entityType).map(link => {
                const required = !!this.getMetadata().get(['entityDefs', box.entityType, 'fields', link.name, 'required']);
                const open = !!this.boxes[prefix + link.name];

                return `
                    <li class="acx-mlink${open ? ' active' : ''}" data-link-row="${this.escapeString(link.name)}">
                        <a role="button" data-action="toggleLink" data-link="${this.escapeString(link.name)}">
                            <span class="fas fa-${open ? 'minus' : 'plus'}-circle"></span>
                            ${this.escapeString(link.label)}
                            <span class="text-muted small">→ ${this.escapeString(this.schema.translateEntity(link.entityType, false))}
                                (${required ? '1,1' : '0,1'})</span>
                        </a>
                    </li>`;
            }).join('') : '';

            return `
                <div class="acx-mbox-head" data-drag="1">
                    <span class="fas fa-${box.path === '' ? 'database' : 'cube'}"></span>
                    <strong>${this.escapeString(this.schema.translateEntity(box.entityType, false))}</strong>
                    ${box.path === '' ? '' : `<a role="button" class="acx-mbox-close" data-action="closeBox" title="${this.escapeString(this.translate('Close'))}">&times;</a>`}
                    <div class="acx-mbox-path small">${this.escapeString(pathLabel)}</div>
                </div>
                <div class="acx-mbox-search">
                    <input type="search" class="form-control input-sm" data-role="field-search"
                        placeholder="${this.escapeString(this.t('Search fields'))}">
                </div>
                <ul class="acx-mbox-fields">${fieldItems}</ul>
                ${linkItems ? `<div class="acx-mbox-section">${this.escapeString(this.t('Associations'))}</div>
                    <ul class="acx-mbox-links">${linkItems}</ul>` : ''}
                ${box.path === '' && this.toManyLinks.length ? this.renderToMany() : ''}
            `;
        }

        /**
         * One-to-many / many-to-many associations of the data source (dashed): not usable as dimensions from here;
         * the analysis can start from the entity on the "many" side instead.
         */
        renderToMany() {
            return `
                <div class="acx-mbox-section">${this.escapeString(this.t('One-to-many associations'))}</div>
                <ul class="acx-mbox-links acx-mbox-tomany">
                    ${this.toManyLinks.map(link => `
                        <li class="acx-mlink" title="${this.escapeString(this.t(link.manyToMany ? 'modelManyToMany' : 'modelOneToMany', 'messages'))}">
                            <span class="acx-mlink-tomany">
                                <span class="fas fa-ellipsis-h text-muted"></span>
                                ${this.escapeString(link.label)}
                                <span class="text-muted small">→ ${this.escapeString(this.schema.translateEntity(link.entityType, false))}
                                    (${link.manyToMany ? '0,N / 0,N' : '0,N / 0,1'})</span>
                            </span>
                            <a role="button" class="acx-mlink-switch" data-action="changeSource"
                                data-entity-type="${this.escapeString(link.entityType)}"
                                title="${this.escapeString(this.t('Analyse from this entity'))}"><span class="fas fa-random"></span></a>
                        </li>`).join('')}
                </ul>
            `;
        }

        useButton(target, letter, field) {
            return `<button type="button" class="btn btn-default btn-xs" data-action="useField" data-use="${target}"
                data-field="${this.escapeString(field)}" title="${this.escapeString(this.t('modelUse.' + target, 'messages'))}">${letter}</button>`;
        }

        badges(list) {
            return (list || []).map(mark => `<span class="badge acx-use-badge">${mark}</span>`).join('');
        }

        refreshBadges() {
            const usage = this.options.getUsage();

            this.canvas.querySelectorAll('.acx-use-badges').forEach(element => {
                element.innerHTML = this.badges(usage[element.dataset.path]);
            });
        }

        filterFields(input) {
            const text = input.value.trim().toLowerCase();

            input.closest('.acx-mbox').querySelectorAll('.acx-mbox-fields > li').forEach(li => {
                li.classList.toggle('hidden', !!text && !li.dataset.fieldLabel.includes(text));
            });
        }

        rerenderBox(path) {
            const element = this.canvas.querySelector(`.acx-mbox[data-box="${CSS.escape(path)}"]`);
            const search = element.querySelector('[data-role="field-search"]');
            const text = search ? search.value : '';

            element.innerHTML = this.renderBox(this.boxes[path]);

            if (text) {
                const input = element.querySelector('[data-role="field-search"]');

                input.value = text;
                this.filterFields(input);
            }
        }

        // --- Associations -----------------------------------------------------------------------------------------

        toggleLink(parentPath, link) {
            const path = (parentPath ? parentPath + '.' : '') + link;

            if (this.boxes[path]) {
                this.closeBox(path);

                return;
            }

            this.openLink(parentPath, link);
            this.drawLinks();
        }

        openLink(parentPath, link) {
            const parent = this.boxes[parentPath];
            const path = (parentPath ? parentPath + '.' : '') + link;
            const entityType = this.schema.getLinkTarget(parent.entityType, link);

            if (!entityType) {
                return;
            }

            const parentElement = this.canvas.querySelector(`.acx-mbox[data-box="${CSS.escape(parentPath)}"]`);
            const row = parentElement.querySelector(`[data-link-row="${CSS.escape(link)}"]`);
            const x = parent.x + BOX_WIDTH + COLUMN_GAP;
            let y = Math.max(10, parent.y + (row ? row.offsetTop - 20 : 0));

            // Find a free vertical slot in the column.
            const column = Object.values(this.boxes).filter(box => Math.abs(box.x - x) < BOX_WIDTH);
            let moved = true;

            while (moved) {
                moved = false;

                for (const box of column) {
                    const element = this.canvas.querySelector(`.acx-mbox[data-box="${CSS.escape(box.path)}"]`);
                    const height = element ? element.offsetHeight : 200;

                    if (y < box.y + height + 16 && y + 120 > box.y) {
                        y = box.y + height + 16;
                        moved = true;
                    }
                }
            }

            this.addBox({path, entityType, depth: parent.depth + 1, parent: parentPath, link, x, y});
            this.rerenderBox(parentPath);
        }

        closeBox(path) {
            for (const childPath of Object.keys(this.boxes)) {
                if (childPath === path || childPath.startsWith(path + '.')) {
                    delete this.boxes[childPath];
                    this.canvas.querySelector(`.acx-mbox[data-box="${CSS.escape(childPath)}"]`)?.remove();
                }
            }

            const parentPath = path.split('.').slice(0, -1).join('.');

            if (this.boxes[parentPath]) {
                this.rerenderBox(parentPath);
            }

            this.updateCanvasSize();
            this.drawLinks();
        }

        useField(target, boxPath, field) {
            const box = this.boxes[boxPath];
            const path = (boxPath ? boxPath + '.' : '') + field;
            const type = field === 'id' ? 'id' : this.schema.getFieldType(box.entityType, field);

            this.options.onUse(target, path, {
                type: type,
                entityType: box.entityType,
                field: field,
                label: this.schema.getPathLabel(this.rootEntityType, path),
            });

            this.refreshBadges();

            Espo.Ui.success(this.t('modelUse.' + target, 'messages') + ': ' + this.schema.getPathLabel(this.rootEntityType, path));
        }

        changeSource(entityType) {
            this.options.onChangeSource(entityType);
            this.close();
        }

        // --- Drawing ----------------------------------------------------------------------------------------------

        updateCanvasSize() {
            let width = 0;
            let height = 0;

            this.canvas.querySelectorAll('.acx-mbox').forEach(element => {
                width = Math.max(width, element.offsetLeft + element.offsetWidth);
                height = Math.max(height, element.offsetTop + element.offsetHeight);
            });

            this.canvas.style.width = (width + 40) + 'px';
            this.canvas.style.height = (height + 40) + 'px';
        }

        boxElement(path) {
            return this.canvas.querySelector(`.acx-mbox[data-box="${CSS.escape(path)}"]`);
        }

        /**
         * MCD notation: entity —(cardinality)— (association) —(cardinality)— entity.
         */
        drawLinks() {
            const parts = [];

            for (const box of Object.values(this.boxes)) {
                if (box.parent === null || box.parent === undefined) {
                    continue;
                }

                const parentElement = this.boxElement(box.parent);
                const childElement = this.boxElement(box.path);

                if (!parentElement || !childElement) {
                    continue;
                }

                const childHeadY = childElement.offsetTop + 22;
                const row = parentElement.querySelector(`[data-link-row="${CSS.escape(box.link)}"]`);
                const x1 = parentElement.offsetLeft + parentElement.offsetWidth;
                const y1 = row ? parentElement.offsetTop + row.offsetTop + row.offsetHeight / 2 : parentElement.offsetTop + 22;
                const x2 = childElement.offsetLeft;
                const parentBox = this.boxes[box.parent];
                const required = !!this.getMetadata().get(['entityDefs', parentBox.entityType, 'fields', box.link, 'required']);

                parts.push(this.connector(x1, y1, x2, childHeadY,
                    this.schema.translateField(parentBox.entityType, box.link), required ? '1,1' : '0,1', '0,N', false));
            }

            this.svg.innerHTML = parts.join('');
        }

        connector(x1, y1, x2, y2, label, cardinality1, cardinality2, dashed) {
            const mx = (x1 + x2) / 2;
            const my = (y1 + y2) / 2;
            const dx = Math.max(30, Math.abs(x2 - x1) / 2);
            const text = this.escapeString(label.length > 18 ? label.slice(0, 17) + '…' : label);
            const rx = Math.max(34, text.length * 3.6 + 12);

            return `
                <path d="M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}" class="acx-mline${dashed ? ' acx-dashed' : ''}"/>
                <ellipse cx="${mx}" cy="${my}" rx="${rx}" ry="13" class="acx-massoc${dashed ? ' acx-dashed' : ''}"/>
                <text x="${mx}" y="${my + 4}" text-anchor="middle" class="acx-massoc-text">${text}</text>
                <text x="${x1 + 6}" y="${y1 - 6}" class="acx-mcard">${cardinality1}</text>
                <text x="${x2 - 6}" y="${y2 - 6}" text-anchor="end" class="acx-mcard">${cardinality2}</text>
            `;
        }

        startDrag(e) {
            const head = e.target.closest('[data-drag]');

            if (!head || e.target.closest('a, button, input')) {
                return;
            }

            const element = head.closest('.acx-mbox');
            const box = this.boxes[element.dataset.box];
            const startX = e.clientX;
            const startY = e.clientY;
            const originX = box.x;
            const originY = box.y;

            element.classList.add('acx-dragging');
            head.setPointerCapture(e.pointerId);

            const move = event => {
                box.x = Math.max(0, originX + event.clientX - startX);
                box.y = Math.max(0, originY + event.clientY - startY);
                element.style.left = box.x + 'px';
                element.style.top = box.y + 'px';
                this.drawLinks();
            };

            const stop = () => {
                element.classList.remove('acx-dragging');
                head.removeEventListener('pointermove', move);
                head.removeEventListener('pointerup', stop);
                this.updateCanvasSize();
            };

            head.addEventListener('pointermove', move);
            head.addEventListener('pointerup', stop);
        }
    };
});
