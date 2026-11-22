import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActionIcon, Alert, Badge, Box, Button, Grid, Group, List, Loader, NumberInput, Paper, SegmentedControl, Select,
  Stack, Text, Textarea, TextInput, ThemeIcon, Title, Tooltip,
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import {
  IconAlertTriangle, IconDeviceFloppy, IconInfoCircle, IconPlus, IconTrash, IconUpload,
} from '@tabler/icons-react';
import { call, errorMessage } from '../../engine/client';
import type {
  AnalysisSummary, PowerCalcSummary, PowerCatalog, PowerDesign, PowerDesignInfo, PowerEffect, PowerMode,
  PowerRequest, PowerResult, PowerSides, ProjectState,
} from '../../engine/types';
import { ChartView } from '../../components/charts/Charts';
import { fixed } from '../../lib/stats';
import { formatDateTime } from '../../lib/format';
import { notifyError } from '../../App';
import { ResultTableView } from '../analysis/ResultView';

interface Props {
  project: ProjectState;
  onChange: (p: ProjectState) => void;
}

type Num = number | '';

interface EffectRow { d: Num; diff: Num; sd: Num; p1: Num; p2: Num; w: Num; r: Num }

interface FormState {
  design: PowerDesign;
  mode: PowerMode;
  alpha: Num;
  sides: PowerSides;
  powerPct: Num;
  dInput: 'd' | 'raw';
  effects: EffectRow[];
  ratio: Num;
  attritionPct: Num;
  n: Num;
  n1: Num;
  n2: Num;
  rows: Num;
  cols: Num;
  pRefPct: Num;
  source: string;
  sourceAnalysis: number | null;
}

const EMPTY_EFFECT: EffectRow = { d: '', diff: '', sd: '', p1: '', p2: '', w: '', r: '' };
const INITIAL: FormState = {
  design: 't_two', mode: 'sample_size', alpha: 0.05, sides: 'two-sided', powerPct: 80, dInput: 'd',
  effects: [{ ...EMPTY_EFFECT, d: 0.5 }], ratio: 1, attritionPct: 0, n: '', n1: '', n2: '', rows: 2, cols: 2,
  pRefPct: '', source: '', sourceAnalysis: null,
};

const MODE_HELP: Record<PowerMode, string> = {
  sample_size: 'Avant la collecte : combien de participants faut-il pour détecter l\'effet attendu ?',
  power: 'Avec un effectif donné (prévu ou obtenu) : quelle chance de détecter l\'effet attendu ?',
  effect: 'Avec un effectif donné : quel est le plus petit effet que l\'étude peut détecter ?',
};

const num = (v: Num) => (v === '' ? undefined : v);

/** Traduit le formulaire en demande pour le moteur (le moteur valide tout). Renvoie null si incomplet. */
function toRequest(f: FormState, info: PowerDesignInfo | undefined): PowerRequest | null {
  if (!info || f.alpha === '') return null;
  const req: PowerRequest = { design: f.design, mode: f.mode, alpha: f.alpha, effect_source: f.source };
  if (info.sided) req.alternative = f.sides;
  if (f.mode !== 'power') {
    if (f.powerPct === '') return null;
    req.power = f.powerPct / 100;
  }
  if (f.mode !== 'effect') {
    const effects: PowerEffect[] = [];
    for (const e of f.effects) {
      if (info.effect === 'd') {
        if (f.dInput === 'd') { if (e.d === '') return null; effects.push({ d: e.d }); }
        else { if (e.diff === '' || e.sd === '') return null; effects.push({ diff: e.diff, sd: e.sd }); }
      } else if (info.effect === 'h') {
        if (e.p1 === '' || e.p2 === '') return null;
        effects.push({ p1: e.p1 / 100, p2: e.p2 / 100 });
      } else if (info.effect === 'w') {
        if (e.w === '') return null;
        effects.push({ w: e.w });
      } else {
        if (e.r === '') return null;
        effects.push({ r: e.r });
      }
    }
    req.effects = effects;
  }
  if (f.design === 'chi2') {
    if (f.rows === '' || f.cols === '') return null;
    req.rows = f.rows;
    req.cols = f.cols;
  }
  if (f.mode === 'sample_size') {
    if (info.groups === 2) req.ratio = num(f.ratio) ?? 1;
    req.attrition = (num(f.attritionPct) ?? 0) / 100;
  } else if (info.groups === 2) {
    if (f.n1 === '' || f.n2 === '') return null;
    req.n1 = f.n1;
    req.n2 = f.n2;
  } else {
    if (f.n === '') return null;
    req.n = f.n;
  }
  if (f.mode === 'effect' && f.design === 'prop_two' && f.pRefPct !== '') req.p_ref = f.pRefPct / 100;
  if (f.sourceAnalysis !== null && f.mode === 'power') req.source_analysis = f.sourceAnalysis;
  return req;
}

/** Recharge un calcul enregistré dans le formulaire. */
function fromRequest(r: PowerRequest): FormState {
  const effects: EffectRow[] = (r.effects ?? []).map((e) => ({
    ...EMPTY_EFFECT, d: e.d ?? '', diff: e.diff ?? '', sd: e.sd ?? '',
    p1: e.p1 !== undefined ? round(e.p1 * 100) : '', p2: e.p2 !== undefined ? round(e.p2 * 100) : '',
    w: e.w ?? '', r: e.r ?? '',
  }));
  return {
    ...INITIAL, design: r.design, mode: r.mode, alpha: r.alpha ?? 0.05, sides: r.alternative ?? 'two-sided',
    powerPct: r.power !== undefined ? round(r.power * 100) : 80,
    dInput: (r.effects ?? []).some((e) => e.diff !== undefined) ? 'raw' : 'd',
    effects: effects.length ? effects : [{ ...EMPTY_EFFECT }], ratio: r.ratio ?? 1,
    attritionPct: r.attrition !== undefined ? round(r.attrition * 100) : 0, n: r.n ?? '', n1: r.n1 ?? '',
    n2: r.n2 ?? '', rows: r.rows ?? 2, cols: r.cols ?? 2, pRefPct: r.p_ref !== undefined ? round(r.p_ref * 100) : '',
    source: r.effect_source ?? '', sourceAnalysis: r.source_analysis ?? null,
  };
}

// Conversion d'affichage (proportion ↔ pourcentage), sans calcul statistique.
const round = (x: number) => Math.round(x * 1e6) / 1e6;

export function PowerPage({ project, onChange }: Props) {
  const [catalog, setCatalog] = useState<PowerCatalog | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL);
  const [result, setResult] = useState<PowerResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [computing, setComputing] = useState(false);
  const [saved, setSaved] = useState<PowerCalcSummary[]>([]);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [title, setTitle] = useState('');
  const [saving, setSaving] = useState(false);
  const [sourceLabel, setSourceLabel] = useState<string | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    Promise.all([call('power.catalog', {}), call('power.list', {}), call('analysis.list', {})])
      .then(([c, l, a]) => { setCatalog(c); setSaved(l); setAnalyses(a); })
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const info = catalog?.designs.find((d) => d.key === form.design);
  const request = useMemo(() => toRequest(form, info), [form, info]);

  // Calcul relancé à chaque modification (aperçu : rien n'est enregistré).
  useEffect(() => {
    if (!request) { setResult(null); setError(null); return; }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setComputing(true);
      call('power.compute', { request })
        .then((r) => { if (!cancelled) { setResult(r); setError(null); } })
        .catch((err) => { if (!cancelled) { setResult(null); setError(errorMessage(err)); } })
        .finally(() => !cancelled && setComputing(false));
    }, 300);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [request]);

  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));
  const setEffect = (i: number, patch: Partial<EffectRow>) =>
    setForm((f) => ({ ...f, effects: f.effects.map((e, j) => (j === i ? { ...e, ...patch } : e)) }));

  const methodsWithPower = useMemo(() => {
    const s = new Set<string>(['fisher']);
    catalog?.designs.forEach((d) => d.methods.forEach((m) => s.add(m)));
    return s;
  }, [catalog]);
  const eligible = analyses.filter((a) => methodsWithPower.has(a.method));

  const importAnalysis = async (id: string | null) => {
    if (!id) return;
    try {
      const r = await call('power.from_analysis', { analysis_id: Number(id) });
      const next = fromRequest({ ...r.request, effects: [] });
      const keep = form.design === r.request.design ? form.effects : [{ ...EMPTY_EFFECT }];
      setForm({ ...next, effects: keep, dInput: form.design === r.request.design ? form.dInput : 'd',
        source: form.source });
      setSourceLabel(r.analysis_title);
    } catch (err) {
      notifyError(err, 'Impossible de reprendre cette analyse');
    }
  };

  const save = async () => {
    if (!request) return;
    setSaving(true);
    try {
      const r = await call('power.save', { request, title: title.trim() || undefined });
      onChangeRef.current(r.project);
      setSaved(await call('power.list', {}));
      setTitle('');
      notifications.show({ color: 'teal', message: `Calcul enregistré : « ${r.calc.title} ».` });
    } catch (err) {
      notifyError(err, "Échec de l'enregistrement");
    } finally {
      setSaving(false);
    }
  };

  const open = async (id: number) => {
    try {
      const c = await call('power.get', { power_id: id });
      setForm(fromRequest(c.request));
      setSourceLabel(null);
      window.scrollTo?.(0, 0);
    } catch (err) {
      notifyError(err, 'Impossible d\'ouvrir ce calcul');
    }
  };

  const remove = async (id: number) => {
    try {
      onChangeRef.current(await call('power.delete', { power_id: id }));
      setSaved(await call('power.list', {}));
    } catch (err) {
      notifyError(err, 'Suppression impossible');
    }
  };

  if (!catalog) {
    return <Box p="xl">{error ? <Alert color="red">{error}</Alert> : <Loader size="sm" />}</Box>;
  }
  const two = info?.groups === 2;

  return (
    <Box p="xl" maw={1400}>
      <Group justify="space-between" align="flex-end" mb="lg">
        <div>
          <Title order={2}>Puissance et taille d'échantillon</Title>
          <Text c="dimmed" size="sm" maw={820}>
            Une estimation qui dépend entièrement de vos hypothèses (effet attendu, seuil, conditions du test) : elle ne
            garantit pas la validité de l'étude. Formules de Cohen (1988), identiques au paquet R pwr.
          </Text>
        </div>
        <Badge variant="light" size="lg">{project.power_count} calcul(s) enregistré(s)</Badge>
      </Group>

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <Paper withBorder p="md">
            <Stack gap="md">
              <SegmentedControl fullWidth value={form.mode} onChange={(v) => set({ mode: v as PowerMode })}
                data={[{ value: 'sample_size', label: 'Taille d\'échantillon' }, { value: 'power', label: 'Puissance' },
                  { value: 'effect', label: 'Plus petit effet' }]} />
              <Text size="xs" c="dimmed" mt={-8}>{MODE_HELP[form.mode]}</Text>
              <Select label="Type de test prévu" value={form.design} allowDeselect={false}
                data={catalog.designs.map((d) => ({ value: d.key, label: d.label }))}
                onChange={(v) => v && set({ design: v as PowerDesign, effects: [{ ...EMPTY_EFFECT }], dInput: 'd' })} />

              {form.mode === 'power' && eligible.length > 0 && (
                <Select label="Après la collecte : reprendre les effectifs d'une analyse" clearable searchable
                  placeholder="Choisir une analyse enregistrée" leftSection={<IconUpload size={16} />}
                  data={eligible.map((a) => ({ value: String(a.id), label: `${a.title} (${a.method_label})` }))}
                  value={form.sourceAnalysis !== null ? String(form.sourceAnalysis) : null}
                  onChange={(v) => { if (v) void importAnalysis(v); else { set({ sourceAnalysis: null }); setSourceLabel(null); } }}
                  description="Seuls les effectifs sont repris : l'effet reste celui que vous supposez, jamais l'effet observé." />
              )}

              <Group grow align="flex-start">
                <NumberInput label="Seuil α" value={form.alpha} decimalScale={4} step={0.01} min={0.0001} max={0.2}
                  decimalSeparator="," onChange={(v) => set({ alpha: v === '' ? '' : Number(v) })} />
                {form.mode !== 'power' && (
                  <NumberInput label="Puissance visée (%)" value={form.powerPct} min={50} max={99.9} step={5}
                    decimalSeparator="," onChange={(v) => set({ powerPct: v === '' ? '' : Number(v) })} />
                )}
              </Group>
              {info?.sided && (
                <SegmentedControl value={form.sides} onChange={(v) => set({ sides: v as PowerSides })}
                  data={catalog.alternatives.map((a) => ({ value: a.key, label: a.key === 'two-sided' ? 'Bilatéral'
                    : 'Unilatéral (sens attendu)' }))} />
              )}
              {form.design === 'chi2' && (
                <Group grow>
                  <NumberInput label="Lignes du tableau" value={form.rows} min={2} max={50} allowDecimal={false}
                    onChange={(v) => set({ rows: v === '' ? '' : Number(v) })} />
                  <NumberInput label="Colonnes (1 : ajustement)" value={form.cols} min={1} max={50} allowDecimal={false}
                    onChange={(v) => set({ cols: v === '' ? '' : Number(v) })} />
                </Group>
              )}

              {form.mode !== 'effect' && info && (
                <EffectsEditor info={info} form={form} max={catalog.max_effects} set={set} setEffect={setEffect} />
              )}

              {form.mode === 'sample_size' ? (
                <Group grow align="flex-start">
                  {two && (
                    <NumberInput label="Rapport n₂ / n₁" value={form.ratio} min={0.1} max={10} step={0.5}
                      decimalSeparator="," description="1 : groupes de même taille"
                      onChange={(v) => set({ ratio: v === '' ? '' : Number(v) })} />
                  )}
                  <NumberInput label="Pertes prévues (%)" value={form.attritionPct} min={0} max={90}
                    decimalSeparator="," description="Abandons, réponses inexploitables"
                    onChange={(v) => set({ attritionPct: v === '' ? '' : Number(v) })} />
                </Group>
              ) : two ? (
                <Group grow>
                  <NumberInput label="Effectif du groupe 1" value={form.n1} min={2} allowDecimal={false}
                    onChange={(v) => set({ n1: v === '' ? '' : Number(v) })} />
                  <NumberInput label="Effectif du groupe 2" value={form.n2} min={2} allowDecimal={false}
                    onChange={(v) => set({ n2: v === '' ? '' : Number(v) })} />
                </Group>
              ) : (
                <NumberInput label={form.design === 't_paired' ? 'Nombre de paires' : 'Effectif total'} value={form.n}
                  min={2} allowDecimal={false} onChange={(v) => set({ n: v === '' ? '' : Number(v) })} />
              )}
              {form.mode === 'effect' && form.design === 'prop_two' && (
                <NumberInput label="Proportion de référence dans le groupe 2 (%), facultatif" value={form.pRefPct}
                  min={0.1} max={99.9} decimalSeparator="," onChange={(v) => set({ pRefPct: v === '' ? '' : Number(v) })}
                  description="Pour traduire h en proportions" />
              )}
              {sourceLabel && form.mode === 'power' && (
                <Text size="xs" c="dimmed">Effectifs repris de l'analyse « {sourceLabel} ».</Text>
              )}
              {form.mode !== 'effect' && (
                <Textarea label="D'où vient l'effet attendu ?" autosize minRows={2} maxLength={2000}
                  placeholder="Ex. : étude de Martin (2020), étude pilote, plus petit effet utile en pratique…"
                  value={form.source} onChange={(e) => set({ source: e.currentTarget.value })} />
              )}
            </Stack>
          </Paper>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Stack gap="md">
            {error && <Alert color="orange" icon={<IconAlertTriangle size={18} />}>{error}</Alert>}
            {!request && !error && (
              <Alert color="gray" icon={<IconInfoCircle size={18} />}>Complétez le formulaire pour lancer le calcul.</Alert>
            )}
            {result && <ResultPanel result={result} computing={computing} />}
            {result && (
              <Paper withBorder p="md">
                <Group align="flex-end" wrap="nowrap">
                  <TextInput label="Enregistrer ce calcul dans le projet" placeholder={result.title} style={{ flex: 1 }}
                    value={title} maxLength={200} onChange={(e) => setTitle(e.currentTarget.value)} />
                  <Button leftSection={<IconDeviceFloppy size={16} />} loading={saving} onClick={() => void save()}>
                    Enregistrer
                  </Button>
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  Le calcul et ses hypothèses sont conservés dans le projet, repris dans le rapport et citables dans le
                  plan d'analyse.
                </Text>
              </Paper>
            )}
            <SavedList saved={saved} onOpen={(id) => void open(id)} onDelete={(id) => void remove(id)} />
          </Stack>
        </Grid.Col>
      </Grid>
    </Box>
  );
}

function EffectsEditor({ info, form, max, set, setEffect }: {
  info: PowerDesignInfo; form: FormState; max: number;
  set: (p: Partial<FormState>) => void; setEffect: (i: number, p: Partial<EffectRow>) => void;
}) {
  const e = info.effect;
  const label = info.effect_label;
  const benchmarks = () => set({ effects: info.benchmarks.map((b) => ({ ...EMPTY_EFFECT, [e]: b })), dInput: 'd' });
  return (
    <Stack gap={6}>
      <Group justify="space-between">
        <Text size="sm" fw={500}>Effet attendu {form.effects.length > 1 ? '(effets comparés)' : ''}</Text>
        {e !== 'h' && (
          <Tooltip label={`Repères de Cohen : ${info.benchmarks.map((b) => fixed(b, 1)).join(' / ')}. À n'utiliser qu'à défaut d'un effet tiré de la littérature.`} multiline w={280}>
            <Button size="compact-xs" variant="subtle" onClick={benchmarks}>Comparer petit, moyen, grand</Button>
          </Tooltip>
        )}
      </Group>
      {e === 'd' && (
        <SegmentedControl size="xs" value={form.dInput} onChange={(v) => set({ dInput: v as 'd' | 'raw' })}
          data={[{ value: 'd', label: label.startsWith('dz') ? 'dz directement' : 'd directement' },
            { value: 'raw', label: 'Différence et écart-type' }]} />
      )}
      {form.effects.map((row, i) => (
        <Group key={i} gap="xs" wrap="nowrap" align="flex-end">
          {e === 'd' && form.dInput === 'd' && (
            <NumberInput label={i === 0 ? label : undefined} aria-label={label} value={row.d} step={0.1}
              decimalScale={4} decimalSeparator="," style={{ flex: 1 }}
              onChange={(v) => setEffect(i, { d: v === '' ? '' : Number(v) })} />
          )}
          {e === 'd' && form.dInput === 'raw' && (
            <>
              <NumberInput label={i === 0 ? (info.key === 't_paired' ? 'Différence moyenne attendue' : 'Différence de moyennes') : undefined}
                aria-label="Différence attendue" value={row.diff} decimalSeparator="," style={{ flex: 1 }}
                onChange={(v) => setEffect(i, { diff: v === '' ? '' : Number(v) })} />
              <NumberInput label={i === 0 ? (info.key === 't_paired' ? 'Écart-type des différences' : 'Écart-type') : undefined}
                aria-label="Écart-type" value={row.sd} min={0} decimalSeparator="," style={{ flex: 1 }}
                onChange={(v) => setEffect(i, { sd: v === '' ? '' : Number(v) })} />
            </>
          )}
          {e === 'h' && (
            <>
              <NumberInput label={i === 0 ? 'Groupe 1 (%)' : undefined} aria-label="Proportion groupe 1 (%)"
                value={row.p1} min={0.1} max={99.9} decimalSeparator="," style={{ flex: 1 }}
                onChange={(v) => setEffect(i, { p1: v === '' ? '' : Number(v) })} />
              <NumberInput label={i === 0 ? 'Groupe 2 (%)' : undefined} aria-label="Proportion groupe 2 (%)"
                value={row.p2} min={0.1} max={99.9} decimalSeparator="," style={{ flex: 1 }}
                onChange={(v) => setEffect(i, { p2: v === '' ? '' : Number(v) })} />
            </>
          )}
          {(e === 'w' || e === 'r') && (
            <NumberInput label={i === 0 ? label : undefined} aria-label={label} value={row[e]} step={0.05}
              decimalScale={4} decimalSeparator="," style={{ flex: 1 }}
              onChange={(v) => setEffect(i, { [e]: v === '' ? '' : Number(v) })} />
          )}
          <ActionIcon variant="subtle" color="gray" mb={4} disabled={form.effects.length === 1}
            aria-label="Retirer cet effet"
            onClick={() => set({ effects: form.effects.filter((_, j) => j !== i) })}>
            <IconTrash size={16} />
          </ActionIcon>
        </Group>
      ))}
      <Button size="compact-sm" variant="light" leftSection={<IconPlus size={14} />} w="fit-content"
        disabled={form.effects.length >= max}
        onClick={() => set({ effects: [...form.effects, { ...EMPTY_EFFECT }] })}>
        Comparer avec un autre effet
      </Button>
    </Stack>
  );
}

function ResultPanel({ result, computing }: { result: PowerResult; computing: boolean }) {
  const first = result.rows[0];
  const two = first.n2 !== null;
  const pct = (x: number) => `${fixed(Math.floor(x * 1000 + 1e-9) / 10, 1)} %`;
  return (
    <Paper withBorder p="md" style={{ opacity: computing ? 0.6 : 1 }}>
      <Stack gap="md">
        <Group justify="space-between" wrap="nowrap">
          <Text fw={650}>{result.title}</Text>
          {computing && <Loader size="xs" />}
        </Group>
        <Group gap="xl">
          {result.mode === 'sample_size' && (
            <Big label={two ? (first.n1 === first.n2 ? 'Par groupe' : 'Groupes 1 et 2') : 'Effectif nécessaire'}
              value={two ? (first.n1 === first.n2 ? String(first.n1) : `${first.n1} et ${first.n2}`) : String(first.n1)} />
          )}
          {result.mode === 'sample_size' && two && <Big label="Total" value={String(first.n_total)} />}
          {result.mode === 'sample_size' && first.recruit_total !== undefined && first.recruit_total !== first.n_total && (
            <Big label="À recruter (pertes)" value={String(first.recruit_total)} />
          )}
          {result.mode !== 'effect' && (
            <Big label={result.mode === 'sample_size' ? 'Puissance atteinte' : 'Puissance'} value={pct(first.power)}
              color={result.mode === 'power' && first.power < 0.8 ? 'orange.8' : 'brand.8'} />
          )}
          {result.mode === 'effect' && <Big label="Plus petit effet détectable" value={fixed(first.effect, 3)} />}
        </Group>
        {result.rows.length > 1 && <Text size="xs" c="dimmed">Valeurs du premier effet ; tous les effets sont dans le tableau.</Text>}
        <Box>
          <Text size="sm" fw={600} mb={4}>Lecture</Text>
          <Stack gap={4}>
            {result.interpretation.map((t, i) => <Text key={i} size="sm">{t}</Text>)}
          </Stack>
          <Text size="xs" c="dimmed" mt={4}>Phrases produites par des règles fixes à partir du calcul, sans intelligence artificielle.</Text>
        </Box>
        {result.diagnostics.filter((d) => d.level !== 'information').map((d, i) => (
          <Alert key={i} color={d.level === 'important' ? 'orange' : 'yellow'} title={d.title}
            icon={<IconAlertTriangle size={18} />}>{d.detail}</Alert>
        ))}
        {result.tables.map((t, i) => <ResultTableView key={i} table={t} />)}
        {result.charts.map((c, i) => <ChartView key={i} chart={c} />)}
        <Box>
          <Text size="sm" fw={600} mb={4}>Hypothèses du calcul</Text>
          <List size="sm" spacing={2}>
            {result.assumptions.map((a, i) => <List.Item key={i}>{a}</List.Item>)}
          </List>
        </Box>
        {result.diagnostics.filter((d) => d.level === 'information').map((d, i) => (
          <Alert key={i} color="blue" variant="light" title={d.title} icon={<IconInfoCircle size={18} />}>{d.detail}</Alert>
        ))}
        <Text size="xs" c="dimmed">{result.disclaimer} {result.method_note} Équivalent R : {result.r_equivalent}.</Text>
      </Stack>
    </Paper>
  );
}

function Big({ label, value, color = 'brand.8' }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <Text size="xs" c="dimmed">{label}</Text>
      <Text fw={700} fz={28} c={color} style={{ fontVariantNumeric: 'tabular-nums' }}>{value}</Text>
    </div>
  );
}

function SavedList({ saved, onOpen, onDelete }: {
  saved: PowerCalcSummary[]; onOpen: (id: number) => void; onDelete: (id: number) => void;
}) {
  if (saved.length === 0) return null;
  return (
    <Paper withBorder p="md">
      <Text fw={600} mb="sm">Calculs enregistrés dans le projet</Text>
      <Stack gap="xs">
        {saved.map((c) => (
          <Group key={c.id} justify="space-between" wrap="nowrap" align="flex-start">
            <Group gap="sm" wrap="nowrap" align="flex-start" style={{ minWidth: 0 }}>
              <ThemeIcon variant="light" size="sm" mt={2}>{c.id}</ThemeIcon>
              <Box style={{ minWidth: 0 }}>
                <Text size="sm" fw={550}>{c.title}</Text>
                <Text size="xs" c="dimmed" lineClamp={2}>{c.headline}</Text>
                <Group gap={6} mt={2}>
                  <Text size="xs" c="dimmed">{formatDateTime(c.created_at)}</Text>
                  {c.locked_in_plan.length > 0 && (
                    <Badge size="xs" variant="light" color="teal">Cité dans le plan verrouillé</Badge>
                  )}
                </Group>
              </Box>
            </Group>
            <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
              <Button size="compact-xs" variant="light" onClick={() => onOpen(c.id)}>Ouvrir</Button>
              <Tooltip label={c.locked_in_plan.length ? 'Cité dans un plan verrouillé : non supprimable' : 'Supprimer'}>
                <ActionIcon variant="subtle" color="red" disabled={c.locked_in_plan.length > 0}
                  aria-label={`Supprimer le calcul ${c.title}`} onClick={() => onDelete(c.id)}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
          </Group>
        ))}
      </Stack>
    </Paper>
  );
}
