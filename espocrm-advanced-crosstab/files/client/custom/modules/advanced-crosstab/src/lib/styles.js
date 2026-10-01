define('advanced-crosstab:lib/styles', [], function () {

    // Neutral translucent tones adapt to both light and dark Espo themes.
    const CSS = `
        .acx-designer { display: flex; gap: 12px; align-items: flex-start; }
        .acx-sidebar { flex: 0 0 300px; max-width: 300px; }
        .acx-main { flex: 1 1 auto; min-width: 0; }
        @media (max-width: 991px) { .acx-designer { flex-direction: column; } .acx-sidebar { max-width: none; width: 100%; flex-basis: auto; } }
        .acx-section { margin-bottom: 14px; }
        .acx-section-title { display: flex; justify-content: space-between; align-items: center; font-weight: 600;
            text-transform: uppercase; font-size: 11px; letter-spacing: .04em; opacity: .75; margin-bottom: 6px; }
        .acx-chips { list-style: none; margin: 0; padding: 0; }
        .acx-chip { display: flex; align-items: center; gap: 6px; padding: 4px 6px; margin-bottom: 4px; border-radius: 4px;
            background: rgba(127,127,127,.09); border: 1px solid rgba(127,127,127,.18); }
        .acx-chip-body { flex: 1 1 auto; min-width: 0; cursor: pointer; }
        .acx-chip-label { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .acx-chip-meta { display: block; font-size: 11px; opacity: .65; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: monospace; }
        .acx-chip-actions { flex: 0 0 auto; white-space: nowrap; }
        .acx-chip-actions a { opacity: .55; padding: 0 3px; }
        .acx-chip-actions a:hover { opacity: 1; }
        .acx-chip.acx-hidden-measure .acx-chip-label { text-decoration: line-through; opacity: .6; }
        .acx-empty-hint { font-size: 12px; opacity: .6; padding: 2px 0 4px; }
        .acx-toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
        .acx-toolbar .acx-info { margin-left: auto; font-size: 11px; opacity: .65; }
        .acx-name-input { font-size: 18px; font-weight: 600; border: 1px solid transparent; background: transparent; padding: 2px 6px;
            border-radius: 4px; min-width: 240px; max-width: 100%; color: inherit; }
        .acx-name-input:hover, .acx-name-input:focus { border-color: rgba(127,127,127,.35); outline: none; }
        .acx-dirty { font-size: 11px; opacity: .7; margin-left: 6px; }
        .acx-header { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-bottom: 12px; }
        .acx-header .acx-header-buttons { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }
        .acx-star.active { color: #eda100; }

        .acx-table-wrap { overflow: auto; max-height: 72vh; }
        table.acx-pivot { width: auto; min-width: 50%; margin-bottom: 0; font-variant-numeric: tabular-nums; }
        table.acx-pivot th, table.acx-pivot td { white-space: nowrap; vertical-align: middle; }
        table.acx-pivot thead th { position: sticky; top: 0; z-index: 2; text-align: center; background-clip: padding-box; }
        table.acx-pivot thead th, table.acx-pivot .acx-corner { background-color: var(--panel-heading-bg, #f5f6f8); }
        table.acx-pivot .acx-corner { position: sticky; left: 0; z-index: 3; text-align: left; vertical-align: bottom; }
        table.acx-pivot tbody th.acx-row-header { position: sticky; left: 0; z-index: 1; font-weight: normal; text-align: left;
            background-color: var(--panel-bg, #fff); }
        table.acx-pivot .acx-num { text-align: right; }
        table.acx-pivot tr.acx-parent > th, table.acx-pivot tr.acx-parent > td { font-weight: 600; }
        table.acx-pivot tr.acx-grand-row > th, table.acx-pivot tr.acx-grand-row > td { font-weight: 700; border-top: 2px solid rgba(127,127,127,.5); }
        table.acx-pivot td.acx-total-cell { background-color: rgba(127,127,127,.07); font-weight: 600; }
        table.acx-pivot td.acx-drill { cursor: pointer; }
        table.acx-pivot td.acx-drill:hover { text-decoration: underline; background-color: rgba(42,120,214,.12); }
        table.acx-pivot td.acx-up { color: #1b8a3a; }
        table.acx-pivot td.acx-down { color: #c4302b; }
        table.acx-pivot .acx-measure-header { cursor: pointer; font-weight: 600; }
        .acx-toggle { opacity: .7; margin-right: 2px; }
        .acx-toggle-spacer { display: inline-block; width: 16px; }
        .acx-rank { font-size: 10px; font-weight: normal; opacity: .8; }
        .acx-alert { padding: 6px 10px; margin-bottom: 8px; }
        .acx-empty { padding: 30px; text-align: center; }

        .acx-chart { position: relative; --acx-muted: #9a9890; --acx-ink-2: currentColor; }
        .acx-chart-title { font-weight: 600; margin-bottom: 4px; }
        .acx-chart-legend { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; margin-bottom: 6px; }
        .acx-legend-item { display: inline-flex; align-items: center; gap: 5px; }
        .acx-legend-swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: middle; }
        .acx-chart-plot svg { display: block; max-width: 100%; overflow: visible; }
        .acx-grid { stroke: rgba(127,127,127,.18); stroke-width: 1; }
        .acx-grid.acx-zero, .acx-baseline { stroke: rgba(127,127,127,.6); stroke-width: 1; }
        .acx-axis-text { fill: currentColor; opacity: .7; font-size: 11px; }
        .acx-point { stroke: var(--panel-bg, #fff); stroke-width: 2; }
        .acx-slice { stroke: var(--panel-bg, #fff); stroke-width: 2; }
        .acx-donut-total { fill: currentColor; font-size: 18px; font-weight: 600; }
        .acx-chart-plot [data-tip]:hover { opacity: .85; }
        .acx-chart-tooltip { position: absolute; z-index: 10; pointer-events: none; padding: 6px 9px; border-radius: 4px; font-size: 12px;
            background: rgba(20,20,20,.92); color: #fff; box-shadow: 0 2px 8px rgba(0,0,0,.25); max-width: 280px; }

        .acx-kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 10px; }
        .acx-kpi { padding: 12px 14px; border-radius: 6px; border: 1px solid rgba(127,127,127,.22); background: rgba(127,127,127,.05); }
        .acx-kpi.acx-clickable { cursor: pointer; }
        .acx-kpi.acx-clickable:hover { border-color: rgba(42,120,214,.6); }
        .acx-kpi-label { font-size: 12px; opacity: .7; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .acx-kpi-value { font-size: 26px; font-weight: 600; line-height: 1.25; font-variant-numeric: tabular-nums; }

        .acx-tree-box { border: 1px solid rgba(127,127,127,.25); border-radius: 4px; padding: 6px; max-height: 340px; overflow: auto; }
        .acx-tree-box-tall { max-height: 60vh; }
        .acx-tree-search { margin-bottom: 6px; }
        .acx-tree-list { list-style: none; margin: 0; padding-left: 0; }
        .acx-tree-list .acx-tree-list { padding-left: 16px; border-left: 1px dotted rgba(127,127,127,.35); margin-left: 6px; }
        .acx-tree-list li > a { display: block; padding: 2px 4px; border-radius: 3px; cursor: pointer; color: inherit; text-decoration: none; }
        .acx-tree-list li > a:hover { background: rgba(42,120,214,.12); }
        .acx-type-icon { width: 16px; text-align: center; }
        .acx-caret { width: 10px; }
        .acx-selected-path { margin-bottom: 6px; min-height: 22px; }
        .acx-source-switch { margin-bottom: 12px; }
        .acx-mt { margin-top: 4px; }

        .acx-formula-input { font-family: SFMono-Regular, Consolas, monospace; font-size: 13px; }
        .acx-formula-toolbar { display: flex; flex-wrap: wrap; gap: 6px; margin: 6px 0; }
        .acx-formula-toolbar .dropdown-menu { max-height: 300px; overflow: auto; }
        .acx-formula-status { min-height: 18px; }
        .acx-formula-help { margin-top: 4px; }
        .acx-formula-side .acx-tree-box { max-height: 260px; }
        .acx-side-title { margin-bottom: 4px; }

        .acx-filter-group { border-left: 3px solid rgba(42,120,214,.45); padding-left: 6px; margin-bottom: 4px; }
        .acx-filter-root { border-left-color: transparent; padding-left: 0; }
        .acx-filter-group-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
        .acx-inline-select { width: auto; display: inline-block; height: 26px; padding: 2px 6px; }
        .acx-filter-items { list-style: none; margin: 0; padding: 0; }
        .acx-filter-item { padding: 5px 6px; margin-bottom: 4px; border-radius: 4px; background: rgba(127,127,127,.07); }
        .acx-filter-item.has-error { outline: 1px solid rgba(220,50,50,.6); }
        .acx-filter-item select, .acx-filter-item input, .acx-filter-item textarea { margin-top: 3px; }
        .acx-filter-item-header { font-size: 12px; }
        .acx-filter-field { font-weight: 600; }
        .acx-filter-formula { font-family: SFMono-Regular, Consolas, monospace; font-size: 12px; }
        .acx-filter-records .label { display: inline-block; margin: 2px 2px 0 0; }
        .acx-filter-records .label a { color: inherit; margin-left: 3px; }
        .acx-drill-summary { margin-bottom: 8px; }
        .acx-dashlet-body { overflow: auto; height: 100%; }
        .acx-dashlet-body .acx-table-wrap { max-height: none; }
    `;

    let injected = false;

    return {
        ensure() {
            if (injected) {
                return;
            }

            const style = document.createElement('style');

            style.id = 'advanced-crosstab-styles';
            style.textContent = CSS;
            document.head.appendChild(style);
            injected = true;
        },
    };
});
