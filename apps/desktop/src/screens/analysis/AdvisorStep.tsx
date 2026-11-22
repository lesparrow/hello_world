import { useEffect, useState } from 'react';
import {
  Alert, Badge, Button, Checkbox, Divider, Grid, Group, List, MultiSelect, Paper, Radio, SegmentedControl, Select,
  SimpleGrid, Stack, Text, Textarea, ThemeIcon, UnstyledButton,
} from '@mantine/core';
import {
  IconAlertTriangle, IconArrowLeft, IconArrowRight, IconArrowsLeftRight, IconBulb, IconChartDots, IconListNumbers,
  IconQuestionMark, IconUsers,
} from '@tabler/icons-react';
import { call, errorMessage } from '../../engine/client';
import type {
  Advice, AdviceObjective, AdviceRequest, AnalysisParams, AnalysisPurpose, ChoiceInput, Variable,
} from '../../engine/types';
import { exclusionReason } from './variables';

/** État du parcours guidé, conservé par la fenêtre quand on revient à l'assistant. */
export interface GuideState {
  objective: AdviceObjective | null;
  vars: Record<string, string | string[]>;
  levels: string[] | null;
  independent: boolean;
  purpose: AnalysisPurpose | null;
  hypothesis: number | null;
  advice: Advice | null;
  selected: string | null; // 'rec' ou 'alt-<i>'
  reason: string;
}

export const EMPTY_GUIDE: GuideState = {
  objective: null, vars: {}, levels: null, independent: false, purpose: null, hypothesis: null, advice: null,
  selected: null, reason: '',
};

export interface GuidedChoice {
  method: string;
  params: AnalysisParams;
  choice: ChoiceInput;
  recommended: string | null;
  followed: boolean;
}

const OBJECTIVES: { value: AdviceObjective; label: string; detail: string; icon: typeof IconUsers }[] = [
  { value: 'describe', label: 'Décrire', detail: 'Résumer une ou plusieurs variables de mon échantillon.',
    icon: IconListNumbers },
  { value: 'compare_groups', label: 'Comparer des groupes', detail: 'Les individus de groupes différents (hommes / femmes, '
    + 'traité / témoin) diffèrent-ils ?', icon: IconUsers },
  { value: 'compare_paired', label: 'Comparer avant / après', detail: 'Deux mesures prises sur les mêmes individus '
    + '(avant / après, deux conditions).', icon: IconArrowsLeftRight },
  { value: 'relate', label: 'Étudier un lien', detail: 'Deux variables évoluent-elles ensemble, ou sont-elles associées ?',
    icon: IconChartDots },
];

const SLOTS: Record<AdviceObjective, { name: string; label: string; multiple?: boolean; help?: string }[]> = {
  describe: [{ name: 'variables', label: 'Variables à décrire', multiple: true,
    help: 'Ajoutez une variable qualitative pour décrire les variables quantitatives par groupe.' }],
  compare_groups: [
    { name: 'outcome', label: 'Variable comparée (ce que vous mesurez)' },
    { name: 'group', label: 'Variable qui définit les groupes' },
  ],
  compare_paired: [
    { name: 'first', label: 'Première mesure (par exemple : avant)' },
    { name: 'second', label: 'Seconde mesure (par exemple : après)' },
  ],
  relate: [
    { name: 'x', label: 'Première variable' },
    { name: 'y', label: 'Seconde variable' },
  ],
};

interface Props {
  datasetId: number;
  versionId: number | null;
  variables: Variable[];
  hypotheses: string[];
  value: GuideState;
  onChange: (next: GuideState) => void;
  onProceed: (c: GuidedChoice) => void;
  onDirect: () => void;
  header: React.ReactNode;
}

export function buildRequest(g: GuideState): AdviceRequest | null {
  if (!g.objective) return null;
  return {
    objective: g.objective,
    variables: g.vars,
    ...(g.objective === 'compare_groups' && g.levels ? { levels: g.levels } : {}),
    ...(g.objective === 'compare_groups' ? { independent: g.independent } : {}),
    purpose: g.purpose,
    hypothesis: g.hypothesis,
  };
}

function isComplete(g: GuideState): boolean {
  if (!g.objective) return false;
  return SLOTS[g.objective].every((s) => {
    const v = g.vars[s.name];
    return s.multiple ? Array.isArray(v) && v.length > 0 : typeof v === 'string' && v !== '';
  });
}

export function AdvisorStep({
  datasetId, versionId, variables, hypotheses, value: g, onChange, onProceed, onDirect, header,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [levels, setLevels] = useState<{ value: string; label: string; count: number }[] | null>(null);

  // Toute modification des informations rend la recommandation précédente caduque.
  const update = (patch: Partial<GuideState>) => {
    setError(null);
    onChange({ ...g, ...patch, advice: null, selected: null, reason: '' });
  };

  const groupKey = g.objective === 'compare_groups' && typeof g.vars.group === 'string' ? g.vars.group : null;
  useEffect(() => {
    if (!groupKey) { setLevels(null); return; }
    let cancelled = false;
    call('analysis.levels', { dataset_id: datasetId, version_id: versionId, key: groupKey })
      .then((lv) => { if (!cancelled) setLevels(lv); })
      .catch(() => { if (!cancelled) setLevels(null); });
    return () => { cancelled = true; };
  }, [groupKey, datasetId, versionId]);

  const ask = async () => {
    const request = buildRequest(g);
    if (!request) return;
    setBusy(true);
    setError(null);
    try {
      const advice = await call('analysis.advise', { dataset_id: datasetId, version_id: versionId, request });
      onChange({ ...g, advice, selected: advice.recommendation ? 'rec' : null, reason: '' });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const advice = g.advice;
  const options = advice ? [
    ...(advice.recommendation ? [{ key: 'rec', method: advice.recommendation.method,
      label: advice.recommendation.label, params: advice.recommendation.params, when: '', available: true }] : []),
    ...advice.alternatives.map((a, i) => ({ key: `alt-${i}`, ...a })),
  ] : [];
  const selected = options.find((o) => o.key === g.selected) ?? null;
  const deviates = Boolean(selected && advice && selected.method !== advice.recommendation?.method);
  const needReason = deviates && g.reason.trim() === '';

  const proceed = () => {
    if (!selected || !selected.method || !advice) return;
    const request = buildRequest(g)!;
    onProceed({
      method: selected.method,
      params: { ...selected.params },
      recommended: advice.recommendation?.method ?? null,
      followed: !deviates,
      choice: {
        mode: 'assistant', request, purpose: g.purpose, hypothesis: g.hypothesis,
        ...(g.reason.trim() ? { reason: g.reason.trim() } : {}),
      },
    });
  };

  const varData = variables.map((v) => {
    const reason = exclusionReason(v, 'any');
    const desc = `${v.type_label}, ${v.level_label.toLowerCase()}`;
    return { value: v.key, label: reason ? `${v.name} (${reason})` : `${v.name} · ${desc}`, disabled: Boolean(reason) };
  });

  return (
    <Grid gap="lg">
      <Grid.Col span={{ base: 12, md: 6 }}>
        <Stack gap="sm">
          {header}
          <Divider label="1. Que cherchez-vous à faire ?" labelPosition="left" />
          <SimpleGrid cols={2} spacing="xs">
            {OBJECTIVES.map((o) => {
              const active = g.objective === o.value;
              return (
                <UnstyledButton key={o.value} aria-pressed={active} aria-label={o.label}
                  onClick={() => update({ objective: o.value, vars: {}, levels: null })}>
                  <Paper withBorder p="xs" h="100%" className="method-card"
                    style={active ? { borderColor: 'var(--mantine-color-brand-6)', background: 'var(--mantine-color-brand-0)' } : undefined}>
                    <Group gap={6} wrap="nowrap">
                      <ThemeIcon variant={active ? 'filled' : 'light'} size="sm"><o.icon size={14} /></ThemeIcon>
                      <Text size="sm" fw={600}>{o.label}</Text>
                    </Group>
                    <Text size="xs" c="dimmed" mt={4}>{o.detail}</Text>
                  </Paper>
                </UnstyledButton>
              );
            })}
          </SimpleGrid>

          {g.objective && (
            <>
              <Divider label="2. Quelles variables ?" labelPosition="left" />
              {SLOTS[g.objective].map((s) => s.multiple ? (
                <MultiSelect key={s.name} label={s.label} description={s.help} data={varData} searchable maxValues={30}
                  value={(g.vars[s.name] as string[]) ?? []} placeholder="Choisir une ou plusieurs variables"
                  nothingFoundMessage="Aucune variable"
                  onChange={(v) => update({ vars: { ...g.vars, [s.name]: v } })} />
              ) : (
                <Select key={s.name} label={s.label} data={varData} searchable placeholder="Choisir une variable"
                  value={(g.vars[s.name] as string) ?? null} nothingFoundMessage="Aucune variable"
                  onChange={(v) => {
                    const vars = { ...g.vars };
                    if (v) vars[s.name] = v; else delete vars[s.name];
                    update({ vars, ...(s.name === 'group' ? { levels: null } : {}) });
                  }} />
              ))}
              {g.objective === 'compare_groups' && levels && levels.length > 2 && (
                <MultiSelect label="Deux groupes à comparer (facultatif)" maxValues={2}
                  description={`${levels.length} groupes : ne choisissez deux groupes précis que si cette comparaison était prévue.`}
                  data={levels.map((l) => ({ value: l.value, label: `${l.label} (n = ${l.count})` }))}
                  value={g.levels ?? []}
                  onChange={(v) => update({ levels: v.length ? v : null })} />
              )}
              {g.objective === 'compare_groups' && (
                <Checkbox checked={g.independent} onChange={(e) => update({ independent: e.currentTarget.checked })}
                  label="Chaque individu n'appartient qu'à un seul groupe (groupes indépendants)" />
              )}

              <Divider label="3. Contexte" labelPosition="left" />
              <div>
                <Text size="sm" fw={500} mb={4}>Nature de l'analyse</Text>
                <SegmentedControl size="xs" value={g.purpose ?? 'none'}
                  data={[{ value: 'none', label: 'Non précisée' }, { value: 'confirmatoire', label: 'Confirmatoire' },
                    { value: 'exploratoire', label: 'Exploratoire' }]}
                  onChange={(v) => update({ purpose: v === 'none' ? null : v as AnalysisPurpose })} />
                <Text size="xs" c="dimmed" mt={4}>
                  Confirmatoire : l'hypothèse et la méthode ont été fixées avant de voir les données.
                </Text>
              </div>
              {hypotheses.length > 0 && (
                <Select label="Hypothèse de l'étude mise à l'épreuve (facultatif)" clearable
                  data={hypotheses.map((h, i) => ({ value: String(i), label: `H${i + 1} : ${h}` }))}
                  value={g.hypothesis === null ? null : String(g.hypothesis)}
                  onChange={(v) => update({ hypothesis: v === null ? null : Number(v) })} />
              )}
            </>
          )}

          {error && <Alert color="red" variant="light" title="Recommandation impossible">{error}</Alert>}
          <Group justify="space-between" mt="xs">
            <Button variant="default" leftSection={<IconArrowLeft size={16} />} onClick={onDirect}>
              Choisir moi-même
            </Button>
            <Button variant={advice ? 'light' : 'filled'} leftSection={<IconBulb size={16} />} loading={busy}
              disabled={!isComplete(g)} onClick={ask}>
              {advice ? 'Recalculer la recommandation' : 'Obtenir une recommandation'}
            </Button>
          </Group>
        </Stack>
      </Grid.Col>

      <Grid.Col span={{ base: 12, md: 6 }}>
        {!advice ? (
          <Paper withBorder p="md" bg="var(--mantine-color-gray-0)">
            <Group gap={6} mb="xs">
              <IconQuestionMark size={16} />
              <Text size="sm" fw={650}>Comment fonctionne l'assistant ?</Text>
            </Group>
            <List size="sm" spacing={4}>
              <List.Item>Il lit le dictionnaire des variables (type, niveau de mesure) et le plan d'étude que vous indiquez.</List.Item>
              <List.Item>Il examine les effectifs, le nombre de groupes, l'asymétrie et les valeurs extrêmes.</List.Item>
              <List.Item>Il ne calcule aucun test et ne choisit jamais une méthode d'après un test de normalité.</List.Item>
              <List.Item>Ses règles sont fixes et versionnées : la même situation donne toujours la même recommandation.</List.Item>
              <List.Item>Vous restez libre de choisir une autre méthode ; votre justification est enregistrée.</List.Item>
            </List>
          </Paper>
        ) : (
          <AdvicePanel advice={advice} options={options} selected={g.selected} reason={g.reason}
            deviates={deviates} needReason={needReason}
            onSelect={(k) => onChange({ ...g, selected: k })}
            onReason={(r) => onChange({ ...g, reason: r })}
            onProceed={proceed} />
        )}
      </Grid.Col>
    </Grid>
  );
}

function Section({ title, items, color }: { title: string; items: string[]; color?: string }) {
  if (items.length === 0) return null;
  return (
    <div>
      <Text size="xs" fw={650} tt="uppercase" c={color ?? 'dimmed'}>{title}</Text>
      <List size="sm" spacing={2}>{items.map((c) => <List.Item key={c}>{c}</List.Item>)}</List>
    </div>
  );
}

interface Option { key: string; method: string | null; label: string; params: AnalysisParams; when: string; available: boolean }

function AdvicePanel({ advice, options, selected, reason, deviates, needReason, onSelect, onReason, onProceed }: {
  advice: Advice; options: Option[]; selected: string | null; reason: string; deviates: boolean; needReason: boolean;
  onSelect: (k: string) => void; onReason: (r: string) => void; onProceed: () => void;
}) {
  const rec = advice.recommendation;
  return (
    <Stack gap="sm">
      {advice.blocking && (
        <Alert color="orange" variant="light" icon={<IconAlertTriangle size={16} />} title="Pas de recommandation possible">
          {advice.blocking}
        </Alert>
      )}
      {rec && (
        <Paper withBorder p="md" style={{ borderColor: 'var(--mantine-color-brand-4)' }}>
          <Group justify="space-between" mb={6}>
            <Text size="xs" fw={650} tt="uppercase" c="brand.7">Méthode recommandée</Text>
            <Badge variant="outline" color="gray" tt="none" size="xs">Règles {advice.rules_version}</Badge>
          </Group>
          <Text fw={650} size="lg" mb="xs">{rec.label}</Text>
          <Stack gap="xs">
            <Section title="Pourquoi" items={rec.reasons} />
            <Section title="Conditions nécessaires" items={rec.conditions} />
            <Section title="À examiner dans le résultat" items={rec.checks} />
            <Section title="Limites" items={rec.limits} />
          </Stack>
        </Paper>
      )}
      <Section title="Ce que l'assistant a observé" items={advice.observations} />
      {advice.missing_information.length > 0 && (
        <Alert color="yellow" variant="light" title="Informations manquantes ou à vérifier">
          <List size="sm" spacing={2}>{advice.missing_information.map((m) => <List.Item key={m}>{m}</List.Item>)}</List>
        </Alert>
      )}

      {options.length > 0 && (
        <Radio.Group label="Méthode retenue" value={selected} onChange={onSelect}>
          <Stack gap={6} mt={6}>
            {options.map((o) => (
              <Radio key={o.key} value={o.key} disabled={!o.available}
                label={<>
                  <Text size="sm" span fw={o.key === 'rec' ? 650 : 500}>{o.label}</Text>
                  {o.key === 'rec' && <Badge size="xs" ml={6} variant="light">recommandée</Badge>}
                  {!o.available && <Badge size="xs" ml={6} color="gray" variant="light">pas encore disponible</Badge>}
                </>}
                description={o.when || undefined} />
            ))}
          </Stack>
        </Radio.Group>
      )}
      {deviates && (
        <Textarea label="Pourquoi choisissez-vous cette méthode ?" required autosize minRows={2} maxLength={2000}
          description="Obligatoire : cette justification est enregistrée avec l'analyse et dans le journal."
          placeholder="Par exemple : méthode imposée par le protocole, comparaison avec une étude antérieure…"
          value={reason} onChange={(e) => onReason(e.currentTarget.value)}
          error={needReason ? 'Indiquez la raison de ce choix.' : undefined} />
      )}
      <Text size="xs" c="dimmed">{advice.principle}</Text>
      <Group justify="flex-end">
        <Button rightSection={<IconArrowRight size={16} />} onClick={onProceed}
          disabled={!selected || needReason || !options.find((o) => o.key === selected)?.method}>
          Configurer et calculer
        </Button>
      </Group>
    </Stack>
  );
}
