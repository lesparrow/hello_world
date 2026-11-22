import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AppShell, Badge, Box, Button, Group, Kbd, Menu, Modal, NavLink, ScrollArea, Stack, Text,
  Timeline, Title, Tooltip,
} from '@mantine/core';
import { useHotkeys } from '@mantine/hooks';
import { notifications } from '@mantine/notifications';
import {
  IconBook2, IconChartBar, IconChevronDown, IconCopy, IconDatabase, IconDeviceFloppy,
  IconFileText, IconHistory, IconTransform, IconX,
} from '@tabler/icons-react';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { call, runningInTauri } from '../engine/client';
import type { Dataset, ProjectState, Study } from '../engine/types';
import { DataPage } from './data/DataPage';
import { PreparationPage } from './data/PreparationPage';
import { Logo } from '../components/Logo';
import { StudyPage } from './StudyPage';
import { studyChanges } from '../lib/studyDiff';
import { pickProjectDestination } from '../lib/files';
import { formatDateTime } from '../lib/format';
import { notifyError } from '../App';

interface Props {
  project: ProjectState;
  onChange: (p: ProjectState) => void;
  onClosed: () => void;
}

// Étapes du parcours. Celles qui ne sont pas encore développées sont affichées
// comme telles et ne sont pas cliquables.
const UPCOMING = [
  { label: 'Analyses', icon: IconChartBar, phase: 'Phase 4' },
  { label: 'Rapport', icon: IconFileText, phase: 'Phase 6' },
];

type Section = 'etude' | 'donnees' | 'preparation';

type PendingClose = 'project' | 'window' | null;

export function Workspace({ project, onChange, onClosed }: Props) {
  const [draft, setDraft] = useState<Study>(project.study);
  const [saving, setSaving] = useState(false);
  const [pendingClose, setPendingClose] = useState<PendingClose>(null);
  const [section, setSection] = useState<Section>('etude');
  const [datasetId, setDatasetId] = useState<number | null>(project.datasets[0]?.id ?? null);
  const [dataset, setDataset] = useState<Dataset | null>(null);

  // Charge le jeu de données sélectionné (le moteur recalcule dictionnaire, qualité et versions).
  useEffect(() => {
    if (datasetId === null) { setDataset(null); return; }
    let cancelled = false;
    call('data.get', { dataset_id: datasetId })
      .then((d) => !cancelled && setDataset(d))
      .catch((err) => !cancelled && notifyError(err, 'Impossible de charger les données'));
    return () => { cancelled = true; };
  }, [datasetId]);

  const applyDataResult = useCallback((r: { dataset: Dataset; project: ProjectState }) => {
    setDataset(r.dataset);
    onChange(r.project);
  }, [onChange]);
  const projectRef = useRef(project);
  projectRef.current = project;
  const draftRef = useRef(draft);
  draftRef.current = draft;

  const localChanges = studyChanges(project.study, draft);
  const hasLocalChanges = Object.keys(localChanges).length > 0;
  const dirty = project.dirty || hasLocalChanges;
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;

  /** Transmet au moteur les modifications du formulaire (validées par le moteur). */
  const flush = useCallback(async (): Promise<boolean> => {
    const changes = studyChanges(projectRef.current.study, draftRef.current);
    if (Object.keys(changes).length === 0) return true;
    try {
      onChange(await call('project.update_study', { changes }));
      return true;
    } catch (err) {
      notifyError(err, 'Modification refusée');
      return false;
    }
  }, [onChange]);

  const save = useCallback(async (): Promise<boolean> => {
    setSaving(true);
    try {
      if (!(await flush())) return false;
      onChange(await call('project.save'));
      notifications.show({ color: 'teal', message: 'Projet enregistré.', autoClose: 2000 });
      return true;
    } catch (err) {
      notifyError(err, "Échec de l'enregistrement");
      return false;
    } finally {
      setSaving(false);
    }
  }, [flush, onChange]);

  const saveAs = async () => {
    if (!(await flush())) return;
    const path = await pickProjectDestination(`copie-${project.file_name}`);
    if (!path) return;
    try {
      onChange(await call('project.save_as', { path, overwrite: runningInTauri() }));
      notifications.show({ color: 'teal', message: 'Copie enregistrée. Vous travaillez maintenant sur la copie.' });
    } catch (err) {
      notifyError(err, "Échec de l'enregistrement de la copie");
    }
  };

  const finishClose = async (target: PendingClose, discard: boolean) => {
    try {
      await call('project.close', { discard_changes: discard });
    } catch (err) {
      notifyError(err, 'Fermeture impossible');
      return;
    }
    setPendingClose(null);
    if (target === 'window') {
      await getCurrentWindow().destroy();
    } else {
      onClosed();
    }
  };

  const requestClose = (target: Exclude<PendingClose, null>) => {
    if (dirtyRef.current) setPendingClose(target);
    else void finishClose(target, false);
  };

  // Fermeture de la fenêtre : on ne perd jamais de modification sans confirmation.
  useEffect(() => {
    if (!runningInTauri()) return;
    const unlisten = getCurrentWindow().onCloseRequested((event) => {
      event.preventDefault();
      requestClose('window');
    });
    return () => {
      void unlisten.then((f) => f());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useHotkeys([['mod+S', () => void save()]], []);

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 240, breakpoint: 0 }}
      aside={{ width: 300, breakpoint: 'md', collapsed: { desktop: section !== 'etude', mobile: true } }} padding={0}>
      <AppShell.Header px="md">
        <Group h="100%" justify="space-between" wrap="nowrap">
          <Group gap="lg" wrap="nowrap" style={{ minWidth: 0 }}>
            <Logo />
            <Box style={{ minWidth: 0 }}>
              <Text fw={600} truncate maw={420}>{project.study.title}</Text>
              <Text size="xs" c="dimmed" truncate maw={420}>{project.path}</Text>
            </Box>
          </Group>
          <Group gap="xs" wrap="nowrap">
            {dirty ? (
              <Badge color="orange" variant="light">Modifications non enregistrées</Badge>
            ) : (
              <Badge color="teal" variant="light">Enregistré</Badge>
            )}
            <Tooltip label={<>Enregistrer <Kbd size="xs">Ctrl</Kbd> + <Kbd size="xs">S</Kbd></>}>
              <Button leftSection={<IconDeviceFloppy size={16} />} loading={saving} onClick={() => void save()}
                variant={dirty ? 'filled' : 'light'}>
                Enregistrer
              </Button>
            </Tooltip>
            <Menu position="bottom-end" withinPortal>
              <Menu.Target>
                <Button variant="default" rightSection={<IconChevronDown size={14} />}>Projet</Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<IconCopy size={16} />} onClick={saveAs}>Enregistrer une copie…</Menu.Item>
                <Menu.Divider />
                <Menu.Item leftSection={<IconX size={16} />} onClick={() => requestClose('project')}>
                  Fermer le projet
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="sm" py={6}>Parcours</Text>
        <NavLink active={section === 'etude'} label="Étude" description="Problématique, objectifs, hypothèses"
          leftSection={<IconBook2 size={18} />} variant="light" style={{ borderRadius: 8 }}
          onClick={() => { void flush(); setSection('etude'); }} />
        <NavLink active={section === 'donnees'} label="Données" description="Import, dictionnaire, qualité"
          leftSection={<IconDatabase size={18} />} variant="light" style={{ borderRadius: 8 }}
          rightSection={project.datasets.length ? <Badge size="xs" variant="light">{project.datasets.length}</Badge> : null}
          onClick={() => { void flush(); setSection('donnees'); }} />
        <NavLink active={section === 'preparation'} label="Préparation" description="Versions et transformations"
          leftSection={<IconTransform size={18} />} variant="light" style={{ borderRadius: 8 }}
          disabled={project.datasets.length === 0}
          onClick={() => { void flush(); setSection('preparation'); }} />
        {UPCOMING.map((s) => (
          <NavLink key={s.label} disabled label={s.label} leftSection={<s.icon size={18} />}
            rightSection={<Badge size="xs" variant="outline" color="gray">{s.phase}</Badge>}
            style={{ borderRadius: 8 }} />
        ))}
        <Text size="xs" c="dimmed" px="sm" mt="auto">
          Les étapes grisées sont en développement et seront activées dans les prochaines versions.
        </Text>
      </AppShell.Navbar>

      <AppShell.Main>
        <ScrollArea h="calc(100vh - 60px)">
          {section === 'etude' && <StudyPage draft={draft} onDraft={setDraft} onCommit={() => void flush()} />}
          {section === 'donnees' && (
            <DataPage project={project} dataset={dataset} onSelectDataset={setDatasetId} onResult={applyDataResult}
              onImported={(id, p) => { onChange(p); setDatasetId(id); if (id === datasetId) call('data.get', { dataset_id: id }).then(setDataset); }} />
          )}
          {section === 'preparation' && (
            <PreparationPage dataset={dataset} onResult={applyDataResult} onGoToData={() => setSection('donnees')} />
          )}
        </ScrollArea>
      </AppShell.Main>

      <AppShell.Aside p="md">
        <Group gap={8} mb="md">
          <IconHistory size={18} />
          <Title order={5}>Journal du projet</Title>
        </Group>
        <ScrollArea h="calc(100vh - 130px)">
          <Timeline bulletSize={14} lineWidth={2} active={-1}>
            {project.journal.map((e) => (
              <Timeline.Item key={e.id} title={<Text size="sm" fw={550}>{e.summary}</Text>}>
                <Text size="xs" c="dimmed">{formatDateTime(e.at)}</Text>
              </Timeline.Item>
            ))}
          </Timeline>
          <Text size="xs" c="dimmed" mt="md">
            Le journal indique quelles informations ont changé, jamais leur contenu.
          </Text>
        </ScrollArea>
      </AppShell.Aside>

      <Modal opened={pendingClose !== null} onClose={() => setPendingClose(null)} centered
        title={<Text fw={650}>Enregistrer les modifications ?</Text>}>
        <Text size="sm">
          Le projet « {project.study.title} » contient des modifications non enregistrées.
        </Text>
        <Stack gap="xs" mt="lg">
          <Button onClick={async () => { const target = pendingClose; if (await save()) await finishClose(target, false); }}>
            Enregistrer et fermer
          </Button>
          <Button color="red" variant="light" onClick={() => finishClose(pendingClose, true)}>
            Fermer sans enregistrer
          </Button>
          <Button variant="default" onClick={() => setPendingClose(null)}>Annuler</Button>
        </Stack>
      </Modal>
    </AppShell>
  );
}
