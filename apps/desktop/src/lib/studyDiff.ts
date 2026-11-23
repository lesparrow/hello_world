import type { Study } from '../engine/types';

/** Champs du brouillon qui diffèrent de l'étude enregistrée dans le moteur. */
export function studyChanges(saved: Study, draft: Study): Partial<Study> {
  const changes: Partial<Study> = {};
  (Object.keys(saved) as (keyof Study)[]).forEach((key) => {
    const a = saved[key];
    const b = draft[key];
    const same = Array.isArray(a) && Array.isArray(b)
      ? a.length === b.length && a.every((v, i) => v === b[i])
      : a === b;
    if (!same) (changes as Record<string, unknown>)[key] = b;
  });
  return changes;
}
