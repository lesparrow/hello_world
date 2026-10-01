define('advanced-crosstab:views/advanced-crosstab/formula-builder', ['view'], function (View) {

    const OPERATORS = ['+', '-', '*', '/', '(', ')', '>', '<', '>=', '<=', '==', '!=', 'AND', 'OR', '!', '??'];

    const FUNCTIONS = {
        aggregate: [
            ['SUM(|)', 'SUM'], ['AVG(|)', 'AVG'], ['MIN(|)', 'MIN'], ['MAX(|)', 'MAX'],
            ['COUNT(id)|', 'COUNT'], ['COUNT_DISTINCT(|)', 'COUNT DISTINCT'],
            ['SUM(|, condition)', 'SUM with condition'],
        ],
        conditional: [
            ['ifThenElse(|condition, valueIfTrue, valueIfFalse)', 'ifThenElse'],
            ['ifThen(|condition, value)', 'ifThen'],
        ],
        string: [
            ['string\\concat(|, \' \')', 'string\\concat'], ['string\\lowerCase(|)', 'string\\lowerCase'],
            ['string\\upperCase(|)', 'string\\upperCase'], ['string\\trim(|)', 'string\\trim'],
            ['string\\length(|)', 'string\\length'], ['string\\contains(|, \'text\')', 'string\\contains'],
            ['string\\replace(|, \'a\', \'b\')', 'string\\replace'],
        ],
        number: [
            ['number\\round(|, 2)', 'number\\round'], ['number\\abs(|)', 'number\\abs'],
            ['number\\floor(|)', 'number\\floor'], ['number\\ceil(|)', 'number\\ceil'],
        ],
        date: [
            ['datetime\\year(|)', 'datetime\\year'], ['datetime\\month(|)', 'datetime\\month'],
            ['datetime\\date(|)', 'datetime\\date'], ['datetime\\dayOfWeek(|)', 'datetime\\dayOfWeek'],
            ['datetime\\diff(|, datetime\\today(), \'days\')', 'datetime\\diff'],
            ['datetime\\today()|', 'datetime\\today'], ['datetime\\now()|', 'datetime\\now'],
        ],
        array: [
            ['array\\includes(list(\'a\', \'b\'), |)', 'array\\includes'],
        ],
    };

    const DISPLAY_FUNCTIONS = {
        conditional: FUNCTIONS.conditional,
        number: FUNCTIONS.number,
    };

    /**
     * Formula editor: field tree (current and related entities), operators, function catalog,
     * server-side validation with a preview computed under the user's ACL.
     *
     * Options:
     * - entityType
     * - kind: 'record' | 'condition' | 'aggregate' | 'display'
     * - value
     * - measures: [{key, label}] (display formulas)
     * - formatter, format (preview formatting)
     */
    return class extends View {

        templateContent = `
            <div class="acx-formula-builder row">
                <div class="col-sm-8">
                    <textarea class="form-control acx-formula-input" data-name="formula" rows="4"
                        spellcheck="false" autocomplete="off"></textarea>
                    <div class="acx-formula-toolbar">
                        <div class="btn-group btn-group-sm acx-operators"></div>
                        <div class="btn-group btn-group-sm acx-functions"></div>
                        <button type="button" class="btn btn-default btn-sm" data-action="validateFormula">
                            <span class="fas fa-check"></span> {{translate 'Validate' scope='AdvancedCrosstab'}}
                        </button>
                    </div>
                    <div class="acx-formula-status small" data-role="status"></div>
                    <div class="acx-formula-help small text-muted" data-role="help"></div>
                </div>
                <div class="col-sm-4 acx-formula-side">
                    <div class="acx-side-title small text-muted" data-role="side-title"></div>
                    <div data-role="side" class="acx-tree-box">{{{tree}}}</div>
                </div>
            </div>
        `

        setup() {
            this.kind = this.options.kind || 'record';
            this.lastValidation = null;

            this.addActionHandler('insertText', (e, target) => this.insert(target.dataset.text));
            this.addActionHandler('validateFormula', () => this.validate());

            if (this.kind !== 'display') {
                this.createView('tree', 'advanced-crosstab:views/advanced-crosstab/field-tree', {
                    selector: '[data-role="side"]',
                    entityType: this.options.entityType,
                    purpose: 'any',
                    onSelect: path => this.insert(path),
                });
            }
        }

        afterRender() {
            this.textarea = this.element.querySelector('[data-name="formula"]');
            this.statusElement = this.element.querySelector('[data-role="status"]');

            this.textarea.value = this.options.value || '';

            this.element.querySelector('.acx-operators').innerHTML = OPERATORS
                .map(op => `<button type="button" class="btn btn-default" data-action="insertText"
                    data-text="${this.escapeString(op.length > 1 && /[A-Z]/.test(op) ? ` ${op} ` : op)}">${this.escapeString(op)}</button>`)
                .join('');

            this.element.querySelector('.acx-functions').innerHTML = this.buildFunctionMenu();

            this.element.querySelector('[data-role="side-title"]').textContent = this.kind === 'display' ?
                this.translate('Measures', 'labels', 'AdvancedCrosstab') :
                this.translate('Available fields', 'labels', 'AdvancedCrosstab');

            if (this.kind === 'display') {
                this.element.querySelector('[data-role="side"]').innerHTML =
                    '<ul class="acx-tree-list">' +
                    (this.options.measures || []).map(m => `
                        <li class="acx-tree-field"><a role="button" data-action="insertText" data-text="${this.escapeString(m.key)}">
                            <span class="fas fa-calculator text-muted acx-type-icon"></span>
                            ${this.escapeString(m.label)} <span class="text-muted small">${this.escapeString(m.key)}</span>
                        </a></li>`).join('') +
                    '</ul>';
            }

            this.element.querySelector('[data-role="help"]').textContent =
                this.translate('formulaHelp.' + this.kind, 'messages', 'AdvancedCrosstab');

            let timeout;

            this.textarea.addEventListener('input', () => {
                this.lastValidation = null;
                clearTimeout(timeout);
                timeout = setTimeout(() => this.validate(), 700);
            });

            if (this.textarea.value) {
                this.validate();
            }
        }

        buildFunctionMenu() {
            const groups = this.kind === 'display' ? DISPLAY_FUNCTIONS :
                Object.fromEntries(Object.entries(FUNCTIONS).filter(([group]) => group !== 'aggregate' || this.kind === 'aggregate'));

            return Object.entries(groups).map(([group, items]) => `
                <div class="btn-group btn-group-sm">
                    <button type="button" class="btn btn-default dropdown-toggle" data-toggle="dropdown">
                        ${this.escapeString(this.translate(group, 'functionGroups', 'AdvancedCrosstab'))} <span class="caret"></span>
                    </button>
                    <ul class="dropdown-menu">
                        ${items.map(([snippet, label]) => `
                            <li><a role="button" data-action="insertText" data-text="${this.escapeString(snippet)}">
                                <code>${this.escapeString(label)}</code></a></li>`).join('')}
                    </ul>
                </div>
            `).join('');
        }

        /**
         * Insert at the cursor. A `|` in the snippet marks where the cursor goes (replacing the selection).
         */
        insert(text) {
            const textarea = this.textarea;
            const start = textarea.selectionStart ?? textarea.value.length;
            const end = textarea.selectionEnd ?? start;
            const selected = textarea.value.substring(start, end);

            let snippet = text;
            let cursor = snippet.indexOf('|');

            if (cursor !== -1) {
                snippet = snippet.replace('|', selected);
                cursor += selected.length;
            } else {
                cursor = snippet.length;
            }

            textarea.value = textarea.value.substring(0, start) + snippet + textarea.value.substring(end);
            textarea.focus();
            textarea.setSelectionRange(start + cursor, start + cursor);
            textarea.dispatchEvent(new Event('input'));
        }

        getValue() {
            return this.textarea ? this.textarea.value.trim() : (this.options.value || '');
        }

        /**
         * @return {Promise<boolean>}
         */
        async validate() {
            const formula = this.getValue();

            if (!formula) {
                this.setStatus(null, '');

                return false;
            }

            if (this.lastValidation && this.lastValidation.formula === formula) {
                return this.lastValidation.valid;
            }

            this.setStatus(null, this.translate('Validating…', 'labels', 'AdvancedCrosstab'));

            const result = await Espo.Ajax.postRequest('AdvancedCrosstab/action/validateFormula', {
                entityType: this.options.entityType,
                formula: formula,
                kind: this.kind,
                measureKeys: (this.options.measures || []).map(m => m.key),
            });

            if (formula !== this.getValue()) {
                return this.validate();
            }

            this.lastValidation = {formula, valid: result.valid};

            if (!result.valid) {
                this.setStatus(false, result.error);

                return false;
            }

            this.setStatus(true, this.translate('Formula valid', 'labels', 'AdvancedCrosstab') + this.previewText(result.preview));

            return true;
        }

        previewText(preview) {
            if (!preview) {
                return '';
            }

            if ('value' in preview) {
                const formatter = this.options.formatter;
                const value = formatter ? formatter.format(preview.value, this.options.format) : preview.value;

                return ' — ' + this.translate('Example result', 'labels', 'AdvancedCrosstab') + ': ' + (value === '' ? '∅' : value);
            }

            if ('count' in preview) {
                return ' — ' + this.translate('Matching records', 'labels', 'AdvancedCrosstab') + ': ' + preview.count;
            }

            if ('values' in preview) {
                return ' — ' + this.translate('Examples', 'labels', 'AdvancedCrosstab') + ': ' +
                    preview.values.map(v => v === null ? '∅' : String(v)).join(', ');
            }

            return '';
        }

        setStatus(valid, text) {
            if (!this.statusElement) {
                return;
            }

            this.statusElement.className = 'acx-formula-status small ' +
                (valid === true ? 'text-success' : valid === false ? 'text-danger' : 'text-muted');

            this.statusElement.innerHTML = (valid === true ? '<span class="fas fa-check-circle"></span> ' :
                valid === false ? '<span class="fas fa-exclamation-circle"></span> ' : '') + this.escapeString(text || '');
        }
    };
});
