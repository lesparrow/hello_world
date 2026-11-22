import { useEffect, useMemo, useState } from 'react';
import {
  Button, Group, Modal, MultiSelect, SegmentedControl, Select, Stack, Table, Text, TextInput,
} from '@mantine/core';
import type { Step, Variable } from '../../engine/types';

export type StepKind = 'remove_duplicates' | 'filter_rows' | 'drop_missing' | 'recode' | 'compute';

export const STEP_HELP: Record<StepKind, string> = {
  remove_duplicates: 'Supprime les lignes identiques (garde la première). Vous pouvez comparer seulement certaines variables, par exemple un identifiant de répondant.',
  filter_rows: 'Garde uniquement les lignes qui respectent une condition (ex. Âge ≥ 18). Les autres sont exclues de cette version, pas supprimées du fichier.',
  drop_missing: 'Exclut les lignes où au moins une des variables choisies est manquante (analyse des cas complets).',
  recode: 'Crée une nouvelle variable en recodant ou regroupant les modalités d\'une variable existante (ex. 1-2 → « Pas satisfait »).',
  compute: 'Crée une nouvelle variable numérique à partir d\'une autre (logarithme, score z, normalisation).',
};

const OPERATORS = [
  { value: 'eq', label: '=' }, { value: 'ne', label: '≠' }, { value: 'lt', label: '<' }, { value: 'le', label: '≤' },
  { value: 'gt', label: '>' }, { value: 'ge', label: '≥' }, { value: 'in', label: 'parmi' },
  { value: 'not_in', label: 'hors de' }, { value: 'missing', label: 'est manquant' },
  { value: 'not_missing', label: "n'est pas manquant" },
];
const FUNCTIONS = [
  { value: 'log', label: 'Logarithme népérien (ln)' }, { value: 'log10', label: 'Logarithme décimal (log10)' },
  { value: 'zscore', label: 'Standardisation (score z)' }, { value: 'minmax', label: 'Normalisation entre 0 et 1' },
];

interface Props {
  kind: StepKind | null;
  title: string;
  variables: Variable[];
  onClose: () => void;
  onSubmit: (step: Step) => Promise<boolean>;
}

export function StepModal({ kind, title, variables, onClose, onSubmit }: Props) {
  const [variable, setVariable] = useState<string | null>(null);
  const [vars, setVars] = useState<string[]>([]);
  const [operator, setOperator] = useState('eq');
  const [value, setValue] = useState('');
  const [values, setValues] = useState<string[]>([]);
  const [fn, setFn] = useState('zscore');
  const [newName, setNewName] = useState('');
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setVariable(null); setVars([]); setOperator('eq'); setValue(''); setValues([]); setFn('zscore');
    setNewName(''); setMapping({});
  }, [kind]);

  const selected = variables.find((v) => v.key === variable);
  const options = (filter?: (v: Variable) => boolean) =>
    variables.filter(filter ?? (() => true)).map((v) => ({ value: v.key, label: v.name }));
  const categoryValues = useMemo(() => selected?.categories.map((c) => c.value) ?? [], [selected]);

  useEffect(() => {
    if (!selected) return;
    if (kind === 'recode') {
      setMapping(Object.fromEntries(categoryValues.map((c) => [c, c])));
      setNewName(`${selected.name}_recode`);
    }
    if (kind === 'compute') setNewName(`${selected.name}_${fn}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variable, kind]);

  useEffect(() => {
    if (kind === 'compute' && selected) setNewName(`${selected.name}_${fn}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fn]);

  const build = (): Step | null => {
    switch (kind) {
      case 'remove_duplicates': return { op: kind, variables: vars };
      case 'drop_missing': return vars.length ? { op: kind, variables: vars } : null;
      case 'filter_rows':
        if (!variable) return null;
        if (operator === 'missing' || operator === 'not_missing') return { op: kind, variable, operator };
        if (operator === 'in' || operator === 'not_in') return values.length ? { op: kind, variable, operator, values } : null;
        return value.trim() ? { op: kind, variable, operator, value: value.trim() } : null;
      case 'recode': {
        if (!variable || !newName.trim()) return null;
        const changed = Object.fromEntries(Object.entries(mapping).filter(([k, v]) => k !== v));
        return Object.keys(changed).length ? { op: kind, variable, new_name: newName.trim(), mapping: changed } : null;
      }
      case 'compute': return variable && newName.trim() ? { op: kind, variable, function: fn, new_name: newName.trim() } : null;
      default: return null;
    }
  };
  const step = build();

  const submit = async () => {
    if (!step) return;
    setBusy(true);
    const ok = await onSubmit(step);
    setBusy(false);
    if (ok) onClose();
  };

  const numericOrdered = selected && (selected.type === 'numerique' || selected.type === 'date');

  return (
    <Modal opened={kind !== null} onClose={onClose} title={<Text fw={650}>{title}</Text>} size="lg" centered>
      {kind && (
        <Stack>
          <Text size="sm" c="dimmed">{STEP_HELP[kind]}</Text>

          {(kind === 'remove_duplicates' || kind === 'drop_missing') && (
            <MultiSelect searchable label={kind === 'remove_duplicates' ? 'Comparer sur (vide = toutes les variables)' : 'Variables'}
              data={options()} value={vars} onChange={setVars} />
          )}

          {kind === 'filter_rows' && (
            <>
              <Select searchable label="Variable" data={options()} value={variable} onChange={setVariable} />
              <SegmentedControl size="xs" value={operator} onChange={setOperator}
                data={OPERATORS.filter((o) => numericOrdered || !['lt', 'le', 'gt', 'ge'].includes(o.value))} />
              {(operator === 'in' || operator === 'not_in') ? (
                <MultiSelect label="Valeurs" data={categoryValues} value={values} onChange={setValues} searchable />
              ) : operator !== 'missing' && operator !== 'not_missing' ? (
                selected && categoryValues.length > 0 && selected.type !== 'numerique' ? (
                  <Select label="Valeur" data={categoryValues} value={value || null} onChange={(v) => setValue(v ?? '')} />
                ) : (
                  <TextInput label="Valeur" value={value} onChange={(e) => setValue(e.currentTarget.value)}
                    placeholder={selected?.type === 'date' ? 'AAAA-MM-JJ' : selected?.type === 'booleen' ? 'oui ou non' : ''} />
                )
              ) : null}
            </>
          )}

          {kind === 'recode' && (
            <>
              <Select searchable label="Variable à recoder" value={variable} onChange={setVariable}
                data={options((v) => v.categories.length > 0)} />
              {selected && (
                <Table fz="sm" withTableBorder>
                  <Table.Thead><Table.Tr><Table.Th>Valeur actuelle</Table.Th><Table.Th>Nouvelle valeur (vide = manquant)</Table.Th></Table.Tr></Table.Thead>
                  <Table.Tbody>
                    {categoryValues.map((c) => (
                      <Table.Tr key={c}>
                        <Table.Td>{c}{selected.categories.find((x) => x.value === c)?.label ? ` (${selected.categories.find((x) => x.value === c)?.label})` : ''}</Table.Td>
                        <Table.Td><TextInput size="xs" value={mapping[c] ?? ''}
                          onChange={(e) => { const v = e.currentTarget.value; setMapping((m) => ({ ...m, [c]: v })); }} /></Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
              <TextInput label="Nom de la nouvelle variable" value={newName} onChange={(e) => setNewName(e.currentTarget.value)} />
            </>
          )}

          {kind === 'compute' && (
            <>
              <Select searchable label="Variable numérique" value={variable} onChange={setVariable}
                data={options((v) => v.type === 'numerique')} />
              <Select label="Calcul" data={FUNCTIONS} value={fn} onChange={(v) => v && setFn(v)} allowDeselect={false} />
              <TextInput label="Nom de la nouvelle variable" value={newName} onChange={(e) => setNewName(e.currentTarget.value)} />
            </>
          )}

          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Annuler</Button>
            <Button onClick={submit} loading={busy} disabled={!step}>Ajouter l'étape</Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
