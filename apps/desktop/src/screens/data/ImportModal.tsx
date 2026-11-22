import { useEffect, useState } from 'react';
import {
  Alert, Badge, Button, Group, Loader, Modal, ScrollArea, Select, SimpleGrid, Stack, Switch,
  Table, Text, TextInput,
} from '@mantine/core';
import { IconAlertTriangle, IconEyeOff, IconFileImport } from '@tabler/icons-react';
import { call, errorMessage } from '../../engine/client';
import type { InspectResult, ProjectState, ReadOptions } from '../../engine/types';
import { fileName } from '../../lib/format';
import { formatInt } from '../../lib/numbers';
import { notifyError } from '../../App';

interface Props {
  path: string | null;
  onClose: () => void;
  onImported: (datasetId: number, project: ProjectState) => void;
}

const ENCODINGS = [
  { value: 'utf-8', label: 'UTF-8 (recommandé)' },
  { value: 'cp1252', label: 'Windows (cp1252)' },
  { value: 'latin-1', label: 'Latin-1 (ISO-8859-1)' },
];
const DELIMITERS = [
  { value: ';', label: 'Point-virgule ( ; )' },
  { value: ',', label: 'Virgule ( , )' },
  { value: '\t', label: 'Tabulation' },
  { value: '|', label: 'Barre verticale ( | )' },
];

export function ImportModal({ path, onClose, onImported }: Props) {
  const [options, setOptions] = useState<Partial<ReadOptions>>({});
  const [info, setInfo] = useState<InspectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setOptions({});
    setInfo(null);
    setError(null);
    if (path) setName(fileName(path).replace(/\.[^.]+$/, ''));
  }, [path]);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    setError(null);
    call('data.inspect_file', { path, options })
      .then((r) => !cancelled && setInfo(r))
      .catch((err) => { if (!cancelled) { setInfo(null); setError(errorMessage(err)); } });
    return () => { cancelled = true; };
  }, [path, options]);

  const doImport = async () => {
    if (!path || !info) return;
    setBusy(true);
    try {
      const r = await call('data.import', { path, options: info.options, name });
      onImported(r.dataset_id, r.project);
    } catch (err) {
      notifyError(err, "Échec de l'import");
    } finally {
      setBusy(false);
    }
  };

  const set = (patch: Partial<ReadOptions>) => setOptions((o) => ({ ...o, ...(info?.options ?? {}), ...patch }));

  return (
    <Modal opened={path !== null} onClose={onClose} size="xl" centered closeOnClickOutside={false}
      title={<Group gap="xs"><IconFileImport size={20} /><Text fw={650} fz="lg">Importer des données</Text></Group>}>
      {!info && !error && <Group><Loader size="sm" /><Text size="sm">Lecture du fichier…</Text></Group>}
      {error && (
        <Alert color="red" icon={<IconAlertTriangle />} title="Fichier illisible" mb="md">{error}</Alert>
      )}
      {(info || error) && (
        <Stack>
          {info && (
            <Text size="sm" c="dimmed">
              {info.file_name} · {formatInt(info.rows)} lignes · {info.columns.length} colonnes.
              Le fichier original ne sera jamais modifié : une copie exacte est conservée dans le projet.
            </Text>
          )}
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            {(info?.kind ?? (path?.match(/\.xlsx?m?$/i) ? 'excel' : 'csv')) === 'csv' ? (
              <>
                <Select label="Encodage" data={ENCODINGS} allowDeselect={false}
                  value={info?.options.encoding ?? options.encoding ?? null}
                  onChange={(v) => v && set({ encoding: v })} />
                <Select label="Séparateur" data={DELIMITERS} allowDeselect={false}
                  value={info?.options.delimiter ?? options.delimiter ?? null}
                  onChange={(v) => v && set({ delimiter: v })} />
              </>
            ) : (
              <Select label="Feuille" data={info?.sheets ?? []} allowDeselect={false}
                value={info?.options.sheet ?? null} onChange={(v) => v && set({ sheet: v })} />
            )}
            <Switch mt={28} label="La première ligne contient les noms des variables"
              checked={info?.options.header ?? options.header ?? true}
              onChange={(e) => set({ header: e.currentTarget.checked })} />
          </SimpleGrid>

          {info?.notes.map((n) => (
            <Alert key={n} color="orange" variant="light" icon={<IconAlertTriangle size={18} />}>{n}</Alert>
          ))}

          {info && (
            <ScrollArea h={300} type="auto" style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 8 }}>
              <Table fz="xs" striped withColumnBorders stickyHeader>
                <Table.Thead>
                  <Table.Tr>
                    {info.columns.map((c) => (
                      <Table.Th key={c.key} style={{ whiteSpace: 'nowrap' }}>
                        <Stack gap={2}>
                          <Group gap={4} wrap="nowrap">
                            {c.potential_identifier && <IconEyeOff size={13} color="var(--mantine-color-orange-6)" />}
                            {c.key}
                          </Group>
                          <Badge size="xs" variant="light" color={c.type === 'texte' ? 'gray' : 'brand'}>{c.type_label}</Badge>
                        </Stack>
                      </Table.Th>
                    ))}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {info.preview.map((row, i) => (
                    <Table.Tr key={i}>
                      {row.map((v, j) => (
                        <Table.Td key={j} style={{ whiteSpace: 'nowrap' }}>
                          {v ?? <Text span size="xs" c="dimmed">—</Text>}
                        </Table.Td>
                      ))}
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </ScrollArea>
          )}
          {info && (
            <Text size="xs" c="dimmed">
              Types proposés automatiquement : vous pourrez les corriger dans le dictionnaire des variables.
              Les colonnes marquées <IconEyeOff size={12} /> semblent contenir des données personnelles et seront masquées.
            </Text>
          )}

          <TextInput label="Nom du jeu de données" value={name} onChange={(e) => setName(e.currentTarget.value)} maxLength={120} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>Annuler</Button>
            <Button onClick={doImport} loading={busy} disabled={!info || !name.trim()}>Importer</Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
