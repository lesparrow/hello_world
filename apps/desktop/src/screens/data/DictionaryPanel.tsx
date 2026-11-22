import { useEffect, useState } from 'react';
import {
  ActionIcon, Badge, Button, Drawer, Group, ScrollArea, Select, Stack, Switch, Table, TagsInput, Text, TextInput,
  Tooltip,
} from '@mantine/core';
import { IconArrowDown, IconArrowUp, IconEyeOff, IconListDetails, IconSparkles } from '@tabler/icons-react';
import type { Category, Dataset, Variable } from '../../engine/types';

interface Props {
  dataset: Dataset;
  onChange: (key: string, changes: Partial<Variable>) => Promise<boolean>;
}

const LEVELS_BY_TYPE: Record<string, string[]> = {
  numerique: ['continu', 'ordinal', 'nominal'],
  texte: ['nominal', 'ordinal'],
  booleen: ['nominal'],
  date: ['continu'],
};

export function DictionaryPanel({ dataset, onChange }: Props) {
  const voc = dataset.vocabulary;
  const [editing, setEditing] = useState<Variable | null>(null);
  const quality = Object.fromEntries(dataset.quality.variables.map((q) => [q.key, q]));

  return (
    <>
      <Text size="sm" c="dimmed" mb="sm">
        Le dictionnaire décrit comment chaque colonne doit être comprise. Il s'applique à toutes les versions
        des données ; le fichier original n'est jamais modifié.
      </Text>
      <ScrollArea type="auto">
        <Table verticalSpacing={6} fz="sm" miw={1100}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Variable</Table.Th>
              <Table.Th w={140}>Type</Table.Th>
              <Table.Th w={190}>Niveau de mesure</Table.Th>
              <Table.Th w={190}>Rôle</Table.Th>
              <Table.Th w={220}>Codes « valeur manquante »</Table.Th>
              <Table.Th w={110}>Modalités</Table.Th>
              <Table.Th w={70} ta="center">Masquée</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {dataset.variables.map((v) => {
              const q = quality[v.key];
              return (
                <Table.Tr key={v.key}>
                  <Table.Td>
                    <NameCell variable={v} onCommit={(changes) => onChange(v.key, changes)} />
                    <Group gap={4} mt={4}>
                      {v.key !== v.name && <Text size="xs" c="dimmed">colonne « {v.key} »</Text>}
                      {v.type !== v.detected_type && (
                        <Tooltip label={`Type détecté automatiquement : ${voc.types[v.detected_type as keyof typeof voc.types]}`}>
                          <Badge size="xs" variant="outline" color="grape" leftSection={<IconSparkles size={10} />}>modifié</Badge>
                        </Tooltip>
                      )}
                      {q?.invalid > 0 && <Badge size="xs" color="red" variant="light">{q.invalid} invalide(s)</Badge>}
                      {q?.missing > 0 && <Badge size="xs" color="gray" variant="light">{q.missing} manquante(s)</Badge>}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Select size="xs" allowDeselect={false} value={v.type}
                      data={Object.entries(voc.types).map(([value, label]) => ({ value, label }))}
                      onChange={(t) => t && onChange(v.key, { type: t as Variable['type'] })} />
                  </Table.Td>
                  <Table.Td>
                    <Select size="xs" allowDeselect={false} value={v.level}
                      data={LEVELS_BY_TYPE[v.type].map((l) => ({ value: l, label: voc.levels[l as keyof typeof voc.levels] }))}
                      onChange={(l) => l && onChange(v.key, { level: l as Variable['level'] })} />
                  </Table.Td>
                  <Table.Td>
                    <Select size="xs" allowDeselect={false} value={v.role}
                      data={Object.entries(voc.roles).map(([value, label]) => ({ value, label }))}
                      onChange={(r) => r && onChange(v.key, { role: r as Variable['role'] })} />
                  </Table.Td>
                  <Table.Td>
                    <TagsInput size="xs" value={v.missing_codes} placeholder={v.missing_codes.length ? '' : 'ex. NSP, 99'}
                      onChange={(codes) => onChange(v.key, { missing_codes: codes })} clearable={false} />
                  </Table.Td>
                  <Table.Td>
                    <Button size="compact-xs" variant="light" leftSection={<IconListDetails size={14} />}
                      onClick={() => setEditing(v)} disabled={v.categories.length === 0 && v.level === 'continu'}>
                      {v.categories.length || '—'}
                    </Button>
                  </Table.Td>
                  <Table.Td ta="center">
                    <Tooltip label={v.identifier_reasons.join(' ') || 'Masquer cette colonne dans les aperçus'} multiline w={260}>
                      <Group justify="center" gap={4}>
                        {v.potential_identifier && <IconEyeOff size={14} color="var(--mantine-color-orange-6)" />}
                        <Switch size="xs" checked={v.potential_identifier}
                          onChange={(e) => onChange(v.key, { potential_identifier: e.currentTarget.checked })} />
                      </Group>
                    </Tooltip>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </ScrollArea>
      <CategoriesDrawer variable={editing} onClose={() => setEditing(null)}
        onSave={async (cats) => { if (editing && (await onChange(editing.key, { categories: cats }))) setEditing(null); }} />
    </>
  );
}

function NameCell({ variable, onCommit }: { variable: Variable; onCommit: (c: Partial<Variable>) => Promise<boolean> }) {
  const [name, setName] = useState(variable.name);
  const [label, setLabel] = useState(variable.label);
  useEffect(() => { setName(variable.name); setLabel(variable.label); }, [variable.name, variable.label]);
  return (
    <Stack gap={4}>
      <TextInput size="xs" fw={600} value={name} onChange={(e) => setName(e.currentTarget.value)} aria-label="Nom"
        onBlur={async () => { if (name !== variable.name && !(await onCommit({ name }))) setName(variable.name); }} />
      <TextInput size="xs" variant="filled" placeholder="Libellé (ex. Âge en années)" value={label} aria-label="Libellé"
        onChange={(e) => setLabel(e.currentTarget.value)}
        onBlur={() => label !== variable.label && onCommit({ label })} />
    </Stack>
  );
}

function CategoriesDrawer({ variable, onClose, onSave }: {
  variable: Variable | null; onClose: () => void; onSave: (c: Category[]) => void;
}) {
  const [cats, setCats] = useState<Category[]>([]);
  useEffect(() => setCats(variable?.categories ?? []), [variable]);
  const move = (i: number, d: number) => setCats((c) => {
    const next = [...c];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    return next;
  });
  return (
    <Drawer opened={variable !== null} onClose={onClose} position="right" size="md"
      title={<Text fw={650}>Modalités de « {variable?.name} »</Text>}>
      <Stack>
        <Text size="sm" c="dimmed">
          Donnez un libellé aux codes (ex. 1 = Pas du tout d'accord) et, pour une variable ordinale, rangez les
          modalités dans l'ordre.
        </Text>
        {cats.length === 0 && <Text size="sm">Aucune modalité détectée pour cette variable.</Text>}
        {cats.map((c, i) => (
          <Group key={c.value} wrap="nowrap" gap="xs">
            <Badge variant="light" w={90} style={{ flexShrink: 0 }}>{c.value}</Badge>
            <TextInput style={{ flex: 1 }} size="xs" placeholder="Libellé" value={c.label}
              onChange={(e) => { const label = e.currentTarget.value; setCats((all) => all.map((x, j) => (j === i ? { ...x, label } : x))); }} />
            <ActionIcon variant="subtle" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Monter"><IconArrowUp size={14} /></ActionIcon>
            <ActionIcon variant="subtle" disabled={i === cats.length - 1} onClick={() => move(i, 1)} aria-label="Descendre"><IconArrowDown size={14} /></ActionIcon>
          </Group>
        ))}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Annuler</Button>
          <Button onClick={() => onSave(cats)} disabled={cats.length === 0}>Enregistrer les modalités</Button>
        </Group>
      </Stack>
    </Drawer>
  );
}
