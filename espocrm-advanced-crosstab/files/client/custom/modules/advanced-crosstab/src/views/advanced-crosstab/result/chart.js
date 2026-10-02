define('advanced-crosstab:views/advanced-crosstab/result/chart', ['view'], function (View) {

    // Categorical palette (validated light/dark steps), assigned in fixed order.
    const PALETTE = {
        light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
        dark: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
    };

    const MAX_SERIES = 8;
    const MAX_CATEGORIES = 40;

    /**
     * Charts drawn as SVG from the same aggregated result as the table (no extra query):
     * column, bar, stacked bar, line, pie, donut.
     *
     * Categories: top-level rows (or top-level columns when there are no rows).
     * Series: top-level columns (when there are rows and columns), else the selected measure.
     *
     * Options: result, formatter, chartType, measure (key).
     */
    return class extends View {

        templateContent = `<div class="acx-chart" data-role="chart"></div>`

        setup() {
            this.isDark = !!this.getThemeManager().getParam('isDark');
        }

        afterRender() {
            this.container = this.element.querySelector('[data-role="chart"]');
            this.draw();

            this.resizeHandler = () => {
                clearTimeout(this.resizeTimeout);
                this.resizeTimeout = setTimeout(() => this.draw(), 150);
            };

            window.addEventListener('resize', this.resizeHandler);
            this.once('remove', () => window.removeEventListener('resize', this.resizeHandler));
        }

        t(label) {
            return this.translate(label, 'labels', 'AdvancedCrosstab');
        }

        getData() {
            const result = this.options.result;
            const measures = result.measures.filter(m => !m.hidden);
            const measure = measures.find(m => m.key === this.options.measure) || measures[0];
            const valueIndex = result.valueColumns.findIndex(c => c.measure === measure.key && c.variant === 'value');
            const cell = (rowPath, columnPath) =>
                ((result.cells[JSON.stringify(rowPath)] || {})[JSON.stringify(columnPath)] || [])[valueIndex] ?? null;

            const hasRows = result.rows.length > 0;
            const hasColumns = result.columns.length > 0;

            let categories;
            let series;

            if (hasRows) {
                categories = result.rows.map(node => ({key: node.k, label: node.l, path: [node.k]}));

                series = hasColumns ?
                    result.columns.map(node => ({name: node.l, path: [node.k]})) :
                    [{name: measure.label, path: []}];

                series = series.map(s => ({...s, values: categories.map(c => cell(c.path, s.path))}));
            } else if (hasColumns) {
                categories = result.columns.map(node => ({key: node.k, label: node.l, path: [node.k]}));
                series = [{name: measure.label, values: categories.map(c => cell([], c.path))}];
            } else {
                categories = [{label: measure.label}];
                series = [{name: measure.label, values: [cell([], [])]}];
            }

            const notes = [];

            if (categories.length > MAX_CATEGORIES) {
                notes.push(this.t('chartCategoriesTruncated').replace('{n}', MAX_CATEGORIES).replace('{total}', categories.length));
                categories = categories.slice(0, MAX_CATEGORIES);
                series.forEach(s => s.values = s.values.slice(0, MAX_CATEGORIES));
            }

            if (series.length > MAX_SERIES) {
                notes.push(this.t('chartSeriesTruncated').replace('{n}', MAX_SERIES).replace('{total}', series.length));
                series = series.slice(0, MAX_SERIES);
            }

            return {categories, series, measure, notes};
        }

        draw() {
            if (!this.container) {
                return;
            }

            const data = this.getData();
            const type = this.options.chartType || 'column';
            const width = Math.max(320, this.container.clientWidth || 600);
            const colors = PALETTE[this.isDark ? 'dark' : 'light'];

            this.format = value => this.options.formatter.format(value, data.measure.format);
            this.compact = value => this.options.formatter.compact(value, data.measure.format);

            let svg;

            if (type === 'pie' || type === 'donut') {
                svg = this.drawPie(data, width, colors, type === 'donut');
            } else if (type === 'line') {
                svg = this.drawLine(data, width, colors);
            } else {
                svg = this.drawBars(data, width, colors, type);
            }

            const isPie = type === 'pie' || type === 'donut';

            const legend = isPie ?
                this.legend((this.pieItems || []).map((item, i) => ({
                    name: item.label,
                    color: item.other ? 'var(--acx-muted)' : colors[i],
                }))) :
                (data.series.length > 1 ? this.legend(data.series.map((s, i) => ({name: s.name, color: colors[i]}))) : '');

            this.container.innerHTML = `
                <div class="acx-chart-title">${this.escapeString(data.measure.label)}</div>
                ${legend}
                <div class="acx-chart-plot">${svg}</div>
                <div class="acx-chart-tooltip hidden" data-role="tooltip"></div>
                ${data.notes.map(n => `<div class="small text-muted">${this.escapeString(n)}</div>`).join('')}
            `;

            this.bindTooltip();
        }

        /**
         * Fixed height, or the available height when embedded in a dashlet (option `height`).
         */
        getPlotHeight() {
            return this.options.height ? Math.max(160, this.options.height - 70) : 320;
        }

        legend(items) {
            return `<div class="acx-chart-legend">${items.map(item => `
                <span class="acx-legend-item"><span class="acx-legend-swatch" style="background:${item.color}"></span>${this.escapeString(item.name)}</span>`).join('')}
            </div>`;
        }

        tip(category, series, value) {
            return this.escapeString(category) + (series ? ' · ' + this.escapeString(series) : '') +
                '<br><strong>' + this.escapeString(this.format(value) || '—') + '</strong>';
        }

        bindTooltip() {
            const tooltip = this.container.querySelector('[data-role="tooltip"]');
            const plot = this.container.querySelector('.acx-chart-plot');

            plot.addEventListener('mousemove', e => {
                const target = e.target.closest('[data-tip]');

                if (!target) {
                    tooltip.classList.add('hidden');

                    return;
                }

                const box = this.container.getBoundingClientRect();

                tooltip.innerHTML = target.getAttribute('data-tip');
                tooltip.classList.remove('hidden');
                tooltip.style.left = Math.min(e.clientX - box.left + 12, box.width - tooltip.offsetWidth - 4) + 'px';
                tooltip.style.top = (e.clientY - box.top + 12) + 'px';
            });

            plot.addEventListener('mouseleave', () => tooltip.classList.add('hidden'));
        }

        scale(min, max) {
            min = Math.min(0, min);
            max = Math.max(0, max);

            if (min === max) {
                max = min + 1;
            }

            const rawStep = (max - min) / 5;
            const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
            const step = [1, 2, 2.5, 5, 10].map(f => f * magnitude).find(s => s >= rawStep);
            const ticks = [];

            for (let v = Math.floor(min / step) * step; v <= max + step * 0.001; v += step) {
                ticks.push(Math.round(v * 1e6) / 1e6);
            }

            if (ticks[ticks.length - 1] < max) {
                ticks.push(ticks[ticks.length - 1] + step);
            }

            return {min: ticks[0], max: ticks[ticks.length - 1], ticks};
        }

        truncate(text, length) {
            text = String(text);

            return text.length > length ? text.slice(0, length - 1) + '…' : text;
        }

        drawBars(data, width, colors, type) {
            const horizontal = type === 'bar' || type === 'stackedBar';
            const stacked = type === 'stackedBar';
            const {categories, series} = data;
            const n = categories.length;

            const totals = categories.map((c, i) => series.reduce((sum, s) => sum + (s.values[i] || 0), 0));
            const all = stacked ? totals.concat(categories.map((c, i) =>
                series.reduce((sum, s) => sum + Math.min(0, s.values[i] || 0), 0))) :
                series.flatMap(s => s.values.filter(v => v !== null));
            const scale = this.scale(Math.min(0, ...all), Math.max(0, ...all));

            const groupSize = horizontal ? Math.max(22, (stacked ? 1 : series.length) * 14 + 10) : null;
            const labelWidth = horizontal ? Math.min(180, Math.max(60, ...categories.map(c => String(c.label).length * 6.5))) : 0;
            const margin = {top: 10, right: 16, bottom: horizontal ? 24 : 56, left: horizontal ? labelWidth + 8 : 64};
            const height = horizontal ? margin.top + margin.bottom + n * groupSize : this.getPlotHeight();
            const plotW = width - margin.left - margin.right;
            const plotH = height - margin.top - margin.bottom;

            const valuePos = v => horizontal ?
                margin.left + (v - scale.min) / (scale.max - scale.min) * plotW :
                margin.top + plotH - (v - scale.min) / (scale.max - scale.min) * plotH;

            const parts = [];

            // Recessive grid and value axis.
            for (const tick of scale.ticks) {
                const p = valuePos(tick);

                parts.push(horizontal ?
                    `<line x1="${p}" x2="${p}" y1="${margin.top}" y2="${margin.top + plotH}" class="acx-grid${tick === 0 ? ' acx-zero' : ''}"/>
                     <text x="${p}" y="${height - 6}" text-anchor="middle" class="acx-axis-text">${this.escapeString(this.compact(tick))}</text>` :
                    `<line x1="${margin.left}" x2="${margin.left + plotW}" y1="${p}" y2="${p}" class="acx-grid${tick === 0 ? ' acx-zero' : ''}"/>
                     <text x="${margin.left - 6}" y="${p + 4}" text-anchor="end" class="acx-axis-text">${this.escapeString(this.compact(tick))}</text>`);
            }

            const band = (horizontal ? plotH : plotW) / n;
            const inner = band * 0.72;
            const barSize = stacked ? inner : Math.max(2, inner / series.length - 2);
            const zero = valuePos(0);

            categories.forEach((category, i) => {
                const start = (horizontal ? margin.top : margin.left) + i * band + (band - inner) / 2;
                let positive = 0;
                let negative = 0;

                series.forEach((s, j) => {
                    const value = s.values[i];

                    if (value === null || value === undefined) {
                        return;
                    }

                    let from = 0;

                    if (stacked) {
                        from = value >= 0 ? positive : negative;

                        if (value >= 0) {
                            positive += value;
                        } else {
                            negative += value;
                        }
                    }

                    const a = valuePos(from);
                    const b = valuePos(from + value);
                    const offset = stacked ? 0 : j * (barSize + 2);
                    const length = Math.abs(b - a);
                    // 2px surface gap between stacked segments.
                    const gap = stacked && j > 0 ? 1 : 0;
                    const tip = this.tip(category.label, series.length > 1 ? s.name : null, value);

                    parts.push(horizontal ?
                        `<rect x="${Math.min(a, b) + gap}" y="${start + offset}" width="${Math.max(0, length - gap * 2)}" height="${barSize}"
                            rx="${stacked ? 0 : 3}" fill="${colors[j]}" data-tip="${this.escapeString(tip)}"/>` :
                        `<rect x="${start + offset}" y="${Math.min(a, b) + gap}" width="${barSize}" height="${Math.max(0, length - gap * 2)}"
                            rx="${stacked ? 0 : 3}" fill="${colors[j]}" data-tip="${this.escapeString(tip)}"/>`);
                });

                const labelPos = start + inner / 2;

                parts.push(horizontal ?
                    `<text x="${margin.left - 6}" y="${labelPos + 4}" text-anchor="end" class="acx-axis-text">
                        <title>${this.escapeString(category.label)}</title>${this.escapeString(this.truncate(category.label, 28))}</text>` :
                    `<text x="${labelPos}" y="${margin.top + plotH + 14}" text-anchor="${n > 8 ? 'end' : 'middle'}" class="acx-axis-text"
                        ${n > 8 ? `transform="rotate(-35 ${labelPos} ${margin.top + plotH + 14})"` : ''}>
                        <title>${this.escapeString(category.label)}</title>${this.escapeString(this.truncate(category.label, n > 8 ? 14 : 18))}</text>`);
            });

            parts.push(horizontal ?
                `<line x1="${zero}" x2="${zero}" y1="${margin.top}" y2="${margin.top + plotH}" class="acx-baseline"/>` :
                `<line x1="${margin.left}" x2="${margin.left + plotW}" y1="${zero}" y2="${zero}" class="acx-baseline"/>`);

            return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">${parts.join('')}</svg>`;
        }

        drawLine(data, width, colors) {
            const {categories, series} = data;
            const n = categories.length;
            const values = series.flatMap(s => s.values.filter(v => v !== null));
            const scale = this.scale(Math.min(0, ...values), Math.max(0, ...values));
            const margin = {top: 12, right: 20, bottom: 56, left: 64};
            const height = this.getPlotHeight();
            const plotW = width - margin.left - margin.right;
            const plotH = height - margin.top - margin.bottom;
            const x = i => margin.left + (n === 1 ? plotW / 2 : i * plotW / (n - 1));
            const y = v => margin.top + plotH - (v - scale.min) / (scale.max - scale.min) * plotH;

            const parts = [];

            for (const tick of scale.ticks) {
                parts.push(`<line x1="${margin.left}" x2="${margin.left + plotW}" y1="${y(tick)}" y2="${y(tick)}" class="acx-grid${tick === 0 ? ' acx-zero' : ''}"/>
                    <text x="${margin.left - 6}" y="${y(tick) + 4}" text-anchor="end" class="acx-axis-text">${this.escapeString(this.compact(tick))}</text>`);
            }

            const every = Math.ceil(n / Math.max(1, Math.floor(plotW / 70)));

            categories.forEach((category, i) => {
                if (i % every === 0) {
                    parts.push(`<text x="${x(i)}" y="${margin.top + plotH + 16}" text-anchor="middle" class="acx-axis-text">
                        <title>${this.escapeString(category.label)}</title>${this.escapeString(this.truncate(category.label, 12))}</text>`);
                }
            });

            series.forEach((s, j) => {
                let path = '';
                let pen = false;

                s.values.forEach((value, i) => {
                    if (value === null || value === undefined) {
                        pen = false;

                        return;
                    }

                    path += (pen ? 'L' : 'M') + x(i).toFixed(1) + ',' + y(value).toFixed(1);
                    pen = true;
                });

                parts.push(`<path d="${path}" fill="none" stroke="${colors[j]}" stroke-width="2" stroke-linejoin="round"/>`);
            });

            // Hover columns: one hit target per category with all series values.
            categories.forEach((category, i) => {
                const tip = this.escapeString(category.label) + series.map((s, j) =>
                    `<br><span class="acx-legend-swatch" style="background:${colors[j]}"></span>${this.escapeString(s.name)}: <strong>${this.escapeString(this.format(s.values[i]) || '—')}</strong>`).join('');
                const half = n === 1 ? plotW / 2 : plotW / (n - 1) / 2;

                series.forEach((s, j) => {
                    if (s.values[i] !== null && s.values[i] !== undefined && n <= 60) {
                        parts.push(`<circle cx="${x(i)}" cy="${y(s.values[i])}" r="4" fill="${colors[j]}" class="acx-point"/>`);
                    }
                });

                parts.push(`<rect x="${x(i) - half}" y="${margin.top}" width="${half * 2}" height="${plotH}" fill="transparent" data-tip="${this.escapeString(tip)}"/>`);
            });

            return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img">${parts.join('')}</svg>`;
        }

        drawPie(data, width, colors, donut) {
            this.pieItems = [];

            const values = data.categories.map((c, i) => data.series.reduce((sum, s) => sum + (s.values[i] || 0), 0));
            let items = data.categories.map((c, i) => ({label: c.label, value: values[i]})).filter(item => item.value > 0);

            if (items.length > MAX_SERIES) {
                const rest = items.slice(MAX_SERIES - 1).reduce((sum, item) => sum + item.value, 0);

                items = items.slice(0, MAX_SERIES - 1).concat([{label: this.t('Other'), value: rest, other: true}]);
            }

            this.pieItems = items;

            const total = items.reduce((sum, item) => sum + item.value, 0);
            const size = Math.min(width, this.getPlotHeight());
            const radius = size / 2 - 8;
            const center = size / 2;
            const innerRadius = donut ? radius * 0.6 : 0;

            if (!total) {
                return `<div class="text-muted">${this.escapeString(this.t('No data'))}</div>`;
            }

            let angle = -Math.PI / 2;
            const parts = [];

            items.forEach((item, i) => {
                const sweep = item.value / total * Math.PI * 2;
                const end = angle + sweep;
                const large = sweep > Math.PI ? 1 : 0;
                const point = (r, a) => `${(center + r * Math.cos(a)).toFixed(2)},${(center + r * Math.sin(a)).toFixed(2)}`;
                const color = item.other ? 'var(--acx-muted)' : colors[i];
                const tip = this.tip(item.label, null, item.value) + ` (${(item.value / total * 100).toFixed(1)} %)`;

                const d = items.length === 1 ?
                    `M${point(radius, 0)}A${radius},${radius} 0 1 1 ${point(radius, Math.PI)}A${radius},${radius} 0 1 1 ${point(radius, 0)}` +
                    (donut ? `M${point(innerRadius, 0)}A${innerRadius},${innerRadius} 0 1 0 ${point(innerRadius, Math.PI)}A${innerRadius},${innerRadius} 0 1 0 ${point(innerRadius, 0)}` : '') :
                    donut ?
                        `M${point(radius, angle)}A${radius},${radius} 0 ${large} 1 ${point(radius, end)}L${point(innerRadius, end)}A${innerRadius},${innerRadius} 0 ${large} 0 ${point(innerRadius, angle)}Z` :
                        `M${center},${center}L${point(radius, angle)}A${radius},${radius} 0 ${large} 1 ${point(radius, end)}Z`;

                parts.push(`<path d="${d}" fill="${color}" fill-rule="evenodd" class="acx-slice" data-tip="${this.escapeString(tip)}"/>`);

                angle = end;
            });

            if (donut) {
                parts.push(`<text x="${center}" y="${center + 6}" text-anchor="middle" class="acx-donut-total">${this.escapeString(this.compact(total))}</text>`);
            }

            return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img">${parts.join('')}</svg>`;
        }
    };
});
