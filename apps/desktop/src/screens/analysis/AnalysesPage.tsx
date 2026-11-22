import { useCallback, useEffect, useState } from 'react';
import {
  Badge, Box, Button, Center, Grid, Group, Loader, Modal, NavLink, Paper, ScrollArea, Stack, Text, Title,
} from '@mantine/core';
import { IconChartBar, IconPlus } from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { Analysis, AnalysisSummary, Catalog, ProjectState } from '../../engine/types';
import { formatDateTime } from '../../lib/format';
import { notifyError } from '../../App';
import { NewAnalysisModal, type AnalysisDraft } from './NewAnalysisModal';
import { ResultView, STATUS_COLOR } from './ResultView';

interface Props {
  project: ProjectState;
  onChange: (p: ProjectState) => void;
  onGoToData: () => void;
}

export function AnalysesPage({ project, onChange, onGoToData }: Props) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [list, setList] = useState<AnalysisSummary[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [modal, setModal] = useState<{ initial: AnalysisDraft | null } | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const items = await call('analysis.list');
      setList(items);
      return items;
    } catch (err) {
      notifyError(err, 'Impossible de charger les analyses');
      return null;
    }
  }, []);

  useEffect(() => {
    call('analysis.catalog').then(setCatalog).catch((err) => notifyError(err, 'Catalogue indisponible'));
    void refresh().then((items) => { if (items && items.length) setSelected(items[0].id); });
  }, [refresh]);

  useEffect(() => {
    if (selected === null) { setAnalysis(null); return; }
    let cancelled = false;
    call('analysis.get', { analysis_id: selected })
      .then((a) => { if (!cancelled) setAnalysis(a); })
      .catch((err) => !cancelled && notifyError(err, "Impossible d'ouvrir l'analyse"));
    return () => { cancelled = true; };
  }, [selected]);

  if (project.datasets.length === 0) {
    return (
      <Center h="60vh"><Stack align="center">
        <Text c="dimmed">Importez d'abord des données pour lancer une analyse.</Text>
        <Button onClick={onGoToData}>Aller aux données</Button>
      </Stack></Center>
    );
  }

  const onDone = async (a: Analysis, p: ProjectState) => {
    setModal(null);
    onChange(p);
    await refresh();
    setAnalysis(a);
    setSelected(a.id);
  };

  const remove = async () => {
    if (!analysis) return;
    try {
      onChange(await call('analysis.delete', { analysis_id: analysis.id }));
      const items = await refresh();
      setSelected(items && items.length ? items[0].id : null);
    } catch (err) {
      notifyError(err, 'Suppression impossible');
    }
    setConfirmDelete(false);
  };

  return (
    <Box p="lg">
      <Group justify="space-between" mb="md">
        <div>
          <Title order={2}>Analyses</Title>
          <Text c="dimmed" size="sm">
            Chaque analyse enregistre la version des données, leur empreinte, la méthode et ses paramètres.
          </Text>
        </div>
        <Button leftSection={<IconPlus size={16} />} disabled={!catalog} onClick={() => setModal({ initial: null })}>
          Nouvelle analyse
        </Button>
      </Group>

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 3 }}>
          <Paper withBorder p="xs">
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" px="xs" py={4}>
              Analyses enregistrées ({list?.length ?? 0})
            </Text>
            {list === null ? <Center p="md"><Loader size="sm" /></Center> : list.length === 0 ? (
              <Text size="sm" c="dimmed" p="xs">Aucune analyse pour l'instant.</Text>
            ) : (
              <ScrollArea.Autosize mah="calc(100vh - 260px)">
                {list.map((a) => (
                  <NavLink key={a.id} active={a.id === selected} onClick={() => setSelected(a.id)}
                    variant="light" style={{ borderRadius: 8 }}
                    label={<Text size="sm" fw={550} lineClamp={2}>{a.title}</Text>}
                    description={`${a.version_name} · ${formatDateTime(a.created_at)}`}
                    rightSection={a.status !== 'a_jour'
                      ? <Badge size="xs" color={STATUS_COLOR[a.status]} variant="light">à vérifier</Badge> : null} />
                ))}
              </ScrollArea.Autosize>
            )}
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 9 }}>
          {analysis ? (
            <ResultView key={analysis.id} analysis={analysis}
              onReproduce={async () => {
                try {
                  const r = await call('analysis.reproduce', { analysis_id: analysis.id });
                  onChange(r.project);
                  return r.report;
                } catch (err) {
                  notifyError(err, 'Reproduction impossible');
                  return null;
                }
              }}
              onDuplicate={() => setModal({ initial: {
                dataset_id: analysis.dataset_id, version_id: analysis.version_id, method: analysis.method,
                params: analysis.params,
              } })}
              onDelete={() => setConfirmDelete(true)}
              onSaveNote={async (note) => {
                try {
                  const r = await call('analysis.update', { analysis_id: analysis.id, changes: { note } });
                  setAnalysis(r.analysis);
                  onChange(r.project);
                } catch (err) {
                  notifyError(err, 'Note non enregistrée');
                }
              }} />
          ) : list && list.length === 0 ? (
            <Paper withBorder p="xl">
              <Stack align="center" gap="xs">
                <IconChartBar size={40} stroke={1.3} color="var(--mantine-color-brand-6)" />
                <Text fw={600}>Lancez votre première analyse</Text>
                <Text size="sm" c="dimmed" ta="center" maw={460}>
                  Statistiques descriptives, comparaisons de groupes, corrélations ou tableaux croisés : chaque
                  résultat est calculé par le moteur, accompagné de ses diagnostics et d'une lecture prudente.
                </Text>
                <Button mt="sm" leftSection={<IconPlus size={16} />} disabled={!catalog}
                  onClick={() => setModal({ initial: null })}>Nouvelle analyse</Button>
              </Stack>
            </Paper>
          ) : null}
        </Grid.Col>
      </Grid>

      {catalog && (
        <NewAnalysisModal opened={modal !== null} onClose={() => setModal(null)} project={project} catalog={catalog}
          initial={modal?.initial ?? null} onDone={(a, p) => void onDone(a, p)} />
      )}

      <Modal opened={confirmDelete} onClose={() => setConfirmDelete(false)} centered
        title={<Text fw={650}>Supprimer cette analyse ?</Text>}>
        <Text size="sm">
          « {analysis?.title} » sera retirée du projet (les données ne sont pas modifiées). La suppression devient
          définitive à l'enregistrement du projet.
        </Text>
        <Group justify="flex-end" mt="lg">
          <Button variant="default" onClick={() => setConfirmDelete(false)}>Annuler</Button>
          <Button color="red" onClick={() => void remove()}>Supprimer</Button>
        </Group>
      </Modal>
    </Box>
  );
}
