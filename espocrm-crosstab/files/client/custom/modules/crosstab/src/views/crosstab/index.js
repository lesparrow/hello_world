define('crosstab:views/crosstab/index', ['view'], function (Dep) {

    var GROUPABLE_TYPES = ['enum', 'varchar', 'bool', 'link', 'int', 'date', 'datetime', 'datetimeOptional'];
    var DATE_TYPES = ['date', 'datetime', 'datetimeOptional'];
    var NUMERIC_TYPES = ['int', 'float', 'currency'];
    var AGGREGATES = ['COUNT', 'SUM', 'AVG', 'MIN', 'MAX'];
    var GRANULARITIES = ['year', 'quarter', 'month', 'day'];
    var DISPLAY_MODES = ['value', 'rowPercent', 'columnPercent', 'totalPercent'];

    function esc(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function option(value, label, selected) {
        return '<option value="' + esc(value) + '"' + (selected ? ' selected' : '') + '>' + esc(label) + '</option>';
    }

    return Dep.extend({

        templateContent: `
            <style>
                .crosstab-form .form-group { margin-bottom: 10px; }
                .crosstab-wrap { overflow: auto; max-height: 70vh; }
                .crosstab-table { width: auto; min-width: 100%; }
                .crosstab-table th, .crosstab-table td { white-space: nowrap; }
                .crosstab-table td.num, .crosstab-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
                .crosstab-table thead th { position: sticky; top: 0; background: var(--default-heading-bg-color, #f5f5f5); z-index: 2; cursor: pointer; }
                .crosstab-table tbody th { position: sticky; left: 0; background: var(--panel-bg, #fff); z-index: 1; font-weight: normal; }
                .crosstab-table .total { font-weight: 600; }
                .crosstab-table th.sorted::after { content: ' \\2193'; }
            </style>
            <div class="page-header"><h3>{{translate 'Crosstab' category='scopeNames'}}</h3></div>
            <div class="panel panel-default crosstab-form">
                <div class="panel-body">
                    <div class="row">
                        <div class="col-sm-3 form-group">
                            <label class="control-label">{{translate 'Entity' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="entityType"></select>
                        </div>
                        <div class="col-sm-3 form-group">
                            <label class="control-label">{{translate 'Filter' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="primaryFilter"></select>
                        </div>
                        <div class="col-sm-3 form-group">
                            <label class="control-label">{{translate 'Aggregate' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="aggregate"></select>
                        </div>
                        <div class="col-sm-3 form-group">
                            <label class="control-label">{{translate 'Value' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="valueField"></select>
                        </div>
                    </div>
                    <div class="row">
                        <div class="col-sm-3 form-group">
                            <label class="control-label">{{translate 'Rows' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="rowField"></select>
                        </div>
                        <div class="col-sm-2 form-group">
                            <label class="control-label">&nbsp;</label>
                            <select class="form-control" data-name="rowGranularity"></select>
                        </div>
                        <div class="col-sm-3 form-group">
                            <label class="control-label">{{translate 'Columns' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="columnField"></select>
                        </div>
                        <div class="col-sm-2 form-group">
                            <label class="control-label">&nbsp;</label>
                            <select class="form-control" data-name="columnGranularity"></select>
                        </div>
                        <div class="col-sm-2 form-group">
                            <label class="control-label">{{translate 'Display' scope='Crosstab'}}</label>
                            <select class="form-control" data-name="display"></select>
                        </div>
                    </div>
                    <div class="btn-group">
                        <button class="btn btn-primary" data-action="run">{{translate 'Run' scope='Crosstab'}}</button>
                        <button class="btn btn-default" data-action="swap" title="{{translate 'Swap' scope='Crosstab'}}"><span class="fas fa-exchange-alt"></span></button>
                        <button class="btn btn-default" data-action="exportCsv" disabled>{{translate 'Export CSV' scope='Crosstab'}}</button>
                    </div>
                </div>
            </div>
            <div class="crosstab-result"></div>
        `,

        events: {
            'change select[data-name="entityType"]': function (e) {
                this.config = {entityType: e.currentTarget.value};
                this.result = null;
                this.renderForm();
                this.$result.empty();
            },
            'change select[data-name]': function (e) {
                var name = e.currentTarget.getAttribute('data-name');

                if (name === 'entityType') {
                    return;
                }

                this.config[name] = e.currentTarget.value || null;

                if (name === 'display') {
                    this.saveConfig();
                    this.renderTable();

                    return;
                }

                this.renderForm();
            },
            'click [data-action="run"]': function () {
                this.run();
            },
            'click [data-action="swap"]': function () {
                this.swap();
            },
            'click [data-action="exportCsv"]': function () {
                this.exportCsv();
            },
            'click th[data-sort]': function (e) {
                var key = e.currentTarget.getAttribute('data-sort');

                this.sortKey = this.sortKey === key ? null : key;
                this.renderTable();
            },
        },

        setup: function () {
            this.entityTypeList = this.getEntityTypeList();

            var stored = this.getStorage().get('crosstab', 'config') || {};

            this.config = this.entityTypeList.indexOf(stored.entityType) !== -1 ?
                stored :
                {entityType: this.entityTypeList[0] || null};

            this.result = null;
            this.sortKey = null;
            this.requestId = 0;
        },

        afterRender: function () {
            this.$result = this.$el.find('.crosstab-result');
            this.renderForm();
        },

        getEntityTypeList: function () {
            var scopes = this.getMetadata().get('scopes') || {};

            return Object.keys(scopes)
                .filter(function (scope) {
                    var defs = scopes[scope];

                    return defs.entity && defs.object && !defs.disabled &&
                        this.getAcl().checkScope(scope, 'read');
                }, this)
                .sort(function (a, b) {
                    return this.translate(a, 'scopeNamesPlural').localeCompare(this.translate(b, 'scopeNamesPlural'));
                }.bind(this));
        },

        getFieldList: function (typeList) {
            var entityType = this.config.entityType;
            var fields = this.getMetadata().get(['entityDefs', entityType, 'fields']) || {};
            var forbidden = this.getAcl().getScopeForbiddenFieldList(entityType) || [];

            return Object.keys(fields)
                .filter(function (field) {
                    var defs = fields[field];

                    return typeList.indexOf(defs.type) !== -1 &&
                        !defs.disabled && !defs.notStorable && !defs.utility &&
                        forbidden.indexOf(field) === -1;
                })
                .sort(function (a, b) {
                    return this.translateField(a).localeCompare(this.translateField(b));
                }.bind(this));
        },

        getFieldType: function (field) {
            return this.getMetadata().get(['entityDefs', this.config.entityType, 'fields', field, 'type']);
        },

        isDateField: function (field) {
            return !!field && DATE_TYPES.indexOf(this.getFieldType(field)) !== -1;
        },

        translateField: function (field) {
            return this.translate(field, 'fields', this.config.entityType);
        },

        label: function (key) {
            return this.translate(key, 'labels', 'Crosstab');
        },

        /**
         * Rebuilds the select boxes from the current config. Cheap: plain strings, one DOM write per select.
         */
        renderForm: function () {
            var c = this.config;
            var self = this;

            var groupFields = c.entityType ? this.getFieldList(GROUPABLE_TYPES) : [];
            var numericFields = c.entityType ? this.getFieldList(NUMERIC_TYPES) : [];

            if (groupFields.indexOf(c.rowField) === -1) {
                c.rowField = groupFields[0] || null;
            }

            if (c.columnField && groupFields.indexOf(c.columnField) === -1) {
                c.columnField = null;
            }

            if (AGGREGATES.indexOf(c.aggregate) === -1 || (c.aggregate !== 'COUNT' && !numericFields.length)) {
                c.aggregate = 'COUNT';
            }

            if (c.aggregate === 'COUNT') {
                c.valueField = null;
            } else if (numericFields.indexOf(c.valueField) === -1) {
                c.valueField = numericFields[0];
            }

            c.rowGranularity = this.isDateField(c.rowField) ? (c.rowGranularity || 'month') : null;
            c.columnGranularity = this.isDateField(c.columnField) ? (c.columnGranularity || 'month') : null;

            if (DISPLAY_MODES.indexOf(c.display) === -1) {
                c.display = 'value';
            }

            var filterList = (this.getMetadata().get(['clientDefs', c.entityType, 'filterList']) || [])
                .map(function (item) {
                    return typeof item === 'string' ? item : item.name;
                })
                .filter(Boolean);

            if (filterList.indexOf(c.primaryFilter) === -1) {
                c.primaryFilter = null;
            }

            var fieldOptions = function (list, selected) {
                return list.map(function (field) {
                    return option(field, self.translateField(field), field === selected);
                }).join('');
            };

            var granularityOptions = function (selected) {
                return GRANULARITIES.map(function (item) {
                    return option(item, self.getLanguage().translateOption(item, 'granularity', 'Crosstab'), item === selected);
                }).join('');
            };

            var set = function (name, html, disabled) {
                self.$el.find('select[data-name="' + name + '"]')
                    .html(html)
                    .prop('disabled', !!disabled)
                    .toggleClass('hidden', disabled === 'hide');
            };

            set('entityType', this.entityTypeList.map(function (scope) {
                return option(scope, self.translate(scope, 'scopeNamesPlural'), scope === c.entityType);
            }).join(''));

            set('primaryFilter', option('', this.label('All'), !c.primaryFilter) + filterList.map(function (name) {
                return option(name, self.translate(name, 'presetFilters', c.entityType), name === c.primaryFilter);
            }).join(''));

            set('aggregate', AGGREGATES.map(function (item) {
                return option(item, self.getLanguage().translateOption(item, 'aggregate', 'Crosstab'), item === c.aggregate);
            }).join(''), !numericFields.length);

            set('valueField', fieldOptions(numericFields, c.valueField), c.aggregate === 'COUNT');

            set('rowField', fieldOptions(groupFields, c.rowField));
            set('rowGranularity', granularityOptions(c.rowGranularity), c.rowGranularity ? false : 'hide');

            set('columnField', option('', this.label('None'), !c.columnField) + fieldOptions(groupFields, c.columnField));
            set('columnGranularity', granularityOptions(c.columnGranularity), c.columnGranularity ? false : 'hide');

            set('display', DISPLAY_MODES.map(function (item) {
                return option(item, self.getLanguage().translateOption(item, 'display', 'Crosstab'), item === c.display);
            }).join(''));
        },

        saveConfig: function () {
            this.getStorage().set('crosstab', 'config', this.config);
        },

        swap: function () {
            var c = this.config;

            if (!c.columnField) {
                return;
            }

            var field = c.rowField;
            var granularity = c.rowGranularity;

            c.rowField = c.columnField;
            c.rowGranularity = c.columnGranularity;
            c.columnField = field;
            c.columnGranularity = granularity;

            this.renderForm();

            // Swapping is a pure transposition: no need to hit the server again.
            if (this.result && this.result.config.columnField) {
                var r = this.result;

                r.cells = r.cells.map(function (cell) {
                    return [cell[1], cell[0], cell[2]];
                });

                var tmp = r.rowTotals;

                r.rowTotals = r.columnTotals;
                r.columnTotals = tmp;
                tmp = r.rowLabels;
                r.rowLabels = r.columnLabels;
                r.columnLabels = tmp;
                r.config = Object.assign({}, c);

                this.sortKey = null;
                this.saveConfig();
                this.renderTable();
            }
        },

        run: function () {
            var c = this.config;

            if (!c.rowField) {
                Espo.Ui.warning(this.label('Select row field'));

                return;
            }

            this.saveConfig();

            var requestId = ++this.requestId;
            var config = Object.assign({}, c);

            Espo.Ui.notify(' ... ');

            Espo.Ajax
                .postRequest('Crosstab/action/run', {
                    entityType: c.entityType,
                    rowField: c.rowField,
                    rowGranularity: c.rowGranularity,
                    columnField: c.columnField,
                    columnGranularity: c.columnGranularity,
                    aggregate: c.aggregate,
                    valueField: c.valueField,
                    primaryFilter: c.primaryFilter,
                })
                .then(function (result) {
                    // Ignore responses of outdated requests.
                    if (requestId !== this.requestId) {
                        return;
                    }

                    Espo.Ui.notify(false);

                    result.config = config;
                    this.result = result;
                    this.sortKey = null;
                    this.renderTable();
                }.bind(this));
        },

        /**
         * @return {{rows: string[], columns: string[], matrix: Object, max: number}}
         */
        buildModel: function () {
            var r = this.result;
            var matrix = {};
            var max = 0;

            r.cells.forEach(function (cell) {
                (matrix[cell[0]] = matrix[cell[0]] || {})[cell[1]] = cell[2];
                max = Math.max(max, Math.abs(cell[2]));
            });

            var rows = this.sortKeys(Object.keys(r.rowTotals), r.config.rowField, r.config.rowGranularity, r.rowLabels);
            var columns = r.config.columnField ?
                this.sortKeys(Object.keys(r.columnTotals), r.config.columnField, r.config.columnGranularity, r.columnLabels) :
                [''];

            if (this.sortKey !== null) {
                var key = this.sortKey;
                var value = function (row) {
                    return key === '__total' ? r.rowTotals[row] : ((matrix[row] || {})[key] || 0);
                };

                rows.sort(function (a, b) {
                    return value(b) - value(a);
                });
            }

            return {rows: rows, columns: columns, matrix: matrix, max: max};
        },

        sortKeys: function (keys, field, granularity, linkLabels) {
            var type = this.getFieldType(field);
            var self = this;
            var natural = granularity || type === 'int';
            var options = type === 'enum' ?
                (this.getMetadata().get(['entityDefs', this.result.config.entityType, 'fields', field, 'options']) || []) :
                null;

            return keys.sort(function (a, b) {
                if (a === '' || b === '') {
                    return a === '' ? 1 : -1;
                }

                if (type === 'int') {
                    return a - b;
                }

                if (natural) {
                    return a < b ? -1 : 1;
                }

                if (options) {
                    return options.indexOf(a) - options.indexOf(b);
                }

                return self.keyLabel(a, field, granularity, linkLabels)
                    .localeCompare(self.keyLabel(b, field, granularity, linkLabels));
            });
        },

        keyLabel: function (key, field, granularity, linkLabels) {
            if (key === '') {
                return this.label('Empty');
            }

            var entityType = this.result.config.entityType;
            var type = this.getFieldType(field);

            if (type === 'link') {
                return linkLabels[key] || key;
            }

            if (type === 'enum') {
                return this.getLanguage().translateOption(key, field, entityType);
            }

            if (type === 'bool') {
                return this.translate(key === '1' ? 'Yes' : 'No');
            }

            if (granularity === 'quarter') {
                var parts = key.split('_');

                return 'Q' + parts[1] + ' ' + parts[0];
            }

            if (granularity === 'month' && window.moment) {
                return window.moment(key + '-01').format('MMM YYYY');
            }

            if (granularity === 'day' && window.moment) {
                return this.getDateTime().toDisplayDate(key);
            }

            return key;
        },

        /**
         * Applies the display mode (raw value or percentage).
         */
        displayValue: function (value, row, column) {
            var r = this.result;
            var base;

            switch (this.config.display) {
                case 'rowPercent':
                    base = row === null ? r.grandTotal : r.rowTotals[row];
                    break;
                case 'columnPercent':
                    base = column === null ? r.grandTotal : r.columnTotals[column];
                    break;
                case 'totalPercent':
                    base = r.grandTotal;
                    break;
                default:
                    return this.formatNumber(value);
            }

            return base ? this.formatNumber(value / base * 100) + ' %' : '';
        },

        formatNumber: function (value) {
            if (value === undefined || value === null) {
                return '';
            }

            if (!this.numberFormat) {
                var language = (this.getPreferences().get('language') || this.getConfig().get('language') || 'en_US');

                this.numberFormat = new Intl.NumberFormat(language.replace('_', '-'), {maximumFractionDigits: 2});
            }

            return this.numberFormat.format(value);
        },

        renderTable: function () {
            var r = this.result;

            this.$el.find('[data-action="exportCsv"]').prop('disabled', !r || !r.cells.length);

            if (!r) {
                return;
            }

            if (!r.cells.length) {
                this.$result.html('<div class="well">' + esc(this.label('No data')) + '</div>');

                return;
            }

            var m = this.buildModel();
            var c = r.config;
            var self = this;
            var hasColumns = !!c.columnField;
            var sortKey = this.sortKey;
            var html = [];

            if (r.truncated) {
                html.push('<div class="alert alert-warning">' + esc(this.label('Truncated')) + '</div>');
            }

            html.push('<div class="crosstab-wrap"><table class="table table-bordered table-condensed crosstab-table"><thead><tr>');
            html.push('<th>' + esc(this.translateField(c.rowField)) +
                (hasColumns ? ' \\ ' + esc(this.translateField(c.columnField)) : '') + '</th>');

            if (hasColumns) {
                m.columns.forEach(function (column) {
                    html.push('<th class="num' + (sortKey === column ? ' sorted' : '') + '" data-sort="' + esc(column) + '">' +
                        esc(self.keyLabel(column, c.columnField, c.columnGranularity, r.columnLabels)) + '</th>');
                });
            }

            html.push('<th class="num total' + (sortKey === '__total' ? ' sorted' : '') + '" data-sort="__total">' +
                esc(hasColumns ? this.label('Total') :
                    this.getLanguage().translateOption(c.aggregate, 'aggregate', 'Crosstab')) + '</th>');
            html.push('</tr></thead><tbody>');

            m.rows.forEach(function (row) {
                var cells = m.matrix[row] || {};

                html.push('<tr><th>' + esc(self.keyLabel(row, c.rowField, c.rowGranularity, r.rowLabels)) + '</th>');

                if (hasColumns) {
                    m.columns.forEach(function (column) {
                        var value = cells[column];
                        var style = '';

                        if (value !== undefined && m.max) {
                            style = ' style="background-color: rgba(66, 133, 244, ' +
                                (Math.abs(value) / m.max * 0.45).toFixed(3) + ')"';
                        }

                        html.push('<td class="num"' + style + '>' +
                            (value === undefined ? '' : esc(self.displayValue(value, row, column))) + '</td>');
                    });
                }

                html.push('<td class="num total">' + esc(self.displayValue(r.rowTotals[row], row, null)) + '</td></tr>');
            });

            if (hasColumns || m.rows.length > 1) {
                html.push('<tr class="total"><th class="total">' + esc(this.label('Total')) + '</th>');

                if (hasColumns) {
                    m.columns.forEach(function (column) {
                        html.push('<td class="num total">' + esc(self.displayValue(r.columnTotals[column], null, column)) + '</td>');
                    });
                }

                html.push('<td class="num total">' + esc(this.displayValue(r.grandTotal, null, null)) + '</td></tr>');
            }

            html.push('</tbody></table></div>');

            this.$result.html(html.join(''));
        },

        exportCsv: function () {
            var r = this.result;

            if (!r) {
                return;
            }

            var m = this.buildModel();
            var c = r.config;
            var self = this;
            var hasColumns = !!c.columnField;
            var q = function (value) {
                return '"' + String(value).replace(/"/g, '""') + '"';
            };
            var lines = [];
            var header = [this.translateField(c.rowField)];

            if (hasColumns) {
                m.columns.forEach(function (column) {
                    header.push(self.keyLabel(column, c.columnField, c.columnGranularity, r.columnLabels));
                });
            }

            header.push(this.label('Total'));
            lines.push(header.map(q).join(';'));

            m.rows.forEach(function (row) {
                var line = [self.keyLabel(row, c.rowField, c.rowGranularity, r.rowLabels)];

                if (hasColumns) {
                    m.columns.forEach(function (column) {
                        var value = (m.matrix[row] || {})[column];

                        line.push(value === undefined ? '' : self.displayValue(value, row, column));
                    });
                }

                line.push(self.displayValue(r.rowTotals[row], row, null));
                lines.push(line.map(q).join(';'));
            });

            var footer = [this.label('Total')];

            if (hasColumns) {
                m.columns.forEach(function (column) {
                    footer.push(self.displayValue(r.columnTotals[column], null, column));
                });
            }

            footer.push(this.displayValue(r.grandTotal, null, null));
            lines.push(footer.map(q).join(';'));

            // BOM so that Excel detects UTF-8.
            var blob = new Blob(['﻿' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
            var link = document.createElement('a');

            link.href = URL.createObjectURL(blob);
            link.download = 'crosstab-' + c.entityType + '.csv';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            setTimeout(function () {
                URL.revokeObjectURL(link.href);
            }, 1000);
        },
    });
});
