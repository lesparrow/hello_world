import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Code, Group, Loader, Modal, Stack, Table, Text } from '@mantine/core';
import { IconAlertTriangle, IconCheck, IconRefresh, IconX } from '@tabler/icons-react';
import { call } from '../engine/client';
import type { EngineInfo, SelfCheck } from '../engine/types';
import { notifyError } from '../App';

/** « À propos et diagnostic » : versions et vérification réelle des bibliothèques incluses. */
export function DiagnosticModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const [info, setInfo] = useState<EngineInfo | null>(null);
  const [check, setCheck] = useState<SelfCheck | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true);
    try {
      setInfo(await call('engine.info', {}));
      setCheck(await call('engine.selfcheck', {}));
    } catch (err) { notifyError(err, 'Diagnostic impossible'); } finally { setBusy(false); }
  };
  useEffect(() => { if (opened && !check) void run(); }, [opened]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Modal opened={opened} onClose={onClose} title="À propos et diagnostic" size="lg" centered>
      <Stack gap="sm">
        {info && (
          <Text size="sm">
            STATPFE, moteur {info.version} (format de projet v{info.project_format_version}), Python {info.python},
            {' '}{info.platform}{info.frozen ? ' — version installée' : ' — version de développement'}.
            <br />Réglages de l'application : <Code>{info.config_dir}</Code>
          </Text>
        )}
        {busy && !check && <Group gap="xs"><Loader size="xs" /><Text size="sm">Vérification des bibliothèques incluses…</Text></Group>}
        {check && (
          <>
            <Alert variant="light" color={check.ok ? 'teal' : 'red'}
              icon={check.ok ? <IconCheck size={18} /> : <IconAlertTriangle size={18} />}>
              {check.ok ? 'Toutes les bibliothèques incluses fonctionnent.'
                : 'Une bibliothèque incluse ne fonctionne pas : réinstallez STATPFE ; si le problème persiste, transmettez ce diagnostic.'}
            </Alert>
            <Table fz="sm" verticalSpacing={4} withTableBorder>
              <Table.Thead>
                <Table.Tr><Table.Th>Élément</Table.Th><Table.Th>Version</Table.Th><Table.Th>Essai</Table.Th><Table.Th>État</Table.Th></Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {check.checks.map((c) => (
                  <Table.Tr key={c.key}>
                    <Table.Td>{c.label} <Text span size="xs" c="dimmed">({c.key})</Text></Table.Td>
                    <Table.Td>{c.version ?? '—'}</Table.Td>
                    <Table.Td><Text size="xs" style={{ wordBreak: 'break-all' }}>{c.detail}</Text></Table.Td>
                    <Table.Td>
                      {c.ok ? <Badge color="teal" variant="light" leftSection={<IconCheck size={12} />}>ok</Badge>
                        : <Badge color="red" variant="light" leftSection={<IconX size={12} />}>échec</Badge>}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </>
        )}
        <Group justify="flex-end">
          <Button variant="default" leftSection={<IconRefresh size={16} />} loading={busy} onClick={() => void run()}>Relancer</Button>
          <Button onClick={onClose}>Fermer</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
