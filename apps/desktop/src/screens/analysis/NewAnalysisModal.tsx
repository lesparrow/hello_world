import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Badge, Button, Divider, Grid, Group, List, Modal, MultiSelect, Paper, SegmentedControl, Select, SimpleGrid,
  Stack, Switch, Text, TextInput, ThemeIcon, UnstyledButton,
} from '@mantine/core';
import {
  IconArrowLeft, IconArrowsLeftRight, IconChartDots, IconInfoCircle, IconListNumbers, IconTable, IconUsers,
} from '@tabler/icons-react';
import { call, errorMessage } from '../../engine/client';
import type {
  Analysis, AnalysisParams, Catalog, Dataset, MethodInfo, MethodVariable, ProjectState, Variable,
} from '../../engine/types';

export interface AnalysisDraft {
  dataset_id: number;
  version_id: number | null;
  method: string;
  params: AnalysisParams;
}

interface Props {
  opened: boolean;
  onClose: () => void;
  project: ProjectState;
  catalog: Catalog;
  initial: AnalysisDraft | null;
  onDone: (a: Analysis, p: ProjectState) => void;
}

const FAMILY_ICON: Record<string, typeof IconTable> = {
  describe: IconListNumbers, compare2: IconUsers, paired: IconArrowsLeftRight, correlate: IconChartDots,
  associate: IconTable,
};

const ALTERNATIVES = [
  { value: 'two-sided', label: 'Bilatérale' },
  { value: 'less', label: 'Unilatérale <' },
  { value: 'greater', label: 'Unilatérale >' },
];

/** Raison pour laquelle une variable ne peut pas être choisie (ou null). */
export function exclusionReason(v: Variable, kind: MethodVariable['kind']): string | null {
  if (v.role === 'identifiant') return 'identifiant';
  if (v.role === 'exclue') return 'exclue des analyses';
  if (v.potential_identifier) return 'identifiant potentiel';
  if (kind === 'quantitative' && v.type !== 'numerique') return 'non numérique';
  if (kind === 'qualitative' && v.type === 'date') return 'date';
  return null;
}

export function NewAnalysisModal({ opened, onClose, project, catalog, initial, onDone }: Props) {
  const [method, setMethod] = useState<MethodInfo | null>(null);
  const [datasetId, setDatasetId] = useState<number | null>(null);
  const [versionId, setVersionId] = useState<number | null>(null);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [params, setParams] = useState<AnalysisParams>({});
  const [title, setTitle] = useState('');
  const [levels, setLevels] = useState<{ value: string; label: string; count: number }[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ouverture : reprise d'un brouillon (duplication) ou nouvelle analyse.
  useEffect(() => {
    if (!opened) return;
    setError(null);
    setTitle('');
    if (initial) {
      setMethod(catalog.methods.find((m) => m.key === initial.method) ?? null);
      setDatasetId(initial.dataset_id);
      setVersionId(initial.version_id);
      setParams({ ...initial.params });
    } else {
      setMethod(null);
      setDatasetId(project.datasets[0]?.id ?? null);
      setVersionId(null);
      setParams({});
    }
  }, [opened, initial, catalog, project.datasets]);

  useEffect(() => {
    if (!opened || datasetId === null) { setDataset(null); return; }
    let cancelled = false;
    call('data.get', { dataset_id: datasetId })
      .then((d) => { if (!cancelled) setDataset(d); })
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => { cancelled = true; };
  }, [opened, datasetId]);

  const version = dataset?.versions.find((v) => v.id === versionId) ?? null;
  const variables: Variable[] = version ? version.variables : dataset?.variables ?? [];
  const usesLevels = method?.params.includes('levels') ?? false;
  const groupKey = typeof params.group === 'string' ? params.group : null;

  // Modalités de la variable de groupe (pour choisir les deux groupes comparés).
  useEffect(() => {
    if (!usesLevels || !groupKey || datasetId === null) { setLevels(null); return; }
    let cancelled = false;
    call('analysis.levels', { dataset_id: datasetId, version_id: versionId, key: groupKey })
      .then((lv) => {
        if (cancelled) return;
        setLevels(lv);
        setParams((p) => {
          const cur = p.levels as string[] | undefined;
          const valid = cur && cur.length === 2 && cur.every((c) => lv.some((l) => l.value === c));
          return { ...p, levels: valid ? cur : lv.length >= 2 ? [lv[0].value, lv[1].value] : undefined };
        });
      })
      .catch((err) => { if (!cancelled) { setLevels([]); setError(errorMessage(err)); } });
    return () => { cancelled = true; };
  }, [usesLevels, groupKey, datasetId, versionId]);

  const families = useMemo(() => Object.entries(catalog.families), [catalog]);

  const setParam = (name: string, value: unknown) => {
    setError(null);
    setParams((p) => {
      const next = { ...p };
      if (value === null || value === undefined || (Array.isArray(value) && value.length === 0)) delete next[name];
      else next[name] = value;
      return next;
    });
  };

  const missingVariable = method?.variables.find((mv) => !mv.optional && (mv.multiple
    ? !Array.isArray(params[mv.name]) || (params[mv.name] as unknown[]).length === 0
    : typeof params[mv.name] !== 'string'));

  const submit = async () => {
    if (!method || datasetId === null) return;
    setBusy(true);
    setError(null);
    try {
      const r = await call('analysis.run', {
        dataset_id: datasetId, version_id: versionId, method: method.key, params,
        ...(title.trim() ? { title: title.trim() } : {}),
      });
      onDone(r.analysis, r.project);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} size={method ? 980 : 860} centered
      title={<Text fw={650}>{method ? method.label : 'Nouvelle analyse : que voulez-vous faire ?'}</Text>}>
      {!method ? (
        <Stack gap="md">
          {families.map(([fam, label]) => {
            const Icon = FAMILY_ICON[fam] ?? IconTable;
            return (
              <div key={fam}>
                <Group gap={8} mb={6}>
                  <ThemeIcon variant="light" size="sm"><Icon size={14} /></ThemeIcon>
                  <Text size="sm" fw={650}>{label}</Text>
                </Group>
                <SimpleGrid cols={{ base: 1, sm: 3 }} spacing="xs">
                  {catalog.methods.filter((m) => m.family === fam).map((m) => (
                    <UnstyledButton key={m.key} onClick={() => { setMethod(m); setParams({}); }} aria-label={m.label}>
                      <Paper withBorder p="sm" h="100%" className="method-card">
                        <Text size="sm" fw={600}>{m.label}</Text>
                        <Text size="xs" c="dimmed" lineClamp={3}>{m.objective}</Text>
                      </Paper>
                    </UnstyledButton>
                  ))}
                </SimpleGrid>
              </div>
            );
          })}
          <Text size="xs" c="dimmed">
            Seules les méthodes implémentées et validées contre R sont proposées. L'assistant de choix de méthode
            arrivera avec la phase suivante.
          </Text>
        </Stack>
      ) : (
        <Grid gap="lg">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="sm">
              <Group grow>
                <Select label="Jeu de données" value={datasetId === null ? null : String(datasetId)} allowDeselect={false}
                  data={project.datasets.map((d) => ({ value: String(d.id), label: d.name }))}
                  onChange={(v) => { setDatasetId(v ? Number(v) : null); setVersionId(null); setParams({}); }} />
                <Select label="Version des données" allowDeselect={false}
                  value={versionId === null ? 'original' : String(versionId)}
                  data={[{ value: 'original', label: "Données d'origine" },
                    ...(dataset?.versions ?? []).map((v) => ({
                      value: String(v.id), label: v.error ? `${v.name} (à corriger)` : `${v.name} (${v.rows} lignes)`,
                      disabled: Boolean(v.error),
                    }))]}
                  onChange={(v) => setVersionId(!v || v === 'original' ? null : Number(v))} />
              </Group>

              <Divider label="Variables" labelPosition="left" />
              {method.variables.map((mv) => (
                <VariablePicker key={mv.name} spec={mv} variables={variables} value={params[mv.name]}
                  onChange={(v) => setParam(mv.name, v)} />
              ))}

              {usesLevels && levels && levels.length > 2 && (
                <Group grow>
                  {[0, 1].map((i) => (
                    <Select key={i} label={i === 0 ? 'Groupe 1' : 'Groupe 2'} allowDeselect={false}
                      value={(params.levels as string[] | undefined)?.[i] ?? null}
                      data={levels.map((l) => ({ value: l.value, label: `${l.label} (n = ${l.count})` }))}
                      onChange={(v) => {
                        const cur = [...((params.levels as string[] | undefined) ?? ['', ''])];
                        cur[i] = v ?? '';
                        setParam('levels', cur);
                      }} />
                  ))}
                </Group>
              )}
              {usesLevels && levels && levels.length === 2 && (
                <Group gap="xs" align="center">
                  <Text size="sm">
                    Différence calculée : « {labelOf(levels, (params.levels as string[] | undefined)?.[0])} » −
                    « {labelOf(levels, (params.levels as string[] | undefined)?.[1])} »
                  </Text>
                  <Button size="compact-xs" variant="subtle"
                    onClick={() => setParam('levels', [...((params.levels as string[]) ?? [])].reverse())}>
                    Inverser
                  </Button>
                </Group>
              )}

              {(method.params.includes('alternative') || method.params.includes('conf_level')
                || method.params.includes('percentages') || method.params.includes('correction')) && (
                <Divider label="Options" labelPosition="left" />
              )}
              {method.params.includes('alternative') && (
                <div>
                  <Text size="sm" fw={500} mb={4}>Hypothèse alternative</Text>
                  <SegmentedControl size="xs" data={ALTERNATIVES} value={(params.alternative as string) ?? 'two-sided'}
                    onChange={(v) => setParam('alternative', v === 'two-sided' ? null : v)} />
                  <Text size="xs" c="dimmed" mt={4}>
                    Une hypothèse unilatérale doit être fixée avant d'avoir vu les données.
                  </Text>
                </div>
              )}
              {method.params.includes('conf_level') && (
                <Select label="Niveau de confiance" w={220} allowDeselect={false}
                  value={String(params.conf_level ?? 0.95)}
                  data={[{ value: '0.9', label: '90 % (seuil α = 10 %)' }, { value: '0.95', label: '95 % (seuil α = 5 %)' },
                    { value: '0.99', label: '99 % (seuil α = 1 %)' }]}
                  onChange={(v) => setParam('conf_level', !v || v === '0.95' ? null : Number(v))} />
              )}
              {method.params.includes('percentages') && (
                <Select label="Pourcentages" w={260} allowDeselect={false} value={(params.percentages as string) ?? 'row'}
                  data={[{ value: 'row', label: 'En ligne' }, { value: 'col', label: 'En colonne' },
                    { value: 'all', label: 'En ligne et en colonne' }, { value: 'none', label: 'Aucun' }]}
                  onChange={(v) => setParam('percentages', v === 'row' ? null : v)} />
              )}
              {method.params.includes('correction') && (
                <Switch label="Correction de continuité de Yates (tableau 2 × 2)" checked={params.correction !== false}
                  onChange={(e) => setParam('correction', e.currentTarget.checked ? null : false)} />
              )}

              <TextInput label="Titre de l'analyse (facultatif)" placeholder={method.label} maxLength={200}
                value={title} onChange={(e) => setTitle(e.currentTarget.value)} />

              {error && <Alert color="red" variant="light" title="Analyse impossible">{error}</Alert>}

              <Group justify="space-between" mt="xs">
                <Button variant="default" leftSection={<IconArrowLeft size={16} />}
                  onClick={() => { setMethod(null); setError(null); }} disabled={Boolean(initial)}>
                  Autre méthode
                </Button>
                <Button onClick={submit} loading={busy} disabled={Boolean(missingVariable) || datasetId === null}>
                  Calculer
                </Button>
              </Group>
            </Stack>
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <MethodCard method={method} />
          </Grid.Col>
        </Grid>
      )}
    </Modal>
  );
}

function labelOf(levels: { value: string; label: string }[], v: string | undefined): string {
  return levels.find((l) => l.value === v)?.label ?? v ?? '';
}

function VariablePicker({ spec, variables, value, onChange }: {
  spec: MethodVariable; variables: Variable[]; value: unknown; onChange: (v: unknown) => void;
}) {
  const data = variables.map((v) => {
    const reason = exclusionReason(v, spec.kind);
    const desc = `${v.type_label}, ${v.level_label.toLowerCase()}`;
    return { value: v.key, label: reason ? `${v.name} (${reason})` : `${v.name} · ${desc}`, disabled: Boolean(reason) };
  });
  if (spec.multiple) {
    return (
      <MultiSelect label={spec.label} data={data} searchable value={(value as string[]) ?? []} maxValues={30}
        onChange={onChange} placeholder="Choisir une ou plusieurs variables" nothingFoundMessage="Aucune variable" />
    );
  }
  return (
    <Select label={spec.label} data={data} searchable clearable={spec.optional}
      value={(value as string) ?? null} onChange={onChange} placeholder={spec.optional ? 'Aucune' : 'Choisir une variable'}
      nothingFoundMessage="Aucune variable" />
  );
}

function MethodCard({ method }: { method: MethodInfo }) {
  return (
    <Paper withBorder p="md" bg="var(--mantine-color-gray-0)">
      <Group gap={6} mb="xs">
        <IconInfoCircle size={16} />
        <Text size="sm" fw={650}>À propos de cette méthode</Text>
      </Group>
      <Text size="sm" mb="sm">{method.objective}</Text>
      <Text size="xs" fw={650} tt="uppercase" c="dimmed">Conditions d'utilisation</Text>
      <List size="sm" spacing={2} mb="sm">{method.conditions.map((c) => <List.Item key={c}>{c}</List.Item>)}</List>
      <Text size="xs" fw={650} tt="uppercase" c="dimmed">Résultats fournis</Text>
      <List size="sm" spacing={2} mb="sm">{method.results.map((c) => <List.Item key={c}>{c}</List.Item>)}</List>
      {method.warnings.length > 0 && (
        <>
          <Text size="xs" fw={650} tt="uppercase" c="dimmed">Avertissements possibles</Text>
          <Text size="sm" mb="sm">{method.warnings.join(' · ')}</Text>
        </>
      )}
      <Badge variant="outline" color="gray" tt="none">Équivalent R : {method.r_equivalent}</Badge>
      <Text size="xs" c="dimmed" mt="sm">
        {method.key === 'descriptives'
          ? 'Valeurs manquantes : chaque variable est décrite à partir de ses valeurs disponibles ; le nombre de manquants est indiqué.'
          : "Valeurs manquantes : seules les observations complètes pour les variables choisies sont utilisées ; le nombre d'exclusions est indiqué dans le résultat."}
      </Text>
    </Paper>
  );
}
