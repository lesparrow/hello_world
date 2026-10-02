define('advanced-crosstab:lib/schema', [], function () {

    const DIMENSION_TYPES = [
        'varchar', 'enum', 'bool', 'int', 'float', 'currency', 'date', 'datetime', 'datetimeOptional',
        'link', 'personName', 'url', 'autoincrement', 'number', 'duration', 'enumInt', 'enumFloat',
    ];

    const NUMERIC_TYPES = ['int', 'float', 'currency', 'autoincrement', 'duration', 'enumInt', 'enumFloat'];
    const DATE_TYPES = ['date', 'datetime', 'datetimeOptional'];
    const MAX_DEPTH = 3;

    /**
     * Metadata-driven schema: entities, fields and many-to-one relations available to the current user.
     * Mirrors the server rules (the server always re-validates).
     */
    class Schema {

        /**
         * @param {import('view').default} view
         */
        constructor(view) {
            this.metadata = view.getMetadata();
            this.language = view.getLanguage();
            this.acl = view.getAcl();
            this.forbiddenCache = {};
        }

        static get DIMENSION_TYPES() { return DIMENSION_TYPES; }
        static get NUMERIC_TYPES() { return NUMERIC_TYPES; }
        static get DATE_TYPES() { return DATE_TYPES; }
        static get MAX_DEPTH() { return MAX_DEPTH; }

        getEntityTypeList() {
            const scopes = this.metadata.get('scopes') || {};

            return Object.keys(scopes)
                .filter(scope => {
                    const defs = scopes[scope];

                    return defs.entity && !defs.disabled && scope !== 'AdvancedCrosstab' &&
                        (defs.object || defs.tab || defs.customizable) &&
                        this.acl.checkScope(scope, 'read');
                })
                .sort((a, b) => this.translateEntity(a).localeCompare(this.translateEntity(b)));
        }

        translateEntity(entityType, plural = true) {
            return this.language.translate(entityType, plural ? 'scopeNamesPlural' : 'scopeNames');
        }

        translateField(entityType, field) {
            if (field === 'id') {
                return 'ID';
            }

            return this.language.translate(field, 'fields', entityType);
        }

        isForbidden(entityType, field) {
            if (!(entityType in this.forbiddenCache)) {
                this.forbiddenCache[entityType] = this.acl.getScopeForbiddenFieldList(entityType, 'read') || [];
            }

            return this.forbiddenCache[entityType].includes(field);
        }

        getFieldDefs(entityType, field) {
            return this.metadata.get(['entityDefs', entityType, 'fields', field]) || null;
        }

        getFieldType(entityType, field) {
            if (field === 'id') {
                return 'id';
            }

            const defs = this.getFieldDefs(entityType, field);

            return defs ? defs.type : null;
        }

        /**
         * Target of a many-to-one link, if usable.
         */
        getLinkTarget(entityType, link) {
            const fieldDefs = this.getFieldDefs(entityType, link);
            const linkDefs = this.metadata.get(['entityDefs', entityType, 'links', link]) || {};

            if (!fieldDefs || fieldDefs.type !== 'link' || fieldDefs.disabled || linkDefs.type !== 'belongsTo') {
                return null;
            }

            const target = linkDefs.entity;

            if (!target || !this.metadata.get(['scopes', target, 'entity']) || !this.acl.checkScope(target, 'read')) {
                return null;
            }

            if (this.isForbidden(entityType, link)) {
                return null;
            }

            return target;
        }

        /**
         * @param {string} entityType
         * @param {'dimension'|'numeric'|'any'} purpose
         * @return {{name: string, type: string, label: string}[]}
         */
        getFieldList(entityType, purpose = 'any') {
            const fields = this.metadata.get(['entityDefs', entityType, 'fields']) || {};

            const allowed = purpose === 'numeric' ? NUMERIC_TYPES : DIMENSION_TYPES.concat(['text']);

            return Object.keys(fields)
                .filter(field => {
                    const defs = fields[field];

                    if (!allowed.includes(defs.type)) {
                        return false;
                    }

                    if (purpose === 'dimension' && defs.type === 'text') {
                        return false;
                    }

                    return !defs.disabled && !defs.notStorable && !defs.utility && !this.isForbidden(entityType, field);
                })
                .map(field => ({name: field, type: fields[field].type, label: this.translateField(entityType, field)}))
                .sort((a, b) => a.label.localeCompare(b.label));
        }

        /**
         * @return {{name: string, entityType: string, label: string}[]}
         */
        getLinkList(entityType) {
            const fields = this.metadata.get(['entityDefs', entityType, 'fields']) || {};

            return Object.keys(fields)
                .filter(field => fields[field].type === 'link')
                .map(field => ({name: field, entityType: this.getLinkTarget(entityType, field)}))
                .filter(item => item.entityType)
                .map(item => ({...item, label: this.translateField(entityType, item.name)}))
                .sort((a, b) => a.label.localeCompare(b.label));
        }

        /**
         * One-to-many and many-to-many links: not usable as dimensions from this entity (they would duplicate rows),
         * but the related entity can be used as the data source instead.
         *
         * @return {{name: string, entityType: string, label: string, manyToMany: boolean, foreign: ?string}[]}
         */
        getToManyLinkList(entityType) {
            const links = this.metadata.get(['entityDefs', entityType, 'links']) || {};

            return Object.keys(links)
                .filter(link => ['hasMany', 'hasChildren'].includes(links[link].type) && links[link].entity &&
                    !links[link].disabled && !links[link].utility &&
                    this.metadata.get(['scopes', links[link].entity, 'entity']) &&
                    this.acl.checkScope(links[link].entity, 'read') &&
                    !this.isForbidden(entityType, link))
                .map(link => ({
                    name: link,
                    entityType: links[link].entity,
                    label: this.translateField(entityType, link) !== link ?
                        this.translateField(entityType, link) :
                        this.language.translate(link, 'links', entityType),
                    manyToMany: !!links[link].relationName,
                    foreign: links[link].foreign || null,
                }))
                .sort((a, b) => a.label.localeCompare(b.label));
        }

        /**
         * @return {{entityType: string, field: string, type: string, valid: boolean}}
         */
        resolvePath(rootEntityType, path) {
            const parts = (path || '').split('.');
            let entityType = rootEntityType;

            for (const link of parts.slice(0, -1)) {
                const target = this.getLinkTarget(entityType, link);

                if (!target) {
                    return {entityType, field: parts[parts.length - 1], type: null, valid: false};
                }

                entityType = target;
            }

            const field = parts[parts.length - 1];
            const type = this.getFieldType(entityType, field);

            return {entityType, field, type, valid: !!type && !this.isForbidden(entityType, field)};
        }

        getPathLabel(rootEntityType, path) {
            if (!path) {
                return '';
            }

            const parts = path.split('.');
            const labels = [];
            let entityType = rootEntityType;

            for (const part of parts) {
                labels.push(this.translateField(entityType, part));
                entityType = this.getLinkTarget(entityType, part) || entityType;
            }

            return labels.join(' › ');
        }

        getEnumOptions(rootEntityType, path) {
            const resolved = this.resolvePath(rootEntityType, path);

            const options = this.metadata.get(['entityDefs', resolved.entityType, 'fields', resolved.field, 'options']) || [];

            return options.map(value => ({
                value: value,
                label: value === '' ? '—' :
                    this.language.translateOption(value, resolved.field, resolved.entityType),
            }));
        }
    }

    return Schema;
});
