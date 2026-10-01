define('advanced-crosstab:views/advanced-crosstab/result/table', ['view'], function (View) {

    const AUTO_COLLAPSE_NODE_COUNT = 400;

    /**
     * Pivot table: hierarchical rows and columns with expand/collapse, subtotals, totals,
     * comparison cells, ranks, interactive re-sorting (client-side, no query) and drill-down.
     *
     * Options: result, formatter, drillDown (bool), onDrillDown({rowPath, columnPath, measure}).
     */
    return class extends View {

        templateContent = `<div class="acx-table-wrap" data-role="wrap"></div>`

        setup() {
            this.collapsedRows = new Set();
            this.collapsedColumns = new Set();
            this.sort = null;

            const result = this.options.result;
            const count = nodes => nodes.reduce((sum, node) => sum + 1 + count(node.c || []), 0);

            if (count(result.rows) > AUTO_COLLAPSE_NODE_COUNT) {
                result.rows.forEach(node => node.c && this.collapsedRows.add(JSON.stringify([node.k])));
            }
        }

        afterRender() {
            this.wrap = this.element.querySelector('[data-role="wrap"]');

            this.wrap.addEventListener('click', e => this.onClick(e));
            this.draw();
        }

        t(label) {
            return this.translate(label, 'labels', 'AdvancedCrosstab');
        }

        value(rowPath, columnPath, index) {
            const result = this.options.result;
            const row = result.cells[JSON.stringify(rowPath)];

            if (!row) {
                return null;
            }

            const cell = row[JSON.stringify(columnPath)];

            return cell ? cell[index] ?? null : null;
        }

        /**
         * Visible column leaves: [{path, label, depth, subtotal}].
         */
        getLeaves() {
            const result = this.options.result;
            const subtotals = result.options.subtotals;
            const leaves = [];

            const walk = (nodes, prefix, depth) => {
                for (const node of nodes) {
                    const path = prefix.concat([node.k]);
                    const id = JSON.stringify(path);

                    if (node.c && !this.collapsedColumns.has(id)) {
                        walk(node.c, path, depth + 1);

                        if (subtotals) {
                            leaves.push({path, depth: depth + 1, subtotal: true});
                        }

                        continue;
                    }

                    leaves.push({path, depth, subtotal: false, node});
                }
            };

            if (result.columns.length) {
                walk(result.columns, [], 0);

                if (result.options.rowTotals) {
                    leaves.push({path: [], depth: 0, subtotal: true, grand: true});
                }
            } else {
                leaves.push({path: [], depth: 0, subtotal: false, grand: true});
            }

            return leaves;
        }

        sortNodes(nodes, prefix) {
            if (!this.sort) {
                return nodes;
            }

            const {columnPath, index, direction} = this.sort;

            return nodes.slice().sort((a, b) => {
                const va = this.value(prefix.concat([a.k]), columnPath, index);
                const vb = this.value(prefix.concat([b.k]), columnPath, index);

                if (va === vb) {
                    return 0;
                }

                if (va === null) {
                    return 1;
                }

                if (vb === null) {
                    return -1;
                }

                return direction === 'desc' ? vb - va : va - vb;
            });
        }

        draw() {
            const result = this.options.result;
            const formatter = this.options.formatter;
            const valueColumns = result.valueColumns;
            const measures = Object.fromEntries(result.measures.map(m => [m.key, m]));
            const C = result.columnDimensions.length;
            const leaves = this.getLeaves();
            const canCollapseColumns = result.options.subtotals;
            const html = [];

            this.leaves = leaves;
            this.rowPaths = [];

            const showMeasureRow = valueColumns.length > 1 || C === 0;
            const headerRows = C + (showMeasureRow ? 1 : 0);
            const VC = valueColumns.length;

            html.push('<table class="table table-bordered table-condensed acx-pivot"><thead>');

            // Column header rows.
            const leafCount = (node, prefix) => {
                const id = JSON.stringify(prefix.concat([node.k]));

                if (!node.c || this.collapsedColumns.has(id)) {
                    return 1;
                }

                return node.c.reduce((sum, child) => sum + leafCount(child, prefix.concat([node.k])), 0) +
                    (result.options.subtotals ? 1 : 0);
            };

            const rowDimensionLabel = result.rowDimensions.map(d => d.label).join(' › ');

            for (let level = 0; level < headerRows; level++) {
                html.push('<tr>');

                if (level === 0) {
                    html.push(`<th class="acx-corner" rowspan="${headerRows}">${this.escapeString(rowDimensionLabel)}` +
                        (C ? `<div class="acx-corner-columns small text-muted">${this.escapeString(result.columnDimensions.map(d => d.label).join(' › '))}</div>` : '') +
                        '</th>');
                }

                if (level === C) {
                    leaves.forEach((leaf, leafIndex) => {
                        valueColumns.forEach((column, index) => {
                            const isSorted = this.sort && this.sort.leaf === leafIndex && this.sort.index === index;

                            html.push(`<th class="acx-measure-header acx-num" data-action-sort="${leafIndex}:${index}"
                                title="${this.escapeString(this.t('Click to sort'))}">` +
                                this.escapeString(measures[column.measure].label + (column.variant === 'compare' ? ' Δ' : '')) +
                                (isSorted ? ` <span class="fas fa-sort-amount-${this.sort.direction === 'desc' ? 'down' : 'up'}"></span>` : '') +
                                '</th>');
                        });
                    });
                } else {
                    // Nodes at this level along the visible leaves.
                    const cells = [];

                    const walk = (nodes, prefix, depth) => {
                        for (const node of nodes) {
                            const path = prefix.concat([node.k]);
                            const id = JSON.stringify(path);
                            const expanded = node.c && !this.collapsedColumns.has(id);

                            if (depth === level) {
                                const span = leafCount(node, prefix) * VC;
                                const rowspan = expanded ? 1 : C - level + (showMeasureRow ? 0 : 0);
                                const toggle = node.c && canCollapseColumns ?
                                    `<a role="button" class="acx-toggle" data-toggle-column="${this.escapeString(id)}">
                                        <span class="fas fa-${expanded ? 'minus' : 'plus'}-square"></span></a> ` : '';

                                cells.push(`<th colspan="${span}" rowspan="${rowspan}" class="acx-column-header">${toggle}${this.escapeString(node.l)}` +
                                    (node.r ? ` <span class="badge acx-rank">#${node.r}</span>` : '') + '</th>');

                                continue;
                            }

                            if (depth < level && expanded) {
                                walk(node.c, path, depth + 1);

                                if (result.options.subtotals && depth + 1 === level) {
                                    cells.push(`<th colspan="${VC}" rowspan="${C - level}" class="acx-column-header acx-subtotal">${this.escapeString(this.t('Total'))}</th>`);
                                }
                            }
                        }
                    };

                    walk(result.columns, [], 0);

                    if (level === 0 && result.options.rowTotals && C) {
                        cells.push(`<th colspan="${VC}" rowspan="${C}" class="acx-column-header acx-grand">${this.escapeString(this.t('Total'))}</th>`);
                    }

                    html.push(cells.join(''));
                }

                html.push('</tr>');
            }

            html.push('</thead><tbody>');

            const renderValues = (rowPath, rowIndex, isTotalRow) => {
                leaves.forEach((leaf, leafIndex) => {
                    valueColumns.forEach((column, index) => {
                        const value = this.value(rowPath, leaf.path, index);
                        const measure = measures[column.measure];
                        const isCompare = column.variant === 'compare';
                        const classes = ['acx-num'];

                        if (leaf.subtotal || leaf.grand || isTotalRow) {
                            classes.push('acx-total-cell');
                        }

                        if (isCompare && value !== null) {
                            classes.push(value > 0 ? 'acx-up' : value < 0 ? 'acx-down' : '');
                        }

                        const drillable = this.options.drillDown && measure.drillable && !isCompare && value !== null;

                        if (drillable) {
                            classes.push('acx-drill');
                        }

                        html.push(`<td class="${classes.join(' ')}"${drillable ? ` data-cell="${rowIndex}:${leafIndex}:${index}"` : ''}>` +
                            this.escapeString(formatter.format(value, measure.format, column.variant, measure.compareMode)) + '</td>');
                    });
                });
            };

            const walkRows = (nodes, prefix, level) => {
                for (const node of this.sortNodes(nodes, prefix)) {
                    const path = prefix.concat([node.k]);
                    const id = JSON.stringify(path);
                    const expanded = node.c && !this.collapsedRows.has(id);
                    const rowIndex = this.rowPaths.push(path) - 1;

                    html.push(`<tr class="acx-level-${Math.min(level, 4)}${node.c ? ' acx-parent' : ''}">`);
                    html.push(`<th class="acx-row-header" style="padding-left: ${8 + level * 18}px">` +
                        (node.c ? `<a role="button" class="acx-toggle" data-toggle-row="${this.escapeString(id)}">
                            <span class="fas fa-${expanded ? 'minus' : 'plus'}-square"></span></a> ` : '<span class="acx-toggle-spacer"></span>') +
                        this.escapeString(node.l) +
                        (node.r ? ` <span class="badge acx-rank">#${node.r}</span>` : '') + '</th>');

                    renderValues(path, rowIndex, false);
                    html.push('</tr>');

                    if (expanded) {
                        walkRows(node.c, path, level + 1);
                    }
                }
            };

            walkRows(result.rows, [], 0);

            if (!result.rows.length || (result.options.columnTotals && result.rows.length)) {
                const rowIndex = this.rowPaths.push([]) - 1;

                html.push(`<tr class="acx-grand-row"><th class="acx-row-header">${this.escapeString(this.t('Total'))}</th>`);
                renderValues([], rowIndex, true);
                html.push('</tr>');
            }

            html.push('</tbody></table>');

            this.wrap.innerHTML = html.join('');
        }

        onClick(e) {
            const rowToggle = e.target.closest('[data-toggle-row]');

            if (rowToggle) {
                this.toggle(this.collapsedRows, rowToggle.dataset.toggleRow);

                return;
            }

            const columnToggle = e.target.closest('[data-toggle-column]');

            if (columnToggle) {
                this.toggle(this.collapsedColumns, columnToggle.dataset.toggleColumn);

                return;
            }

            const sortHeader = e.target.closest('[data-action-sort]');

            if (sortHeader) {
                const [leaf, index] = sortHeader.dataset.actionSort.split(':').map(Number);
                const same = this.sort && this.sort.leaf === leaf && this.sort.index === index;

                this.sort = !same ? {leaf, index, direction: 'desc', columnPath: this.leaves[leaf].path} :
                    (this.sort.direction === 'desc' ? {...this.sort, direction: 'asc'} : null);

                this.draw();

                return;
            }

            const cell = e.target.closest('[data-cell]');

            if (cell && this.options.onDrillDown) {
                const [rowIndex, leafIndex, index] = cell.dataset.cell.split(':').map(Number);

                this.options.onDrillDown({
                    rowPath: this.rowPaths[rowIndex],
                    columnPath: this.leaves[leafIndex].path,
                    measure: this.options.result.valueColumns[index].measure,
                });
            }
        }

        toggle(set, id) {
            set.has(id) ? set.delete(id) : set.add(id);
            this.draw();
        }

        expandAll(expand) {
            this.collapsedRows.clear();
            this.collapsedColumns.clear();

            if (!expand) {
                const collect = (nodes, prefix, set) => nodes.forEach(node => {
                    if (node.c) {
                        set.add(JSON.stringify(prefix.concat([node.k])));
                        collect(node.c, prefix.concat([node.k]), set);
                    }
                });

                collect(this.options.result.rows, [], this.collapsedRows);
            }

            this.draw();
        }
    };
});
