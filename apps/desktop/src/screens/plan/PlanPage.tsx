import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActionIcon, Alert, Badge, Box, Button, Grid, Group, List, Loader, Modal, NumberInput, Paper, SegmentedControl, Select,
  Stack, TagsInput, Text, Textarea, Timeline, Title, Tooltip,
} from '@mantine/core';
import {
  IconArrowBackUp, IconCopy, IconHistory, IconInfoCircle, IconLock, IconLockOpen, IconPlayerPlay, IconPlus, IconTrash,
} from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { AiMarkBadge, AiMarksBanner, CopilotButton, useAiMarks, useCopilotEnv } from '../../components/ai/Copilot';
import { call, errorMessage } from '../../engine/client';
import type {
  Catalog, PlanContent, PlanRunResult, PlanItem, PlanState, PlanVersion, PowerCalcSummary, ProjectState,
} from '../../engine/types';
import { HypothesesEditor } from '../../components/HypothesesEditor';
import { formatDateTime } from '../../lib/format';
import { notifyError } from '../../App';

interface Props {
  project: ProjectState;
  variableNames: string[];
  onChange: (p: ProjectState) => void;
}

const NEW_ITEM: PlanItem = {
  id: null, method: '', variables: {}, hypothesis: null, role: 'principale', alternative: 'two-sided',
  description: '', power_calc: null,
};

const ALTERNATIVES = [
  { value: 'two-sided', label: 'Bilatéral' }, { value: 'greater', label: 'Unilatéral (supérieur)' },
  { value: 'less', label: 'Unilatéral (inférieur)' },
];

const sameContent = (a: PlanContent, b: PlanContent) => JSON.stringify(a) === JSON.stringify(b);

export function PlanPage({ project, variableNames, onChange }: Props) {
  const [plan, setPlan] = useState<PlanState | null>(null);
  const [content, setContent] = useState<PlanContent | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [calcs, setCalcs] = useState<PowerCalcSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [lockOpen, setLockOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [viewed, setViewed] = useState<(PlanVersion & { content: PlanContent }) | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const contentRef = useRef(content);
  contentRef.current = content;
  const env = useCopilotEnv();
  const aiMarks = useAiMarks('plan');
  const [runResult, setRunResult] = useState<PlanRunResult | null>(null);

  // Rechargé aussi après une proposition de l'IA appliquée ou annulée.
  useEffect(() => {
    Promise.all([call('plan.get', {}), call('analysis.catalog', {}), call('power.list', {})])
      .then(([p, c, l]) => { setPlan(p); resetFrom(p); setCatalog(c); setCalcs(l); })
      .catch((err) => setError(errorMessage(err)));
  }, [env?.marksVersion]);

  const lastSent = useRef<string>('');
  const [sentVersion, setSentVersion] = useState(0);
  const resetFrom = (p: PlanState) => {
    const c = p.current?.content ?? p.empty;
    lastSent.current = JSON.stringify(c);
    setContent(c);
    setSentVersion((n) => n + 1);
  };

  // Enregistrement automatique du brouillon (le moteur valide et attribue les références A1, A2…).
  useEffect(() => {
    if (!content || !plan) return;
    const text = JSON.stringify(content);
    if (text === lastSent.current) return;
    if (content.analyses.some((it) => !it.method)) return; // analyse en cours de saisie : méthode à choisir
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setSaving(true);
      call('plan.save', { content })
        .then((r) => {
          if (cancelled) return;
          lastSent.current = text;
          setPlan(r.plan);
          setError(null);
          onChangeRef.current(r.project);
          const fresh = r.plan.current?.content;
          const now = contentRef.current;
          if (fresh && now && now.analyses.some((it) => !it.id)) {
            // On reprend seulement les références attribuées, sans toucher à la saisie en cours.
            const patched = { ...now, analyses: now.analyses.map((it, i) => (it.id ? it
              : { ...it, id: fresh.analyses[i]?.id ?? null })) };
            if (sameContent(now, content)) lastSent.current = JSON.stringify(patched);
            setContent(patched);
          }
          setSentVersion((n) => n + 1);
        })
        .catch((err) => !cancelled && setError(errorMessage(err)))
        .finally(() => !cancelled && setSaving(false));
    }, 700);
    return () => { cancelled = true; window.clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [content]);

  const methods = useMemo(() => (catalog ? catalog.methods.map((m) => ({
    value: m.key, label: m.label, group: catalog.families[m.family] ?? m.family,
  })) : []), [catalog]);
  const grouped = useMemo(() => {
    const g = new Map<string, { value: string; label: string }[]>();
    methods.forEach((m) => g.set(m.group, [...(g.get(m.group) ?? []), { value: m.value, label: m.label }]));
    return [...g.entries()].map(([group, items]) => ({ group, items }));
  }, [methods]);

  if (!plan || !content || !catalog) {
    return <Box p="xl">{error ? <Alert color="red">{error}</Alert> : <Loader size="sm" />}</Box>;
  }

  const current = plan.current;
  const locked = plan.locked;
  const isDraft = current?.status === 'brouillon';
  const pendingLocal = sentVersion >= 0 && JSON.stringify(content) !== lastSent.current;
  const set = (patch: Partial<PlanContent>) => setContent({ ...content, ...patch });
  const setItem = (i: number, patch: Partial<PlanItem>) =>
    set({ analyses: content.analyses.map((it, j) => (j === i ? { ...it, ...patch } : it)) });

  const lock = async () => {
    setBusy(true);
    try {
      const r = await call('plan.lock', { reason });
      setPlan(r.plan);
      resetFrom(r.plan);
      onChange(r.project);
      setLockOpen(false);
      setReason('');
    } catch (err) {
      notifyError(err, 'Verrouillage impossible');
    } finally {
      setBusy(false);
    }
  };

  const discard = async () => {
    setBusy(true);
    try {
      const r = await call('plan.discard', {});
      setPlan(r.plan);
      resetFrom(r.plan);
      onChange(r.project);
    } catch (err) {
      notifyError(err, 'Abandon impossible');
    } finally {
      setBusy(false);
    }
  };

  const runAll = async () => {
    if (!env?.datasetId) return;
    setBusy(true);
    try {
      const r = await call('plan.run_all', { dataset_id: env.datasetId, version_id: env.versionId });
      setRunResult(r.run);
      onChange(r.project);
      notifications.show({ color: r.run.ran ? 'teal' : 'gray',
        message: `${r.run.ran} analyse(s) prévue(s) calculée(s) par le moteur.` });
    } catch (err) {
      notifyError(err, 'Lancement impossible');
    } finally {
      setBusy(false);
    }
  };

  const fromStudy = () => set({
    objectives: content.objectives || project.study.objectives,
    hypotheses: content.hypotheses.length ? content.hypotheses : project.study.hypotheses,
  });

  const variableData = [...new Set([...variableNames, ...content.primary_variables, ...content.secondary_variables])];
  const calcData = calcs.map((c) => ({ value: String(c.id), label: `n° ${c.id} · ${c.title}` }));
  const hypData = content.hypotheses.map((h, i) => ({ value: String(i), label: `P${i + 1}. ${h.slice(0, 80)}` }));

  return (
    <Box p="xl" maw={1300}>
      <Group justify="space-between" align="flex-start" mb="md" wrap="nowrap">
        <div>
          <Group gap="sm">
            <Title order={2}>Plan d'analyse</Title>
            {!current && <Badge variant="light" color="gray">Pas encore commencé</Badge>}
            {current && isDraft && <Badge variant="light" color="orange">Version {current.version} · brouillon</Badge>}
            {current && !isDraft && <Badge variant="light" color="teal" leftSection={<IconLock size={12} />}>
              Version {current.version} verrouillée</Badge>}
            {saving && <Loader size="xs" />}
            <AiMarkBadge mark={aiMarks.find('plan')} onValidate={(t) => void aiMarks.validate(t)} />
          </Group>
          <Text c="dimmed" size="sm" maw={820}>
            À rédiger avant l'analyse finale. Une fois verrouillé, le plan ne change plus : toute modification crée une
            nouvelle version, avec son motif, conservée dans l'historique et dans le rapport. Le rapport distingue les
            analyses prévues des analyses ajoutées après avoir vu les données.
          </Text>
        </div>
        <Group gap="xs" wrap="nowrap">
          {(!current || isDraft) && (
            <CopilotButton action="plan" label="Proposer le plan avec l'IA"
              disabled={project.datasets.length === 0 || project.study.hypotheses.length === 0 || pendingLocal}
              disabledReason={project.datasets.length === 0 ? "Importez d'abord les données."
                : project.study.hypotheses.length === 0 ? "Ajoutez d'abord des hypothèses à l'étude (l'IA peut les proposer)."
                : 'Enregistrement du brouillon en cours.'} />
          )}
          {locked && (
            <Tooltip label="Le moteur calcule chaque analyse prévue au plan verrouillé, sur le jeu de données ouvert (et sa dernière version préparée).">
              <Button variant="light" color="teal" leftSection={<IconPlayerPlay size={16} />} loading={busy}
                disabled={!env?.datasetId} onClick={() => void runAll()}>
                Lancer toutes les analyses prévues
              </Button>
            </Tooltip>
          )}
          {plan.versions.length > 0 && (
            <Button variant="default" leftSection={<IconHistory size={16} />} onClick={() => setHistoryOpen(true)}>
              Historique ({plan.versions.length})
            </Button>
          )}
          {isDraft && (
            <Tooltip label={current!.version > 1 ? `Revenir à la version ${current!.version - 1}` : 'Supprimer le brouillon'}>
              <Button variant="default" color="red" leftSection={<IconArrowBackUp size={16} />} loading={busy}
                onClick={() => void discard()}>Abandonner le brouillon</Button>
            </Tooltip>
          )}
          <Button leftSection={<IconLock size={16} />} disabled={!isDraft || pendingLocal || saving}
            onClick={() => setLockOpen(true)}>
            Verrouiller{isDraft ? ` la version ${current!.version}` : ''}
          </Button>
        </Group>
      </Group>

      {error && <Alert color="orange" mb="md">{error}</Alert>}
      <AiMarksBanner marks={aiMarks.marks} onValidate={(t) => void aiMarks.validate(t)} />
      {runResult && (
        <Alert color="teal" variant="light" mb="md" withCloseButton onClose={() => setRunResult(null)}
          title={`Plan verrouillé v${runResult.version} : ${runResult.ran} analyse(s) calculée(s)`}>
          <List size="sm">
            {runResult.results.map((r) => (
              <List.Item key={r.item}>
                <Text span size="sm" fw={600}>{r.label}</Text> : <Text span size="sm"
                  c={r.status === 'erreur' ? 'red' : r.status === 'lancee' ? 'teal.8' : 'dimmed'}>{r.message}</Text>
              </List.Item>
            ))}
          </List>
          {runResult.ran > 0 && env && (
            <Button size="xs" mt="xs" variant="light" onClick={() => env.goTo('analyses')}>Voir les résultats</Button>
          )}
        </Alert>
      )}
      {current && !isDraft && (
        <Alert color="teal" variant="light" icon={<IconLock size={18} />} mb="md">
          Plan verrouillé le {formatDateTime(current.locked_at!)}. Vous pouvez encore le modifier : la première
          modification crée la version {current.version + 1} en brouillon, à verrouiller avec le motif du changement.
        </Alert>
      )}
      {isDraft && locked && plan.pending_changes.length > 0 && (
        <Alert color="orange" variant="light" icon={<IconLockOpen size={18} />} mb="md"
          title={`Modifications par rapport à la version verrouillée ${locked.version}`}>
          <List size="sm">{plan.pending_changes.map((c, i) => <List.Item key={i}>{c.detail}</List.Item>)}</List>
        </Alert>
      )}

      <Grid gap="lg">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper withBorder p="md">
            <Group justify="space-between" mb="xs">
              <Text fw={600}>Objectifs et hypothèses</Text>
              <Button size="compact-xs" variant="subtle" leftSection={<IconCopy size={14} />} onClick={fromStudy}
                disabled={!!content.objectives && content.hypotheses.length > 0}>
                Reprendre la fiche Étude
              </Button>
            </Group>
            <Stack gap="sm">
              <Textarea label="Objectifs" autosize minRows={2} maxLength={20000} value={content.objectives}
                onChange={(e) => set({ objectives: e.currentTarget.value })} />
              <div>
                <Text size="sm" fw={500} mb={4}>Hypothèses du plan</Text>
                <HypothesesEditor prefix="P" value={content.hypotheses} onChange={(h) => set({ hypotheses: h })} />
              </div>
            </Stack>
          </Paper>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Paper withBorder p="md">
            <Text fw={600} mb="xs">Variables et effectif</Text>
            <Stack gap="sm">
              <TagsInput label="Variables principales" data={variableData} value={content.primary_variables}
                onChange={(v) => set({ primary_variables: v })} placeholder="Nom de variable, puis Entrée"
                description={variableNames.length ? undefined : 'Aucune donnée importée : saisissez les noms prévus.'} />
              <TagsInput label="Variables secondaires" data={variableData} value={content.secondary_variables}
                onChange={(v) => set({ secondary_variables: v })} placeholder="Nom de variable, puis Entrée" />
              <Group grow align="flex-start">
                <NumberInput label="Seuil de signification α" value={content.alpha} min={0.0001} max={0.2} step={0.01}
                  decimalScale={4} decimalSeparator="," onChange={(v) => typeof v === 'number' && set({ alpha: v })} />
                <NumberInput label="Taille d'échantillon prévue" value={content.sample_size ?? ''} min={1}
                  allowDecimal={false} onChange={(v) => set({ sample_size: v === '' ? null : Number(v) })} />
              </Group>
              <Select label="Justification de la taille : calcul de puissance" clearable data={calcData}
                value={content.power_calc !== null ? String(content.power_calc) : null}
                placeholder={calcData.length ? 'Choisir un calcul enregistré' : 'Aucun calcul enregistré (écran Puissance)'}
                disabled={calcData.length === 0}
                onChange={(v) => set({ power_calc: v ? Number(v) : null })} />
            </Stack>
          </Paper>
        </Grid.Col>

        <Grid.Col span={12}>
          <Paper withBorder p="md">
            <Group justify="space-between" mb="sm">
              <div>
                <Text fw={600}>Analyses prévues</Text>
                <Text size="xs" c="dimmed">
                  Chaque analyse reçoit une référence (A1, A2…). Au lancement d'une analyse, vous la rattachez à sa
                  référence : seules les analyses rattachées à un plan verrouillé sont présentées comme prévues.
                </Text>
              </div>
              <Button size="xs" leftSection={<IconPlus size={14} />}
                onClick={() => set({ analyses: [...content.analyses, { ...NEW_ITEM }] })}>
                Ajouter une analyse prévue
              </Button>
            </Group>
            {content.analyses.length === 0 && (
              <Alert color="gray" icon={<IconInfoCircle size={18} />}>Aucune analyse prévue pour l'instant.</Alert>
            )}
            <Stack gap="sm">
              {content.analyses.map((it, i) => {
                const info = catalog.methods.find((m) => m.key === it.method);
                return (
                  <Paper key={it.id ?? `new-${i}`} withBorder p="sm" bg="gray.0">
                    <Group justify="space-between" mb={6}>
                      <Badge variant="filled" size="lg">{it.id ?? 'Nouvelle'}</Badge>
                      <ActionIcon variant="subtle" color="red" aria-label={`Retirer l'analyse prévue ${it.id ?? i + 1}`}
                        onClick={() => set({ analyses: content.analyses.filter((_, j) => j !== i) })}>
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                    <Grid gap="sm">
                      <Grid.Col span={{ base: 12, md: 4 }}>
                        <Select label="Méthode" data={grouped} value={it.method || null} searchable
                          aria-label={`Méthode de l'analyse prévue ${i + 1}`}
                          onChange={(v) => v && setItem(i, { method: v, variables: {} })} />
                      </Grid.Col>
                      {info?.variables.map((role) => (
                        <Grid.Col key={role.name} span={{ base: 12, md: info.variables.length > 1 ? 4 : 8 }}>
                          <TagsInput label={role.label} data={variableData} value={it.variables[role.name] ?? []}
                            maxTags={role.multiple ? 30 : 1} placeholder={role.multiple ? 'Variables' : 'Variable'}
                            onChange={(v) => setItem(i, { variables: { ...it.variables, [role.name]: v } })} />
                        </Grid.Col>
                      ))}
                      <Grid.Col span={{ base: 12, md: 4 }}>
                        <Select label="Hypothèse" clearable data={hypData} placeholder="Aucune"
                          value={it.hypothesis !== null ? String(it.hypothesis) : null}
                          onChange={(v) => setItem(i, { hypothesis: v === null ? null : Number(v) })} />
                      </Grid.Col>
                      <Grid.Col span={{ base: 12, md: 3 }}>
                        <Text size="sm" fw={500} mb={4}>Rôle</Text>
                        <SegmentedControl size="xs" value={it.role} data={[{ value: 'principale', label: 'Principale' },
                          { value: 'secondaire', label: 'Secondaire' }]}
                          onChange={(v) => setItem(i, { role: v as PlanItem['role'] })} />
                      </Grid.Col>
                      {info?.params.includes('alternative') && (
                        <Grid.Col span={{ base: 12, md: 2 }}>
                          <Select label="Test" data={ALTERNATIVES} value={it.alternative} allowDeselect={false}
                            onChange={(v) => v && setItem(i, { alternative: v as PlanItem['alternative'] })} />
                        </Grid.Col>
                      )}
                      <Grid.Col span={{ base: 12, md: 3 }}>
                        <Select label="Calcul de puissance" clearable data={calcData} placeholder="Aucun"
                          disabled={calcData.length === 0}
                          value={it.power_calc !== null ? String(it.power_calc) : null}
                          onChange={(v) => setItem(i, { power_calc: v ? Number(v) : null })} />
                      </Grid.Col>
                      <Grid.Col span={12}>
                        <Textarea label="Précisions" autosize minRows={1} maxLength={2000} value={it.description}
                          placeholder="Ex. : groupes « oui » et « non », comparaison principale de l'étude"
                          onChange={(e) => setItem(i, { description: e.currentTarget.value })} />
                      </Grid.Col>
                    </Grid>
                  </Paper>
                );
              })}
            </Stack>
          </Paper>
        </Grid.Col>

        <Grid.Col span={12}>
          <Paper withBorder p="md">
            <Text fw={600} mb="xs">Règles fixées à l'avance</Text>
            <Grid gap="sm">
              {([
                ['exclusion_criteria', "Critères d'exclusion", 'Ex. : questionnaires remplis à moins de 80 %'],
                ['missing_values', 'Traitement des valeurs manquantes', 'Ex. : analyse des cas complets, sans imputation'],
                ['multiplicity', 'Tests multiples', 'Ex. : correction de Holm sur les analyses secondaires'],
                ['exploratory', 'Analyses exploratoires envisagées', 'Ex. : comparaison selon le sexe, à titre exploratoire'],
              ] as const).map(([key, label, ph]) => (
                <Grid.Col key={key} span={{ base: 12, md: 6 }}>
                  <Textarea label={label} placeholder={ph} autosize minRows={2} maxLength={20000} value={content[key]}
                    onChange={(e) => set({ [key]: e.currentTarget.value } as Partial<PlanContent>)} />
                </Grid.Col>
              ))}
            </Grid>
          </Paper>
        </Grid.Col>
      </Grid>

      <Modal opened={lockOpen} onClose={() => setLockOpen(false)} centered size="lg"
        title={<Text fw={650}>Verrouiller la version {current?.version}</Text>}>
        <Stack gap="sm">
          <Text size="sm">
            Une version verrouillée ne peut plus être modifiée. Les analyses lancées ensuite pourront y être rattachées et
            seront présentées comme prévues dans le rapport.
          </Text>
          {locked && plan.pending_changes.length > 0 && (
            <List size="sm">{plan.pending_changes.map((c, i) => <List.Item key={i}>{c.detail}</List.Item>)}</List>
          )}
          <Textarea label={current && current.version > 1 ? 'Motif de la modification (obligatoire)' : 'Remarque (facultatif)'}
            autosize minRows={2} maxLength={2000} value={reason} onChange={(e) => setReason(e.currentTarget.value)}
            placeholder={current && current.version > 1 ? 'Ex. : critère d\'exclusion précisé après avis de l\'encadrant' : ''} />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setLockOpen(false)}>Annuler</Button>
            <Button leftSection={<IconLock size={16} />} loading={busy}
              disabled={!!current && current.version > 1 && !reason.trim()} onClick={() => void lock()}>
              Verrouiller
            </Button>
          </Group>
        </Stack>
      </Modal>

      <Modal opened={historyOpen} onClose={() => setHistoryOpen(false)} centered size="lg"
        title={<Text fw={650}>Historique du plan d'analyse</Text>}>
        <Timeline bulletSize={18} active={plan.versions.length}>
          {[...plan.versions].reverse().map((v) => (
            <Timeline.Item key={v.version} bullet={v.status === 'verrouille' ? <IconLock size={10} /> : undefined}
              title={<Group gap="xs"><Text size="sm" fw={600}>Version {v.version}</Text>
                <Badge size="xs" variant="light" color={v.status === 'verrouille' ? 'teal' : 'orange'}>
                  {v.status === 'verrouille' ? 'Verrouillée' : 'Brouillon'}</Badge></Group>}>
              <Text size="xs" c="dimmed">
                {v.locked_at ? `Verrouillée le ${formatDateTime(v.locked_at)}` : `Modifiée le ${formatDateTime(v.updated_at)}`}
              </Text>
              {v.change_reason && <Text size="sm">Motif : {v.change_reason}</Text>}
              {v.changes.length > 0 && (
                <List size="xs" mt={4}>{v.changes.map((c, i) => <List.Item key={i}>{c.detail}</List.Item>)}</List>
              )}
              {v.status === 'verrouille' && (
                <Button size="compact-xs" variant="subtle" mt={4}
                  onClick={() => call('plan.version', { version: v.version }).then(setViewed)
                    .catch((err) => notifyError(err, 'Version introuvable'))}>
                  Voir le contenu
                </Button>
              )}
            </Timeline.Item>
          ))}
        </Timeline>
      </Modal>

      <Modal opened={viewed !== null} onClose={() => setViewed(null)} centered size="lg"
        title={<Text fw={650}>Version {viewed?.version} (lecture seule)</Text>}>
        {viewed && (
          <Stack gap="xs">
            <Text size="sm"><b>Objectifs :</b> {viewed.content.objectives || '—'}</Text>
            {viewed.content.hypotheses.map((h, i) => <Text key={i} size="sm"><b>P{i + 1}.</b> {h}</Text>)}
            <Text size="sm" fw={600} mt="xs">Analyses prévues</Text>
            <List size="sm">
              {viewed.content.analyses.map((it) => (
                <List.Item key={it.id}>
                  <b>{it.id}</b> · {catalog.methods.find((m) => m.key === it.method)?.label} :{' '}
                  {Object.values(it.variables).flat().join(', ')}
                </List.Item>
              ))}
            </List>
            <Text size="sm"><b>Seuil :</b> {String(viewed.content.alpha).replace('.', ',')}</Text>
          </Stack>
        )}
      </Modal>
    </Box>
  );
}
