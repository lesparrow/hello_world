import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActionIcon, Alert, Badge, Box, Button, Checkbox, Grid, Group, List, Loader, Paper, ScrollArea, SegmentedControl,
  Select, SimpleGrid, Stack, Switch, Text, TextInput, ThemeIcon, Title, Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle, IconArrowDown, IconArrowUp, IconChartBar, IconCircleCheck, IconFileExport, IconInfoCircle,
  IconTable, IconX,
} from '@tabler/icons-react';
import { call, errorMessage } from '../../engine/client';
import type {
  AnalysisSummary, Catalog, CheckLevel, OutlineItem, PowerCalcSummary, ProjectState, ReportCheck, ReportExport,
  ReportFormat, ReportOptions, ReportTemplates,
} from '../../engine/types';
import { pickReportDestination } from '../../lib/files';
import { suggestFileName } from '../../lib/format';
import { STATUS_COLOR } from '../analysis/ResultView';

interface Props {
  project: ProjectState;
  onChange: (p: ProjectState) => void;
  onGoToAnalyses: () => void;
}

const LEVEL: Record<CheckLevel, { color: string; label: string }> = {
  bloquant: { color: 'red', label: 'Bloquant' },
  important: { color: 'orange', label: 'Important' },
  methodologique: { color: 'yellow', label: 'Méthodologique' },
  information: { color: 'blue', label: 'Information' },
};

export function ReportPage({ project, onChange, onGoToAnalyses }: Props) {
  const [templates, setTemplates] = useState<ReportTemplates | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [calcs, setCalcs] = useState<PowerCalcSummary[]>([]);
  const [options, setOptions] = useState<ReportOptions | null>(null);
  const [checks, setChecks] = useState<ReportCheck | null>(null);
  const [outline, setOutline] = useState<OutlineItem[]>([]);
  const [checking, setChecking] = useState(false);
  const [format, setFormat] = useState<ReportFormat>('docx');
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState<ReportExport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    Promise.all([call('report.templates', {}), call('report.options', {}), call('analysis.list', {}),
      call('analysis.catalog', {}), call('power.list', {})])
      .then(([t, o, a, c, pw]) => { setTemplates(t); setOptions(o); setAnalyses(a); setCatalog(c); setCalcs(pw); })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  // Contrôles relancés à chaque modification des options (le moteur les enregistre dans le projet).
  useEffect(() => {
    if (!options) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setChecking(true);
      call('report.check', { options })
        .then((r) => {
          if (cancelled) return;
          setChecks(r.checks);
          setOutline(r.outline);
          setError(null);
          onChangeRef.current(r.project);
        })
        .catch((err) => !cancelled && setError(errorMessage(err)))
        .finally(() => !cancelled && setChecking(false));
    }, 350);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [options]);

  const family = useMemo(() => {
    const m = new Map<string, string>();
    catalog?.methods.forEach((x) => m.set(x.key, x.family));
    return m;
  }, [catalog]);

  const ordered = useMemo(() => {
    if (!options) return [];
    const byId = new Map(analyses.map((a) => [a.id, a]));
    const chosen = options.analyses.map((id) => byId.get(id)).filter((a): a is AnalysisSummary => Boolean(a));
    return [...chosen, ...analyses.filter((a) => !options.analyses.includes(a.id))];
  }, [analyses, options]);

  if (error && !options) return <Box p="xl"><Alert color="red" title="Rapport indisponible">{error}</Alert></Box>;
  if (!options || !templates) return <Box p="xl"><Loader size="sm" /></Box>;

  const update = (patch: Partial<ReportOptions>) => { setExported(null); setOptions({ ...options, ...patch }); };
  const setTemplate = (key: string) => {
    const t = templates.templates.find((x) => x.key === key);
    if (!t) return;
    update({ template: key, sections: Object.fromEntries(templates.sections.map((s) => [s.key, t.sections.includes(s.key)])) });
  };
  const toggle = (id: number, on: boolean) => update({
    analyses: on ? [...options.analyses, id] : options.analyses.filter((x) => x !== id),
  });
  const move = (id: number, delta: number) => {
    const list = [...options.analyses];
    const i = list.indexOf(id);
    const j = i + delta;
    if (i < 0 || j < 0 || j >= list.length) return;
    [list[i], list[j]] = [list[j], list[i]];
    update({ analyses: list });
  };

  const exportReport = async () => {
    const base = suggestFileName(project.study.title).replace(/\.statpfe$/, '');
    const path = await pickReportDestination(`${base}-rapport.${format}`, format);
    if (!path) return;
    setExporting(true);
    setError(null);
    try {
      const r = await call('report.export', { path, format, options });
      setExported(r.export);
      setChecks(r.export.checks);
      onChange(r.project);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setExporting(false);
    }
  };

  const tables = outline.filter((o) => o.kind === 'table').length;
  const figures = outline.filter((o) => o.kind === 'figure').length;
  const blocking = checks?.blocking ?? 0;

  return (
    <Box p="xl" maw={1400}>
      <Group justify="space-between" mb="lg" align="flex-end">
        <div>
          <Title order={2}>Rapport</Title>
          <Text c="dimmed" size="sm">
            Un rapport Word ou PDF construit à partir de votre étude et de vos analyses enregistrées, contrôlé avant
            l'export. C'est un document de travail à relire et à compléter, jamais un rapport « validé ».
          </Text>
        </div>
      </Group>

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Stack gap="md">
            <Paper withBorder p="md">
              <Text fw={650} mb="xs">Modèle</Text>
              <Select aria-label="Modèle de rapport" allowDeselect={false} value={options.template} w={340}
                data={templates.templates.map((t) => ({ value: t.key, label: t.label }))}
                onChange={(v) => v && setTemplate(v)} />
              <Text size="xs" c="dimmed" mt={6}>
                Le modèle choisit la page de garde et les sections proposées ; vous pouvez ensuite ajuster chaque section.
              </Text>
            </Paper>

            {options.sections.cover && (
              <Paper withBorder p="md">
                <Text fw={650} mb="xs">Page de garde</Text>
                <Text size="sm" mb="sm">Titre : <b>{project.study.title}</b> <Text span size="xs" c="dimmed">(fiche « Étude »)</Text></Text>
                <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
                  {templates.cover_fields.map((f) => (
                    <TextInput key={f.key} label={f.label} maxLength={300} value={options.cover[f.key] ?? ''}
                      onChange={(e) => update({ cover: { ...options.cover, [f.key]: e.currentTarget.value } })} />
                  ))}
                </SimpleGrid>
              </Paper>
            )}

            <Paper withBorder p="md">
              <Text fw={650} mb="xs">Sections</Text>
              <SimpleGrid cols={{ base: 1, sm: 2 }} spacing={6}>
                {templates.sections.map((s) => (
                  <Checkbox key={s.key} label={s.label} checked={options.sections[s.key] ?? false}
                    onChange={(e) => update({ sections: { ...options.sections, [s.key]: e.currentTarget.checked } })} />
                ))}
              </SimpleGrid>
              <Switch mt="md" label="Inclure les figures (histogrammes, boîtes à moustaches, barres, nuages de points, courbes de puissance)"
                checked={options.figures} onChange={(e) => update({ figures: e.currentTarget.checked })} />
              <Switch mt="xs" label="Inclure les textes rédigés avec l'aide de l'IA, relus et retenus (toujours signalés comme tels)"
                checked={options.ai_texts ?? true} onChange={(e) => update({ ai_texts: e.currentTarget.checked })} />
            </Paper>

            <Paper withBorder p="md">
              <Group justify="space-between" mb="xs">
                <Text fw={650}>Analyses incluses ({options.analyses.length} sur {analyses.length})</Text>
                <Group gap="xs">
                  <Button size="compact-xs" variant="subtle" onClick={() => update({ analyses: analyses.map((a) => a.id) })}>
                    Tout inclure
                  </Button>
                  <Button size="compact-xs" variant="subtle" onClick={() => update({ analyses: [] })}>Aucune</Button>
                </Group>
              </Group>
              {analyses.length === 0 ? (
                <Alert variant="light" color="gray" icon={<IconInfoCircle size={16} />}>
                  Aucune analyse enregistrée.{' '}
                  <Button variant="subtle" size="compact-sm" onClick={onGoToAnalyses}>Lancer une analyse</Button>
                </Alert>
              ) : (
                <Stack gap={4}>
                  {ordered.map((a) => {
                    const on = options.analyses.includes(a.id);
                    const desc = family.get(a.method) === 'describe';
                    return (
                      <Group key={a.id} justify="space-between" wrap="nowrap" p={6}
                        style={{ borderRadius: 6, background: on ? 'var(--mantine-color-gray-0)' : undefined }}>
                        <Checkbox checked={on} onChange={(e) => toggle(a.id, e.currentTarget.checked)}
                          label={<>
                            <Text size="sm" span fw={on ? 600 : 400}>{a.title}</Text>
                            <Text size="xs" c="dimmed" span> · {a.method_label} · {a.dataset_name ?? '—'}, {a.version_name}</Text>
                          </>} />
                        <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
                          <Badge size="xs" variant="light" color={desc ? 'gray' : 'brand'}>
                            {desc ? 'descriptive' : 'inférentielle'}
                          </Badge>
                          {a.status !== 'a_jour' && <Badge size="xs" color={STATUS_COLOR[a.status]}>{a.status_label}</Badge>}
                          {on && (
                            <>
                              <ActionIcon size="sm" variant="subtle" aria-label="Monter" onClick={() => move(a.id, -1)}>
                                <IconArrowUp size={14} />
                              </ActionIcon>
                              <ActionIcon size="sm" variant="subtle" aria-label="Descendre" onClick={() => move(a.id, 1)}>
                                <IconArrowDown size={14} />
                              </ActionIcon>
                            </>
                          )}
                        </Group>
                      </Group>
                    );
                  })}
                  <Text size="xs" c="dimmed" mt={4}>
                    Dans le rapport, les analyses descriptives sont présentées avant les analyses inférentielles, chacune
                    dans l'ordre choisi ici.
                  </Text>
                </Stack>
              )}
            </Paper>
            {options.sections.power && calcs.length > 0 && (
              <Paper withBorder p="md">
                <Text fw={650} mb="xs">Calculs de puissance inclus ({options.power.length} sur {calcs.length})</Text>
                <Stack gap={4}>
                  {calcs.map((c) => (
                    <Checkbox key={c.id} checked={options.power.includes(c.id)}
                      onChange={(e) => update({ power: e.currentTarget.checked ? [...options.power, c.id]
                        : options.power.filter((x) => x !== c.id) })}
                      label={<>
                        <Text size="sm" span>{c.title}</Text>
                        <Text size="xs" c="dimmed" span> · {c.mode_label}</Text>
                      </>} />
                  ))}
                </Stack>
              </Paper>
            )}
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Stack gap="md" style={{ position: 'sticky', top: 16 }}>
            <Paper withBorder p="md">
              <Group justify="space-between" mb="xs">
                <Text fw={650}>Contrôles avant export</Text>
                {checking ? <Loader size="xs" /> : checks && (
                  <Badge color={blocking ? 'red' : 'teal'} variant="light">
                    {blocking ? `${blocking} bloquant(s)` : 'Export possible'}
                  </Badge>
                )}
              </Group>
              {checks && (
                <ScrollArea.Autosize mah={360}>
                  <Stack gap={6}>
                    {checks.items.map((i, k) => (
                      <Group key={k} gap={8} wrap="nowrap" align="flex-start">
                        <ThemeIcon size="sm" variant="light" color={LEVEL[i.level].color}>
                          {i.level === 'bloquant' ? <IconX size={12} /> : i.level === 'information'
                            ? <IconInfoCircle size={12} /> : <IconAlertTriangle size={12} />}
                        </ThemeIcon>
                        <div>
                          <Text size="sm" fw={500}>{i.title}</Text>
                          {i.detail && <Text size="xs" c="dimmed">{i.detail}</Text>}
                        </div>
                      </Group>
                    ))}
                    {checks.passed.map((t) => (
                      <Group key={t} gap={8} wrap="nowrap" align="flex-start">
                        <ThemeIcon size="sm" variant="light" color="teal"><IconCircleCheck size={12} /></ThemeIcon>
                        <Text size="sm">{t}</Text>
                      </Group>
                    ))}
                  </Stack>
                </ScrollArea.Autosize>
              )}
            </Paper>

            <Paper withBorder p="md">
              <Group justify="space-between" mb="xs">
                <Text fw={650}>Plan du rapport</Text>
                <Group gap={6}>
                  <Tooltip label="Tableaux numérotés"><Badge leftSection={<IconTable size={11} />} variant="light" color="gray">{tables}</Badge></Tooltip>
                  <Tooltip label="Figures numérotées"><Badge leftSection={<IconChartBar size={11} />} variant="light" color="gray">{figures}</Badge></Tooltip>
                </Group>
              </Group>
              <ScrollArea.Autosize mah={260}>
                <List size="sm" spacing={2} listStyleType="none">
                  {outline.filter((o) => o.kind === 'heading').map((o, k) => (
                    <List.Item key={k} pl={o.level === 2 ? 16 : 0}>
                      <Text size="sm" fw={o.level === 1 ? 600 : 400} c={o.level === 1 ? undefined : 'dimmed'}>{o.text}</Text>
                    </List.Item>
                  ))}
                </List>
              </ScrollArea.Autosize>
            </Paper>

            <Paper withBorder p="md">
              <Text fw={650} mb="xs">Exporter</Text>
              <Group align="flex-end" justify="space-between">
                <SegmentedControl value={format} onChange={(v) => { setFormat(v as ReportFormat); setExported(null); }}
                  data={templates.formats.map((f) => ({ value: f.key, label: f.label }))} />
                <Button leftSection={<IconFileExport size={16} />} loading={exporting}
                  disabled={!checks || blocking > 0 || checking} onClick={exportReport}>
                  Exporter le rapport
                </Button>
              </Group>
              {blocking > 0 && (
                <Text size="xs" c="red" mt={6}>Corrigez les contrôles bloquants pour pouvoir exporter.</Text>
              )}
              {error && <Alert mt="sm" color="red" variant="light" title="Export impossible">{error}</Alert>}
              {exported && (
                <Alert mt="sm" color="teal" variant="light" icon={<IconCircleCheck size={16} />} title="Rapport exporté">
                  <Text size="sm">{exported.file_name} ({Math.max(1, Math.round(exported.size / 1024))} Ko) :
                    {' '}{exported.tables} tableau(x), {exported.figures} figure(s).</Text>
                  <Text size="xs" c="dimmed" style={{ overflowWrap: 'anywhere' }}>{exported.path}</Text>
                  {format === 'docx' && (
                    <Text size="xs" mt={4}>À l'ouverture, Word propose de mettre à jour les champs : acceptez pour
                      afficher le sommaire.</Text>
                  )}
                </Alert>
              )}
            </Paper>
          </Stack>
        </Grid.Col>
      </Grid>
    </Box>
  );
}
