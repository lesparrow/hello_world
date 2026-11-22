import { Paper, Text } from '@mantine/core';
import type { BoxSeries, Chart } from '../../engine/types';
import { fixed, niceTicks, tickLabel } from '../../lib/stats';

// Graphiques en SVG : ils ne dessinent que des valeurs calculées par le moteur
// (classes d'histogramme, quartiles, effectifs, points), sans recalcul côté interface.

const W = 560;
const H = 300;
const M = { top: 16, right: 16, bottom: 48, left: 56 };
const INK = '#3155a3';
const INK_LIGHT = '#b6c6ea';
const AXIS = '#868e96';
const GRID = '#e9ecef';
const PALETTE = ['#3155a3', '#e8590c', '#2b8a3e', '#ae3ec9', '#1098ad', '#f08c00', '#c2255c', '#5c940d'];

type Scale = (v: number) => number;
const linear = (d0: number, d1: number, r0: number, r1: number): Scale =>
  (v) => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0));

export function ChartView({ chart }: { chart: Chart }) {
  return (
    <Paper withBorder p="sm">
      <Text size="sm" fw={600} mb={4}>{chart.title}</Text>
      {chart.type === 'histogram' && <Histogram {...chart.data} title={chart.title} />}
      {chart.type === 'boxplot' && <BoxPlot series={chart.data.series} unit={chart.data.unit} title={chart.title} />}
      {chart.type === 'bar' && <Bars bars={chart.data.bars} title={chart.title} />}
      {chart.type === 'stacked' && <Stacked {...chart.data} title={chart.title} />}
      {chart.type === 'scatter' && <Scatter {...chart.data} title={chart.title} />}
    </Paper>
  );
}

function Frame({ title, children, height = H }: { title: string; children: React.ReactNode; height?: number }) {
  return (
    <svg viewBox={`0 0 ${W} ${height}`} width="100%" role="img" aria-label={title}
      style={{ display: 'block', fontFamily: 'inherit', maxHeight: height + 40 }}>
      <title>{title}</title>
      {children}
    </svg>
  );
}

function YAxis({ ticks, y, label }: { ticks: number[]; y: Scale; label?: string }) {
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke={GRID} />
          <text x={M.left - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize={11} fill={AXIS}>{tickLabel(t)}</text>
        </g>
      ))}
      {label && (
        <text transform={`translate(14 ${(M.top + H - M.bottom) / 2}) rotate(-90)`} textAnchor="middle"
          fontSize={11} fill={AXIS}>{label}</text>
      )}
    </g>
  );
}

function XTicks({ ticks, x, height = H, label }: { ticks: number[]; x: Scale; height?: number; label?: string }) {
  return (
    <g>
      <line x1={M.left} x2={W - M.right} y1={height - M.bottom} y2={height - M.bottom} stroke={AXIS} />
      {ticks.map((t) => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={height - M.bottom} y2={height - M.bottom + 4} stroke={AXIS} />
          <text x={x(t)} y={height - M.bottom + 16} textAnchor="middle" fontSize={11} fill={AXIS}>{tickLabel(t)}</text>
        </g>
      ))}
      {label && <text x={(M.left + W - M.right) / 2} y={height - 8} textAnchor="middle" fontSize={11} fill={AXIS}>{label}</text>}
    </g>
  );
}

function Histogram({ edges, counts, variable, unit, title }: {
  edges: number[]; counts: number[]; variable: string; unit: string; title: string;
}) {
  const maxC = Math.max(1, ...counts);
  const x = linear(edges[0], edges[edges.length - 1], M.left, W - M.right);
  const yTicks = niceTicks(0, maxC, 4).filter((t) => Number.isInteger(t));
  const y = linear(0, Math.max(maxC, yTicks[yTicks.length - 1] ?? maxC), H - M.bottom, M.top);
  return (
    <Frame title={title}>
      <YAxis ticks={yTicks} y={y} label="Effectif" />
      {counts.map((c, i) => (
        <rect key={i} x={x(edges[i]) + 0.5} width={Math.max(0, x(edges[i + 1]) - x(edges[i]) - 1)}
          y={y(c)} height={y(0) - y(c)} fill={INK} fillOpacity={0.85}>
          <title>{`[${fixed(edges[i], 2)} ; ${fixed(edges[i + 1], 2)}${i === counts.length - 1 ? ']' : '['} : ${c}`}</title>
        </rect>
      ))}
      <XTicks ticks={niceTicks(edges[0], edges[edges.length - 1], 6)} x={x} label={unit ? `${variable} (${unit})` : variable} />
    </Frame>
  );
}

function BoxPlot({ series, unit, title }: { series: BoxSeries[]; unit: string; title: string }) {
  const values = series.flatMap((s) => [s.whisker_low, s.whisker_high, ...s.outliers]);
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const ticks = niceTicks(lo, hi, 5);
  const y = linear(Math.min(lo, ticks[0] ?? lo), Math.max(hi, ticks[ticks.length - 1] ?? hi), H - M.bottom, M.top);
  const band = (W - M.left - M.right) / series.length;
  const boxW = Math.min(70, band * 0.5);
  return (
    <Frame title={title}>
      <YAxis ticks={ticks} y={y} label={unit || undefined} />
      <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} stroke={AXIS} />
      {series.map((s, i) => {
        const cx = M.left + band * (i + 0.5);
        const color = PALETTE[i % PALETTE.length];
        return (
          <g key={i}>
            <title>{`${s.label} (n = ${s.n}) : médiane ${fixed(s.median)}, Q1 ${fixed(s.q1)}, Q3 ${fixed(s.q3)}, moyenne ${fixed(s.mean)}`}</title>
            <line x1={cx} x2={cx} y1={y(s.whisker_low)} y2={y(s.q1)} stroke={color} />
            <line x1={cx} x2={cx} y1={y(s.q3)} y2={y(s.whisker_high)} stroke={color} />
            <line x1={cx - boxW / 4} x2={cx + boxW / 4} y1={y(s.whisker_low)} y2={y(s.whisker_low)} stroke={color} />
            <line x1={cx - boxW / 4} x2={cx + boxW / 4} y1={y(s.whisker_high)} y2={y(s.whisker_high)} stroke={color} />
            <rect x={cx - boxW / 2} width={boxW} y={y(s.q3)} height={Math.max(1, y(s.q1) - y(s.q3))}
              fill={color} fillOpacity={0.18} stroke={color} />
            <line x1={cx - boxW / 2} x2={cx + boxW / 2} y1={y(s.median)} y2={y(s.median)} stroke={color} strokeWidth={2.5} />
            <path d={`M ${cx - 4} ${y(s.mean)} l 4 -4 l 4 4 l -4 4 z`} fill="#fff" stroke={color} />
            {s.outliers.map((o, j) => (
              <circle key={j} cx={cx + ((j % 5) - 2) * 2} cy={y(o)} r={3} fill="none" stroke={color}>
                <title>{fixed(o, 3)}</title>
              </circle>
            ))}
            <text x={cx} y={H - M.bottom + 16} textAnchor="middle" fontSize={11} fill="#495057">
              {truncate(s.label, Math.max(6, Math.floor(band / 7)))}
            </text>
            <text x={cx} y={H - M.bottom + 30} textAnchor="middle" fontSize={10} fill={AXIS}>n = {s.n}</text>
          </g>
        );
      })}
    </Frame>
  );
}

function Bars({ bars, title }: { bars: { label: string; count: number; percent: number }[]; title: string }) {
  const maxC = Math.max(1, ...bars.map((b) => b.count));
  const ticks = niceTicks(0, maxC, 4).filter((t) => Number.isInteger(t));
  const y = linear(0, Math.max(maxC, ticks[ticks.length - 1] ?? maxC), H - M.bottom, M.top);
  const band = (W - M.left - M.right) / Math.max(1, bars.length);
  return (
    <Frame title={title}>
      <YAxis ticks={ticks} y={y} label="Effectif" />
      <line x1={M.left} x2={W - M.right} y1={H - M.bottom} y2={H - M.bottom} stroke={AXIS} />
      {bars.map((b, i) => {
        const x0 = M.left + band * i + band * 0.15;
        return (
          <g key={i}>
            <rect x={x0} width={band * 0.7} y={y(b.count)} height={y(0) - y(b.count)} fill={INK} fillOpacity={0.85}>
              <title>{`${b.label} : ${b.count} (${fixed(b.percent * 100, 1)} %)`}</title>
            </rect>
            <text x={x0 + band * 0.35} y={y(b.count) - 4} textAnchor="middle" fontSize={10} fill="#495057">
              {fixed(b.percent * 100, 0)} %
            </text>
            <text x={x0 + band * 0.35} y={H - M.bottom + 16} textAnchor="middle" fontSize={11} fill="#495057">
              {truncate(b.label, Math.max(4, Math.floor(band / 7)))}
            </text>
          </g>
        );
      })}
    </Frame>
  );
}

function Stacked({ rows, columns, percent, counts, title }: {
  rows: string[]; columns: string[]; percent: number[][]; counts: number[][]; title: string;
}) {
  const height = Math.max(140, 40 + rows.length * 34 + 40);
  const left = 120;
  const x = linear(0, 1, left, W - M.right);
  return (
    <Frame title={title} height={height}>
      {rows.map((r, i) => {
        let acc = 0;
        const yy = 12 + i * 34;
        return (
          <g key={i}>
            <text x={left - 8} y={yy + 12} dy="0.32em" textAnchor="end" fontSize={11} fill="#495057">{truncate(r, 18)}</text>
            {percent[i].map((p, j) => {
              const x0 = x(acc);
              acc += p;
              return (
                <rect key={j} x={x0} width={Math.max(0, x(acc) - x0)} y={yy} height={24}
                  fill={PALETTE[j % PALETTE.length]} fillOpacity={0.85}>
                  <title>{`${r} · ${columns[j]} : ${counts[i][j]} (${fixed(p * 100, 1)} %)`}</title>
                </rect>
              );
            })}
          </g>
        );
      })}
      {[0, 0.25, 0.5, 0.75, 1].map((t) => (
        <text key={t} x={x(t)} y={12 + rows.length * 34 + 8} textAnchor="middle" fontSize={10} fill={AXIS}>
          {fixed(t * 100, 0)} %
        </text>
      ))}
      <g transform={`translate(${left} ${height - 16})`}>
        {columns.map((c, j) => (
          <g key={j} transform={`translate(${j * 110} 0)`}>
            <rect width={10} height={10} y={-9} fill={PALETTE[j % PALETTE.length]} />
            <text x={14} fontSize={11} fill="#495057">{truncate(c, 14)}</text>
          </g>
        ))}
      </g>
    </Frame>
  );
}

function Scatter({ points, x_label, y_label, n, truncated, title }: {
  points: [number, number][]; x_label: string; y_label: string; n: number; truncated: boolean; title: string;
}) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const xt = niceTicks(Math.min(...xs), Math.max(...xs), 6);
  const yt = niceTicks(Math.min(...ys), Math.max(...ys), 5);
  const x = linear(Math.min(...xs, xt[0]), Math.max(...xs, xt[xt.length - 1]), M.left, W - M.right);
  const y = linear(Math.min(...ys, yt[0]), Math.max(...ys, yt[yt.length - 1]), H - M.bottom, M.top);
  return (
    <>
      <Frame title={title}>
        <YAxis ticks={yt} y={y} label={y_label} />
        {points.map((p, i) => (
          <circle key={i} cx={x(p[0])} cy={y(p[1])} r={3} fill={INK} fillOpacity={0.45} stroke={INK_LIGHT} />
        ))}
        <XTicks ticks={xt} x={x} label={x_label} />
      </Frame>
      {truncated && <Text size="xs" c="dimmed">Affichage des {points.length} premiers points sur {n}.</Text>}
    </>
  );
}

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}
