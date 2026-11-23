import type { CellKind, StatKind } from '../engine/types';

const cache = new Map<number, Intl.NumberFormat>();
function fmt(digits: number): Intl.NumberFormat {
  let f = cache.get(digits);
  if (!f) {
    f = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    cache.set(digits, f);
  }
  return f;
}

/** Nombre au format français avec un nombre fixe de décimales. */
export function fixed(x: number, digits = 2): string {
  return fmt(digits).format(x);
}

/** Valeur p : trois décimales, « < 0,001 » en dessous. */
export function formatP(p: number): string {
  return p < 0.001 ? '< 0,001' : fixed(p, 3);
}

/** Affichage d'une statistique de synthèse selon sa nature. */
export function formatStat(value: number | string | null, kind: StatKind, digits = 3): string {
  if (value === null) return 'non calculable';
  if (typeof value === 'string') return value;
  if (kind === 'p') return formatP(value);
  if (kind === 'df') return fixed(value, Number.isInteger(value) ? 0 : 2);
  return fixed(value, digits);
}

/** Cellule d'un tableau de résultats. */
export function formatCellOf(v: string | number | boolean | null, kind: CellKind | undefined): string {
  if (v === null) return '—';
  if (typeof v === 'boolean') return v ? 'oui' : 'non';
  if (typeof v === 'string') return v;
  switch (kind) {
    case 'int':
      return fixed(v, 0);
    case 'pct':
      return `${fixed(v * 100, 1)} %`;
    case 'text':
      return String(v);
    default:
      return Math.abs(v) >= 1e6 || (v !== 0 && Math.abs(v) < 1e-3) ? v.toExponential(3).replace('.', ',') : fixed(v, 3);
  }
}

/** Graduations « rondes » couvrant [lo, hi]. */
export function niceTicks(lo: number, hi: number, count = 5): number[] {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return [];
  if (lo === hi) {
    const d = Math.abs(lo) || 1;
    lo -= d / 2;
    hi += d / 2;
  }
  const span = hi - lo;
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) ?? 10 * mag;
  const start = Math.ceil(lo / step - 1e-9) * step;
  const out: number[] = [];
  for (let t = start; t <= hi + step * 1e-9; t += step) out.push(Math.abs(t) < step * 1e-9 ? 0 : t);
  return out;
}

/** Libellé court d'une graduation. */
export function tickLabel(t: number): string {
  const a = Math.abs(t);
  if (a !== 0 && (a >= 1e6 || a < 1e-3)) return t.toExponential(1).replace('.', ',');
  const digits = a >= 100 || Number.isInteger(t) ? 0 : a >= 1 ? 1 : 2;
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: digits + 1 }).format(t);
}
