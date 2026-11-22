import { describe, expect, it } from 'vitest';
import { fileName, suggestFileName, withProjectExtension } from './format';
import { studyChanges } from './studyDiff';
import type { Study } from '../engine/types';

describe('format', () => {
  it('extrait le nom de fichier sous Windows et Unix', () => {
    expect(fileName('C:\\Users\\a\\Documents\\etude.statpfe')).toBe('etude.statpfe');
    expect(fileName('/home/a/etude.statpfe')).toBe('etude.statpfe');
  });
  it("ajoute l'extension une seule fois", () => {
    expect(withProjectExtension('C:\\x\\etude')).toBe('C:\\x\\etude.statpfe');
    expect(withProjectExtension('/x/etude.STATPFE')).toBe('/x/etude.STATPFE');
  });
  it('propose un nom de fichier sans accents ni caractères spéciaux', () => {
    expect(suggestFileName('Étude : réussite & tutorat ')).toBe('etude-reussite-tutorat.statpfe');
    expect(suggestFileName('???')).toBe('projet.statpfe');
  });
});

describe('studyChanges', () => {
  const base: Study = {
    title: 'T',
    problem_statement: '',
    objectives: '',
    population: '',
    sampling_method: '',
    planned_sample_size: null,
    hypotheses: ['H1'],
  };
  it('ne renvoie rien sans modification', () => {
    expect(studyChanges(base, { ...base, hypotheses: ['H1'] })).toEqual({});
  });
  it('renvoie seulement les champs modifiés', () => {
    expect(studyChanges(base, { ...base, objectives: 'O', hypotheses: ['H1', 'H2'] })).toEqual({
      objectives: 'O',
      hypotheses: ['H1', 'H2'],
    });
  });
});
