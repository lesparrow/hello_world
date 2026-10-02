/**
 * Editor for repeatable pass fields stored as jsonArray:
 * [{key, label, value, section, textAlignment}, …]
 * Field param "sectionList" restricts the selectable sections (front: header/primary/secondary/auxiliary).
 */
define('wallet-passes:views/fields/wallet-field-list', ['views/fields/base'], (BaseFieldView) => {

    const alignmentList = ['natural', 'left', 'center', 'right'];

    const sectionLabels = {
        header: 'Header',
        primary: 'Primary',
        secondary: 'Secondary',
        auxiliary: 'Auxiliary',
        back: 'Back',
    };

    return class extends BaseFieldView {

        type = 'jsonArray'

        detailTemplate = 'wallet-passes:fields/wallet-field-list/detail'
        editTemplate = 'wallet-passes:fields/wallet-field-list/edit'
        listTemplate = 'wallet-passes:fields/wallet-field-list/list'

        setup() {
            super.setup();

            this.sectionList = this.params.sectionList ||
                this.getMetadata().get(['entityDefs', this.entityType, 'fields', this.name, 'sectionList']) ||
                ['secondary'];

            this.addActionHandler('walletAddField', () => {
                const list = this.fetchList();

                list.push({key: '', label: '', value: '', section: this.sectionList[0], textAlignment: 'natural'});
                this.renderEditRows(list);
                this.trigger('change');
            });

            this.addActionHandler('walletRemoveField', (e, target) => {
                const list = this.fetchList();

                list.splice(parseInt(target.dataset.index), 1);
                this.renderEditRows(list);
                this.trigger('change');
            });
        }

        getList() {
            const value = this.model.get(this.name);

            return Array.isArray(value) ? Espo.Utils.cloneDeep(value) : [];
        }

        afterRender() {
            super.afterRender();

            if (this.isEditMode()) {
                this.renderEditRows(this.getList());

                return;
            }

            this.renderDetail(this.getList());
        }

        renderDetail(list) {
            const $container = this.$el.find('.wallet-field-list-container');

            if (!list.length) {
                $container.html(`<span class="none-value">${this.translate('None')}</span>`);

                return;
            }

            const rows = list.map(item => `
                <tr>
                    <td class="text-muted small">${this.escapeString(sectionLabels[item.section] || item.section || '')}</td>
                    <td><code>${this.escapeString(item.key || '')}</code></td>
                    <td>${this.escapeString(item.label || '')}</td>
                    <td>${this.escapeString(item.value || '')}</td>
                </tr>`).join('');

            $container.html(`<table class="table table-condensed table-bordered-inside no-margin">${rows}</table>`);
        }

        renderEditRows(list) {
            const sectionOptions = selected => this.sectionList
                .map(s => `<option value="${s}"${s === selected ? ' selected' : ''}>${sectionLabels[s] || s}</option>`)
                .join('');

            const alignOptions = selected => alignmentList
                .map(a => `<option value="${a}"${a === selected ? ' selected' : ''}>${a}</option>`)
                .join('');

            const rows = list.map((item, index) => `
                <div class="wallet-field-row" data-index="${index}">
                    ${this.sectionList.length > 1 ?
                        `<select class="form-control input-sm" data-name="section">${sectionOptions(item.section)}</select>` :
                        `<input type="hidden" data-name="section" value="${this.sectionList[0]}">`}
                    <input class="form-control input-sm" data-name="key" placeholder="key"
                        value="${this.escapeString(item.key || '')}" maxlength="64">
                    <input class="form-control input-sm" data-name="label" placeholder="${this.translate('Label', 'labels', 'Admin')}"
                        value="${this.escapeString(item.label || '')}" maxlength="100">
                    <input class="form-control input-sm wallet-field-value" data-name="value" placeholder="{contact.firstName}"
                        value="${this.escapeString(item.value || '')}" maxlength="500">
                    <select class="form-control input-sm" data-name="textAlignment">${alignOptions(item.textAlignment)}</select>
                    <button type="button" class="btn btn-link btn-sm" data-action="walletRemoveField" data-index="${index}"
                        title="${this.translate('Remove')}"><span class="fas fa-times"></span></button>
                </div>`).join('');

            const html = rows +
                `<button type="button" class="btn btn-default btn-sm" data-action="walletAddField">
                    <span class="fas fa-plus"></span> ${this.translate('Add')}
                </button>`;

            const $container = this.$el.find('.wallet-field-list-container');

            $container.html(html);
            $container.find('input, select').on('change', () => this.trigger('change'));
        }

        fetchList() {
            const list = [];

            this.$el.find('.wallet-field-row').each((i, row) => {
                const item = {};

                row.querySelectorAll('[data-name]').forEach(input => {
                    item[input.dataset.name] = input.value.trim();
                });

                if (!item.key) {
                    item.key = (item.label || 'field' + (i + 1))
                        .toLowerCase()
                        .normalize('NFD').replace(/[̀-ͯ]/g, '')
                        .replace(/[^a-z0-9_]+/g, '_')
                        .replace(/^_|_$/g, '') || 'field' + (i + 1);
                }

                list.push(item);
            });

            return list;
        }

        fetch() {
            return {[this.name]: this.fetchList()};
        }

        validateRequired() {
            if (this.isRequired() && !this.fetchList().length) {
                const msg = this.translate('fieldIsRequired', 'messages')
                    .replace('{field}', this.getLabelText());

                this.showValidationMessage(msg);

                return true;
            }

            return false;
        }
    };
});
