import { describe, expect, it } from 'vitest';
import { formatCellOf, formatP, formatStat, niceTicks } from './stats';

const nb = (s: string) => s.replace(/ | /g, ' ');

describe('mise en forme des résultats', () => {
  it('formate les valeurs p', () => {
    expect(formatP(0.0004)).toBe('< 0,001');
    expect(formatP(0.0312)).toBe('0,031');
    expect(formatStat(0.5, 'p')).toBe('0,500');
  });
  it('formate statistiques, degrés de liberté et cellules', () => {
    expect(formatStat(29.51873, 'df')).toBe('29,52');
    expect(formatStat(37, 'df')).toBe('37');
    expect(formatStat(null, 'value')).toBe('non calculable');
    expect(formatStat('−∞', 'ci')).toBe('−∞');
    expect(nb(formatCellOf(1234.5678, 'num'))).toBe('1 234,568');
    expect(formatCellOf(0.256, 'pct')).toBe('25,6 %');
    expect(formatCellOf(null, 'num')).toBe('—');
  });
  it('produit des graduations rondes', () => {
    expect(niceTicks(0, 10, 5)).toEqual([0, 2, 4, 6, 8, 10]);
    const t = niceTicks(-1.3, 2.7, 4);
    expect(t[0]).toBeGreaterThanOrEqual(-1.3);
    expect(t[t.length - 1]).toBeLessThanOrEqual(2.7);
    expect(niceTicks(5, 5).length).toBeGreaterThan(0);
  });
});
