import { useEffect, useMemo, useState } from 'react';
import {
  Alert, Badge, Button, Divider, Grid, Group, List, Modal, MultiSelect, Paper, SegmentedControl, Select, SimpleGrid,
  Stack, Switch, Text, Textarea, TextInput, ThemeIcon, UnstyledButton,
} from '@mantine/core';
import {
  IconArrowLeft, IconArrowsLeftRight, IconBulb, IconChartDots, IconChevronRight, IconInfoCircle, IconListNumbers,
  IconTable, IconUsers,
} from '@tabler/icons-react';
import { call, errorMessage } from '../../engine/client';
import type {
  Analysis, AnalysisParams, AnalysisPurpose, Catalog, ChoiceInput, Dataset, MethodInfo, MethodVariable, PlanItem,
  ProjectState,
  Variable,
} from '../../engine/types';
import { AdvisorStep, EMPTY_GUIDE, type GuideState, type GuidedChoice } from './AdvisorStep';
import { exclusionReason } from './variables';

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
  const [guideMode, setGuideMode] = useState(false);
  const [guide, setGuide] = useState<GuideState>(EMPTY_GUIDE);
  const [guided, setGuided] = useState<GuidedChoice | null>(null);
  const [purpose, setPurpose] = useState<AnalysisPurpose | null>(null);
  const [hypothesis, setHypothesis] = useState<number | null>(null);
  const [planItems, setPlanItems] = useState<PlanItem[]>([]);
  const [planVersion, setPlanVersion] = useState<number | null>(null);
  const [planItem, setPlanItem] = useState<string | null>(null);
  const [planTouched, setPlanTouched] = useState(false);
  const [planReason, setPlanReason] = useState('');
  const hypotheses = project.study.hypotheses;
  const lockedPlan = project.plan_status?.locked_version ?? null;

  // Ouverture : reprise d'un brouillon (duplication) ou nouvelle analyse.
  useEffect(() => {
    if (!opened) return;
    setError(null);
    setTitle('');
    setGuideMode(false);
    setGuide(EMPTY_GUIDE);
    setGuided(null);
    setPurpose(null);
    setHypothesis(null);
    setPlanItem(null);
    setPlanTouched(false);
    setPlanReason('');
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

  // Analyses prévues du plan verrouillé, pour rattacher l'analyse à sa référence (A1, A2…).
  useEffect(() => {
    if (!opened || lockedPlan === null) { setPlanItems([]); setPlanVersion(null); return; }
    let cancelled = false;
    call('plan.get', {})
      .then((p) => { if (!cancelled) { setPlanItems(p.locked?.content.analyses ?? []); setPlanVersion(p.locked?.version ?? null); } })
      .catch(() => !cancelled && setPlanItems([]));
    return () => { cancelled = true; };
  }, [opened, lockedPlan]);

  const chosenNames = useMemo(() => {
    if (!method) return [] as string[];
    const byKey = new Map(variables.map((v) => [v.key, v.name]));
    return method.variables.flatMap((mv) => {
      const v = params[mv.name];
      const keys = Array.isArray(v) ? v as string[] : typeof v === 'string' ? [v] : [];
      return keys.map((k) => byKey.get(k) ?? k);
    });
  }, [method, params, variables]);
  const norm = (xs: string[]) => [...xs].map((x) => x.trim().toLocaleLowerCase('fr')).sort().join('|');
  const matching = planItems.find((it) => it.method === method?.key
    && norm(Object.values(it.variables).flat()) === norm(chosenNames));
  useEffect(() => {
    if (!planTouched) setPlanItem(matching?.id ?? null);
  }, [matching, planTouched]);
  const selectedItem = planItems.find((it) => it.id === planItem) ?? null;
  const deviates = selectedItem !== null && (selectedItem.method !== method?.key
    || norm(Object.values(selectedItem.variables).flat()) !== norm(chosenNames));

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
    const base: ChoiceInput = guided ? guided.choice : { mode: 'direct', purpose, hypothesis };
    const choice: ChoiceInput = planItem ? { ...base, plan_item: planItem, plan_reason: deviates ? planReason : '' } : base;
    try {
      const r = await call('analysis.run', {
        dataset_id: datasetId, version_id: versionId, method: method.key, params, choice,
        ...(title.trim() ? { title: title.trim() } : {}),
      });
      onDone(r.analysis, r.project);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const sourceSelects = (
    <Group grow>
      <Select label="Jeu de données" value={datasetId === null ? null : String(datasetId)} allowDeselect={false}
        disabled={Boolean(guided)}
        data={project.datasets.map((d) => ({ value: String(d.id), label: d.name }))}
        onChange={(v) => {
          setDatasetId(v ? Number(v) : null); setVersionId(null); setParams({}); setGuide(EMPTY_GUIDE);
        }} />
      <Select label="Version des données" allowDeselect={false} disabled={Boolean(guided)}
        value={versionId === null ? 'original' : String(versionId)}
        data={[{ value: 'original', label: "Données d'origine" },
          ...(dataset?.versions ?? []).map((v) => ({
            value: String(v.id), label: v.error ? `${v.name} (à corriger)` : `${v.name} (${v.rows} lignes)`,
            disabled: Boolean(v.error),
          }))]}
        onChange={(v) => { setVersionId(!v || v === 'original' ? null : Number(v)); setGuide((g) => ({ ...g, advice: null, selected: null })); }} />
    </Group>
  );

  const startGuide = () => { setError(null); setGuideMode(true); };
  const proceedGuided = (c: GuidedChoice) => {
    setGuided(c);
    setParams(c.params);
    setMethod(catalog.methods.find((m) => m.key === c.method) ?? null);
  };
  const backToMethods = () => {
    setError(null);
    setMethod(null);
    if (guided) { setGuided(null); setParams({}); }
  };

  const modalTitle = method ? method.label
    : guideMode ? "Nouvelle analyse : l'assistant vous aide à choisir" : 'Nouvelle analyse : que voulez-vous faire ?';

  return (
    <Modal opened={opened} onClose={onClose} size={method || guideMode ? 1040 : 860} centered
      title={<Text fw={650}>{modalTitle}</Text>}>
      {!method && guideMode && datasetId !== null ? (
        <AdvisorStep datasetId={datasetId} versionId={versionId} variables={variables} hypotheses={hypotheses}
          value={guide} onChange={setGuide} onProceed={proceedGuided}
          onDirect={() => { setGuideMode(false); setError(null); }} header={sourceSelects} />
      ) : !method ? (
        <Stack gap="md">
          <UnstyledButton onClick={startGuide} aria-label="Être guidé" disabled={datasetId === null}>
            <Paper withBorder p="md" className="method-card"
              style={{ borderColor: 'var(--mantine-color-brand-4)', background: 'var(--mantine-color-brand-0)' }}>
              <Group justify="space-between" wrap="nowrap">
                <Group gap="sm" wrap="nowrap">
                  <ThemeIcon size="lg" variant="filled"><IconBulb size={20} /></ThemeIcon>
                  <div>
                    <Text fw={650}>Être guidé dans le choix de la méthode</Text>
                    <Text size="sm" c="dimmed">
                      Décrivez votre objectif et vos variables : l'assistant recommande une méthode, explique pourquoi
                      et indique ses conditions et ses limites.
                    </Text>
                  </div>
                </Group>
                <IconChevronRight size={20} />
              </Group>
            </Paper>
          </UnstyledButton>
          <Divider label="ou choisissez directement une méthode" labelPosition="center" />
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
            Seules les méthodes implémentées et validées contre R sont proposées.
          </Text>
        </Stack>
      ) : (
        <Grid gap="lg">
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Stack gap="sm">
              {guided && (
                <Alert color={guided.followed ? 'teal' : 'yellow'} variant="light" icon={<IconBulb size={16} />}
                  title={guided.followed ? "Méthode recommandée par l'assistant" : 'Méthode choisie par vous'}>
                  {guided.followed
                    ? "Les variables viennent de l'assistant. Pour les changer, revenez à l'assistant."
                    : `L'assistant recommandait « ${catalog.methods.find((m) => m.key === guided.recommended)?.label
                      ?? 'aucune méthode'} ». Votre justification sera enregistrée avec l'analyse.`}
                </Alert>
              )}
              {sourceSelects}

              <Divider label="Variables" labelPosition="left" />
              {method.variables.map((mv) => (
                <VariablePicker key={mv.name} spec={mv} variables={variables} value={params[mv.name]}
                  disabled={Boolean(guided)} onChange={(v) => setParam(mv.name, v)} />
              ))}

              {usesLevels && levels && levels.length > 2 && (
                <Group grow>
                  {[0, 1].map((i) => (
                    <Select key={i} label={i === 0 ? 'Groupe 1' : 'Groupe 2'} allowDeselect={false}
                      disabled={Boolean(guided)} value={(params.levels as string[] | undefined)?.[i] ?? null}
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

              {!guided && (
                <>
                  <Divider label="Contexte (facultatif)" labelPosition="left" />
                  <Group grow align="flex-start">
                    <Select label="Nature de l'analyse" value={purpose ?? 'none'} allowDeselect={false}
                      data={[{ value: 'none', label: 'Non précisée' },
                        { value: 'confirmatoire', label: 'Confirmatoire (hypothèse fixée à l\'avance)' },
                        { value: 'exploratoire', label: 'Exploratoire (recherche de pistes)' }]}
                      onChange={(v) => setPurpose(!v || v === 'none' ? null : v as AnalysisPurpose)} />
                    {hypotheses.length > 0 && (
                      <Select label="Hypothèse mise à l'épreuve" clearable placeholder="Aucune"
                        data={hypotheses.map((h, i) => ({ value: String(i), label: `H${i + 1} : ${h}` }))}
                        value={hypothesis === null ? null : String(hypothesis)}
                        onChange={(v) => setHypothesis(v === null ? null : Number(v))} />
                    )}
                  </Group>
                </>
              )}

              {planItems.length > 0 && (
                <>
                  <Divider label={`Plan d'analyse (version ${planVersion} verrouillée)`} labelPosition="left" />
                  <Select label="Analyse prévue au plan" allowDeselect={false}
                    value={planItem ?? 'none'}
                    data={[{ value: 'none', label: 'Aucune : analyse non prévue au plan' },
                      ...planItems.map((it) => ({ value: it.id!, label: `${it.id} · ${catalog.methods.find((m) => m.key === it.method)?.label ?? it.method} : ${Object.values(it.variables).flat().join(', ')}` }))]}
                    description={planItem
                      ? (deviates ? 'Méthode ou variables différentes de celles prévues : indiquez la raison de l\'écart.'
                        : 'Correspond à l\'analyse prévue : elle sera présentée comme prévue dans le rapport.')
                      : 'Elle sera présentée dans le rapport comme ajoutée après consultation des données.'}
                    onChange={(v) => { setPlanTouched(true); setPlanItem(!v || v === 'none' ? null : v); }} />
                  {deviates && (
                    <Textarea label="Raison de l'écart au plan" autosize minRows={2} maxLength={2000} required
                      value={planReason} onChange={(e) => setPlanReason(e.currentTarget.value)}
                      placeholder="Ex. : distribution très asymétrique, test de Mann-Whitney retenu à la place du test t" />
                  )}
                </>
              )}

              <TextInput label="Titre de l'analyse (facultatif)" placeholder={method.label} maxLength={200}
                value={title} onChange={(e) => setTitle(e.currentTarget.value)} />

              {error && <Alert color="red" variant="light" title="Analyse impossible">{error}</Alert>}

              <Group justify="space-between" mt="xs">
                <Button variant="default" leftSection={<IconArrowLeft size={16} />}
                  onClick={backToMethods} disabled={Boolean(initial)}>
                  {guided ? "Retour à l'assistant" : 'Autre méthode'}
                </Button>
                <Button onClick={submit} loading={busy} disabled={Boolean(missingVariable) || datasetId === null || (deviates && !planReason.trim())}>
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

function VariablePicker({ spec, variables, value, onChange, disabled }: {
  spec: MethodVariable; variables: Variable[]; value: unknown; onChange: (v: unknown) => void; disabled?: boolean;
}) {
  const data = variables.map((v) => {
    const reason = exclusionReason(v, spec.kind);
    const desc = `${v.type_label}, ${v.level_label.toLowerCase()}`;
    return { value: v.key, label: reason ? `${v.name} (${reason})` : `${v.name} · ${desc}`, disabled: Boolean(reason) };
  });
  if (spec.multiple) {
    return (
      <MultiSelect label={spec.label} data={data} searchable disabled={disabled} value={(value as string[]) ?? []} maxValues={30}
        onChange={onChange} placeholder="Choisir une ou plusieurs variables" nothingFoundMessage="Aucune variable" />
    );
  }
  return (
    <Select label={spec.label} data={data} searchable disabled={disabled} clearable={spec.optional}
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
