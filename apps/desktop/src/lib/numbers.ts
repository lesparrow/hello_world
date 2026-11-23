const nf = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 6 });
const pf = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 1 });
const intf = new Intl.NumberFormat('fr-FR');

/** Affichage d'une cellule : nombres au format français, sans arrondi trompeur. */
export function formatCell(v: string | number | null): string {
  if (v === null) return '';
  if (typeof v === 'number') return nf.format(v);
  return v;
}
export const formatPercent = (x: number) => pf.format(x);
export const formatInt = (x: number) => intf.format(x);
