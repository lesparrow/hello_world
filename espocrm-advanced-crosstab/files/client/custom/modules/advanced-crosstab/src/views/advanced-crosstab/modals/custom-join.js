define('advanced-crosstab:views/advanced-crosstab/modals/custom-join', ['views/modal', 'advanced-crosstab:lib/schema'], function (ModalView, Schema) {

    /**
     * Link the entity at `from` to any entity on any pair of key fields
     * (e.g. LigneBesoinPlants.codeFiche = FicheAction.code), even without an EspoCRM relationship.
     *
     * Options: rootEntityType, from (path, '' = data source), joins (existing), onApply(join).
     */
    return class extends ModalView {

        templateContent = `
            <div class="acx-modal-form">
                <p class="text-muted small">{{translate 'customJoinHelp' category='messages' scope='AdvancedCrosstab'}}</p>
                <div class="row">
                    <div class="col-sm-5 form-group">
                        <label class="control-label" data-role="from-label"></label>
                        <select class="form-control" data-name="localField"></select>
                    </div>
                    <div class="col-sm-2 text-center acx-join-equals"><span class="fas fa-equals"></span></div>
                    <div class="col-sm-5 form-group">
                        <label class="control-label">{{translate 'Entity to link' scope='AdvancedCrosstab'}}</label>
                        <select class="form-control" data-name="entityType"></select>
                        <select class="form-control acx-mt" data-name="foreignField"></select>
                    </div>
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
                <div class="small" data-role="hint"></div>
            </div>
        `

        setup() {
            this.schema = new Schema(this);
            this.from = this.options.from || '';
            this.fromEntityType = this.from ?
                this.schema.resolvePath(this.options.rootEntityType, this.from + '.id').entityType :
                this.options.rootEntityType;

            this.headerText = this.translate('Link another entity', 'labels', 'AdvancedCrosstab');

            this.buttonList = [
                {name: 'apply', label: 'Apply', style: 'primary', onClick: () => this.apply()},
                {name: 'cancel', label: 'Cancel', onClick: () => this.close()},
            ];
        }

        afterRender() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const options = (list, selected) => list.map(([value, label]) =>
                `<option value="${this.escapeString(value)}"${value === selected ? ' selected' : ''}>${this.escapeString(label)}</option>`).join('');

            this.element.querySelector('[data-role="from-label"]').textContent =
                (this.from ? this.schema.getPathLabel(this.options.rootEntityType, this.from) :
                    this.schema.translateEntity(this.fromEntityType, false)) + ' · ' +
                this.translate('Field', 'labels', 'AdvancedCrosstab');

            const localFields = this.schema.getKeyFieldList(this.fromEntityType);

            $('localField').innerHTML = options(localFields.map(f => [f.name, f.label + ' (' + f.type + ')']), localFields[1]?.name);

            const entities = this.schema.getEntityTypeList().map(scope => [scope, this.schema.translateEntity(scope, false)]);

            $('entityType').innerHTML = options(entities, null);

            const syncForeign = () => {
                const entityType = $('entityType').value;
                const local = $('localField').value;
                const localType = this.schema.getFieldType(this.fromEntityType, local);
                const fields = this.schema.getKeyFieldList(entityType);

                // A link pointing to the chosen entity joins on its ID; otherwise prefer a field with the same name.
                let preferred = 'id';

                if (localType !== 'link' || this.schema.getLinkTarget(this.fromEntityType, local) !== entityType) {
                    preferred = (fields.find(f => f.name === local) || fields.find(f => f.name === 'name') || fields[0]).name;
                }

                $('foreignField').innerHTML = options(fields.map(f => [f.name, f.label + ' (' + f.type + ')']), preferred);

                $('label').value = this.schema.translateEntity(entityType, false);
                $('name').value = this.uniqueName(entityType);
                syncHint();
            };

            const syncHint = () => {
                const hint = this.element.querySelector('[data-role="hint"]');

                hint.className = 'small text-muted';
                hint.textContent = $('foreignField').value === 'id' ?
                    this.translate('customJoinById', 'messages', 'AdvancedCrosstab') :
                    this.translate('customJoinByField', 'messages', 'AdvancedCrosstab');
            };

            $('entityType').addEventListener('change', syncForeign);
            $('localField').addEventListener('change', syncForeign);
            $('foreignField').addEventListener('change', syncHint);

            // Start with the target of the first link field, if any.
            const firstLink = localFields.find(f => f.type === 'link');
            const target = firstLink ? this.schema.getLinkTarget(this.fromEntityType, firstLink.name) : null;

            if (target && entities.some(([scope]) => scope === target)) {
                $('localField').value = firstLink.name;
                $('entityType').value = target;
            }

            syncForeign();
        }

        uniqueName(entityType) {
            const used = (this.options.joins || []).map(j => j.name);
            const fields = this.getMetadata().get(['entityDefs', this.options.rootEntityType, 'fields']) || {};
            const links = this.getMetadata().get(['entityDefs', this.options.rootEntityType, 'links']) || {};
            const base = 'x' + entityType.replace(/[^a-zA-Z0-9]/g, '');
            let name = base;
            let i = 2;

            while (used.includes(name) || name in fields || name in links) {
                name = base + i++;
            }

            return name;
        }

        apply() {
            const $ = name => this.element.querySelector(`[data-name="${name}"]`);
            const name = $('name').value.trim();

            if (!/^[a-zA-Z][a-zA-Z0-9]{0,39}$/.test(name)) {
                Espo.Ui.warning(this.translate('Invalid key', 'labels', 'AdvancedCrosstab'));

                return;
            }

            const fields = this.getMetadata().get(['entityDefs', this.options.rootEntityType, 'fields']) || {};
            const links = this.getMetadata().get(['entityDefs', this.options.rootEntityType, 'links']) || {};

            if ((this.options.joins || []).some(j => j.name === name) || name in fields || name in links) {
                Espo.Ui.warning(this.translate('Key already used', 'labels', 'AdvancedCrosstab'));

                return;
            }

            const join = {
                name: name,
                from: this.from,
                localField: $('localField').value,
                entityType: $('entityType').value,
                foreignField: $('foreignField').value,
            };

            if ($('label').value.trim()) {
                join.label = $('label').value.trim();
            }

            this.options.onApply(join);
            this.close();
        }
    };
});
