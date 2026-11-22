import { useEffect, useState } from 'react';
import {
  ActionIcon, Alert, Badge, Button, Center, Container, Grid, Group, Menu, Modal, NavLink, Paper, Stack, Tabs, Text,
  TextInput, ThemeIcon, Timeline, Title, Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle, IconArrowRight, IconCopy, IconDots, IconFilter, IconLock, IconPencil, IconPlus, IconTrash,
  IconTransform, IconVersions,
} from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { Dataset, ProjectState, QualityReport, Step } from '../../engine/types';
import { formatInt } from '../../lib/numbers';
import { notifyError } from '../../App';
import { DataTable } from './DataTable';
import { QualityPanel } from './QualityPanel';
import { StepModal, type StepKind } from './StepModal';

interface Props {
  dataset: Dataset | null;
  onResult: (r: { dataset: Dataset; project: ProjectState }) => void;
  onGoToData: () => void;
}

const STEP_KINDS: { kind: StepKind; label: string }[] = [
  { kind: 'remove_duplicates', label: 'Supprimer les doublons' },
  { kind: 'filter_rows', label: 'Filtrer les lignes' },
  { kind: 'drop_missing', label: 'Exclure les lignes incomplètes' },
  { kind: 'recode', label: 'Recoder / regrouper des modalités' },
  { kind: 'compute', label: 'Créer une variable calculée' },
];

export function PreparationPage({ dataset, onResult, onGoToData }: Props) {
  const [selected, setSelected] = useState<number | null>(null);
  const [stepKind, setStepKind] = useState<StepKind | null>(null);
  const [naming, setNaming] = useState<{ mode: 'create' | 'copy' | 'rename'; name: string } | null>(null);

  if (!dataset) {
    return (
      <Center h="60vh"><Stack align="center">
        <Text c="dimmed">Importez d'abord des données.</Text>
        <Button onClick={onGoToData}>Aller aux données</Button>
      </Stack></Center>
    );
  }

  const version = dataset.versions.find((v) => v.id === selected) ?? null;
  const act = async (fn: () => Promise<{ dataset: Dataset; project: ProjectState }>, title: string) => {
    try {
      const r = await fn();
      onResult(r);
      return r;
    } catch (err) {
      notifyError(err, title);
      return null;
    }
  };

  const submitName = async () => {
    if (!naming) return;
    const name = naming.name.trim();
    if (naming.mode === 'rename' && version) {
      await act(() => call('data.rename_version', { dataset_id: dataset.id, version_id: version.id, name }), 'Renommage impossible');
    } else {
      const r = await act(() => call('data.create_version', {
        dataset_id: dataset.id, name, from_version_id: naming.mode === 'copy' && version ? version.id : null,
      }), 'Création impossible') as ({ version_id: number } & object) | null;
      if (r) setSelected(r.version_id);
    }
    setNaming(null);
  };

  return (
    <Container size="xl" py="lg">
      <Group justify="space-between" mb="md">
        <div>
          <Title order={2}>Préparation des données</Title>
          <Text c="dimmed" size="sm">
            Chaque version applique des étapes à l'original, dans l'ordre. Retirer une étape annule son effet.
          </Text>
        </div>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setNaming({ mode: 'create', name: 'Version de travail' })}>
          Nouvelle version
        </Button>
      </Group>
      <Grid>
        <Grid.Col span={{ base: 12, md: 3 }}>
          <Paper withBorder p="xs">
            <NavLink active={selected === null} onClick={() => setSelected(null)} style={{ borderRadius: 8 }}
              label="Original" description={`${formatInt(dataset.original.rows)} lignes · lecture seule`}
              leftSection={<IconLock size={16} />} />
            {dataset.versions.map((v) => (
              <NavLink key={v.id} active={selected === v.id} onClick={() => setSelected(v.id)} style={{ borderRadius: 8 }}
                label={v.name} leftSection={<IconVersions size={16} />}
                description={v.error ? 'À corriger' : `${formatInt(v.rows ?? 0)} lignes · ${v.steps.length} étape(s)`}
                rightSection={v.error ? <IconAlertTriangle size={14} color="var(--mantine-color-red-6)" /> : null} />
            ))}
            {dataset.versions.length === 0 && (
              <Text size="xs" c="dimmed" p="sm">
                Créez une version de travail pour nettoyer ou transformer les données sans toucher à l'original.
              </Text>
            )}
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 9 }}>
          {version === null ? (
            <Stack>
              <Alert color="teal" variant="light" icon={<IconLock size={18} />} title="Données d'origine">
                Lecture seule. Empreinte : <code>{dataset.original.fingerprint.slice(0, 12)}</code>
              </Alert>
              <DataTable datasetId={dataset.id} versionId={null} revision={JSON.stringify(dataset.variables)} />
            </Stack>
          ) : (
            <Stack>
              <Paper withBorder p="md">
                <Group justify="space-between">
                  <div>
                    <Text fw={650} fz="lg">{version.name}</Text>
                    <Text size="sm" c="dimmed">
                      {version.error ? 'Cette version ne peut pas être calculée.' :
                        `${formatInt(version.rows ?? 0)} lignes · ${version.columns} variables · empreinte ${version.fingerprint?.slice(0, 12)}`}
                    </Text>
                  </div>
                  <Group gap="xs">
                    <Menu position="bottom-end">
                      <Menu.Target>
                        <Button leftSection={<IconPlus size={16} />} disabled={!!version.error}>Ajouter une étape</Button>
                      </Menu.Target>
                      <Menu.Dropdown>
                        {STEP_KINDS.map((s) => (
                          <Menu.Item key={s.kind} onClick={() => setStepKind(s.kind)}>{s.label}</Menu.Item>
                        ))}
                      </Menu.Dropdown>
                    </Menu>
                    <Menu position="bottom-end">
                      <Menu.Target><ActionIcon variant="default" size="lg" aria-label="Actions"><IconDots size={18} /></ActionIcon></Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item leftSection={<IconPencil size={16} />} onClick={() => setNaming({ mode: 'rename', name: version.name })}>Renommer</Menu.Item>
                        <Menu.Item leftSection={<IconCopy size={16} />} onClick={() => setNaming({ mode: 'copy', name: `Copie de ${version.name}` })}>Dupliquer</Menu.Item>
                        <Menu.Divider />
                        <Menu.Item color="red" leftSection={<IconTrash size={16} />}
                          onClick={async () => {
                            if (await act(() => call('data.delete_version', { dataset_id: dataset.id, version_id: version.id }), 'Suppression impossible')) setSelected(null);
                          }}>
                          Supprimer la version
                        </Menu.Item>
                      </Menu.Dropdown>
                    </Menu>
                  </Group>
                </Group>
                {version.error && <Alert mt="sm" color="red" icon={<IconAlertTriangle size={16} />}>{version.error}</Alert>}
              </Paper>

              <Paper withBorder p="md">
                <Text fw={600} mb="sm">Étapes</Text>
                {version.steps.length === 0 ? (
                  <Text size="sm" c="dimmed">Aucune étape : cette version est identique à l'original.</Text>
                ) : (
                  <Timeline bulletSize={26} lineWidth={2} active={version.steps.length}>
                    {version.steps.map((s) => (
                      <Timeline.Item key={s.index} bullet={<ThemeIcon size={26} radius="xl" variant="light" color={s.error ? 'red' : 'brand'}>
                        {s.op === 'filter_rows' ? <IconFilter size={14} /> : <IconTransform size={14} />}</ThemeIcon>}
                        title={
                          <Group justify="space-between" wrap="nowrap">
                            <Text size="sm" fw={600}>{s.index + 1}. {s.description}</Text>
                            <Tooltip label="Retirer cette étape">
                              <ActionIcon variant="subtle" color="gray" aria-label={`Retirer l'étape ${s.index + 1}`}
                                onClick={() => act(() => call('data.remove_step', { dataset_id: dataset.id, version_id: version.id, index: s.index }), "Impossible de retirer l'étape")}>
                                <IconTrash size={15} />
                              </ActionIcon>
                            </Tooltip>
                          </Group>
                        }>
                        <Group gap={6}>
                          <Badge size="sm" variant="light" color="gray">{formatInt(s.rows_before)} lignes</Badge>
                          <IconArrowRight size={12} />
                          <Badge size="sm" variant="light" color={s.rows_after !== null && s.rows_after < s.rows_before ? 'orange' : 'teal'}>
                            {s.rows_after === null ? '?' : `${formatInt(s.rows_after)} lignes`}
                          </Badge>
                        </Group>
                        {s.warnings.map((w) => <Text key={w} size="xs" c="orange.8" mt={4}>{w}</Text>)}
                        {s.error && <Text size="xs" c="red" mt={4}>{s.error}</Text>}
                      </Timeline.Item>
                    ))}
                  </Timeline>
                )}
              </Paper>

              {!version.error && (
                <Tabs defaultValue="donnees" keepMounted={false}>
                  <Tabs.List>
                    <Tabs.Tab value="donnees">Données de la version</Tabs.Tab>
                    <Tabs.Tab value="qualite">Qualité de la version</Tabs.Tab>
                  </Tabs.List>
                  <Tabs.Panel value="donnees" pt="md">
                    <DataTable datasetId={dataset.id} versionId={version.id}
                      revision={`${version.fingerprint}-${JSON.stringify(dataset.variables)}`} />
                  </Tabs.Panel>
                  <Tabs.Panel value="qualite" pt="md">
                    <VersionQuality datasetId={dataset.id} versionId={version.id} revision={version.fingerprint ?? ''} />
                  </Tabs.Panel>
                </Tabs>
              )}
            </Stack>
          )}
        </Grid.Col>
      </Grid>

      <StepModal kind={stepKind} title={STEP_KINDS.find((s) => s.kind === stepKind)?.label ?? ''}
        variables={version?.variables ?? []} onClose={() => setStepKind(null)}
        onSubmit={async (step: Step) => !!version && !!(await act(
          () => call('data.add_step', { dataset_id: dataset.id, version_id: version.id, step }), 'Étape refusée'))} />

      <Modal opened={naming !== null} onClose={() => setNaming(null)} centered
        title={<Text fw={650}>{naming?.mode === 'rename' ? 'Renommer la version' : naming?.mode === 'copy' ? 'Dupliquer la version' : 'Nouvelle version'}</Text>}>
        <TextInput data-autofocus label="Nom" value={naming?.name ?? ''} maxLength={120}
          onChange={(e) => { const name = e.currentTarget.value; setNaming((n) => (n ? { ...n, name } : n)); }}
          onKeyDown={(e) => e.key === 'Enter' && naming?.name.trim() && submitName()} />
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setNaming(null)}>Annuler</Button>
          <Button disabled={!naming?.name.trim()} onClick={submitName}>Valider</Button>
        </Group>
      </Modal>
    </Container>
  );
}

function VersionQuality({ datasetId, versionId, revision }: { datasetId: number; versionId: number; revision: string }) {
  const [report, setReport] = useState<QualityReport | null>(null);
  useEffect(() => {
    call('data.quality', { dataset_id: datasetId, version_id: versionId }).then(setReport).catch((e) => notifyError(e));
  }, [datasetId, versionId, revision]);
  return report ? <QualityPanel report={report} /> : null;
}
