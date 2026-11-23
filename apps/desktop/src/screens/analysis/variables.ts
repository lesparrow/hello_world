import type { MethodVariable, Variable } from '../../engine/types';

/** Raison pour laquelle une variable ne peut pas être choisie (ou null). */
export function exclusionReason(v: Variable, kind: MethodVariable['kind']): string | null {
  if (v.role === 'identifiant') return 'identifiant';
  if (v.role === 'exclue') return 'exclue des analyses';
  if (v.potential_identifier) return 'identifiant potentiel';
  if (kind === 'quantitative' && v.type !== 'numerique') return 'non numérique';
  if (kind === 'qualitative' && v.type === 'date') return 'date';
  return null;
}
