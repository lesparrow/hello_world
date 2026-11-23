import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import {
  Alert, Badge, Box, Button, Checkbox, Code, Group, List, Loader, Menu, Modal, Paper, ScrollArea, Stack, Table,
  Text, Textarea, Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle, IconArrowBackUp, IconCheck, IconChevronDown, IconEye, IconInfoCircle, IconPlayerStop,
  IconSettings, IconSparkles, IconTrash,
} from '@tabler/icons-react';
import { call } from '../../engine/client';
import type {
  AiMark, AiStatus, CopilotAction, CopilotContext, CopilotIssue, CopilotJob, CopilotProposal, PlanItemProposal,
  ProjectState, StudyFieldProposal,
} from '../../engine/types';
import { formatStat } from '../../lib/stats';
import { notifyError } from '../../App';
import { CheckSummary, Highlighted } from '../../screens/analysis/AiAssistPanel';

// ====================================================================== environnement partagé
export type ScreenKey = 'etude' | 'plan' | 'puissance' | 'donnees' | 'preparation' | 'analyses' | 'rapport' | 'ia';

export interface CopilotEnv {
  screen: ScreenKey;
  datasetId: number | null;
  versionId: number | null;
  marksVersion: number;
  onProjectChange: (p: ProjectState) => void;
  /** Après une application : le moteur a modifié l'étude, les données, le plan… */
  onApplied: (action: CopilotAction, p: ProjectState) => void;
  openSettings: () => void;
  goTo: (screen: ScreenKey, openAction?: CopilotAction) => void;
}

export const CopilotEnvContext = createContext<CopilotEnv | null>(null);

export function useCopilotEnv(): CopilotEnv | null {
  return useContext(CopilotEnvContext);
}

/** Mentions « proposé par l'IA » encore à valider, rechargées après chaque application. */
export function useAiMarks(prefix: string) {
  const env = useCopilotEnv();
  const [marks, setMarks] = useState<AiMark[]>([]);
  const version = env?.marksVersion ?? 0;
  const projectChange = env?.onProjectChange;

  const reload = useCallback(async () => {
    try { setMarks((await call('ai.marks', { prefix })).marks); } catch { setMarks([]); }
  }, [prefix]);

  useEffect(() => { void reload(); }, [reload, version]);

  const validate = useCallback(async (targets: string[]) => {
    try {
      const r = await call('ai.marks_validate', { targets });
      setMarks(r.marks.filter((m) => m.target.startsWith(prefix)));
      projectChange?.(r.project);
    } catch (err) { notifyError(err, 'Validation impossible'); }
  }, [prefix, projectChange]);

  const find = useCallback((target: string) => marks.find((m) => m.target === target), [marks]);
  return { marks, find, validate, reload };
}

/** Badge « Proposé par l'IA » : valider ou annuler toute l'application. */
export function AiMarkBadge({ mark, onValidate }: { mark: AiMark | undefined; onValidate: (targets: string[]) => void }) {
  const env = useCopilotEnv();
  if (!mark) return null;
  const undo = async () => {
    try {
      const r = await call('ai.copilot_undo', { proposal_id: mark.proposal_id });
      env?.onApplied(r.proposal.action, r.project);
    } catch (err) { notifyError(err, 'Annulation impossible'); }
  };
  return (
    <Menu position="bottom-start" withinPortal>
      <Menu.Target>
        <Badge component="button" type="button" color="yellow" variant="light" size="sm" style={{ cursor: 'pointer' }}
          leftSection={<IconSparkles size={11} />} rightSection={<IconChevronDown size={11} />}>
          Proposé par l'IA, à valider
        </Badge>
      </Menu.Target>
      <Menu.Dropdown>
        <Menu.Label>{mark.label}</Menu.Label>
        <Menu.Item leftSection={<IconCheck size={15} />} onClick={() => onValidate([mark.target])}>
          J'ai relu : valider
        </Menu.Item>
        <Menu.Item leftSection={<IconArrowBackUp size={15} />} onClick={() => void undo()}>
          Annuler toute cette proposition
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );
}

/** Bandeau récapitulatif des éléments d'un écran encore marqués. */
export function AiMarksBanner({ marks, onValidate }: { marks: AiMark[]; onValidate: (targets: string[]) => void }) {
  if (marks.length === 0) return null;
  return (
    <Alert color="yellow" variant="light" icon={<IconSparkles size={18} />} mb="md">
      <Group justify="space-between" wrap="nowrap" gap="sm">
        <Text size="sm">
          {marks.length} élément(s) de cet écran ont été proposés par l'IA et ne sont pas encore validés :{' '}
          {marks.slice(0, 6).map((m) => m.label).join(', ')}{marks.length > 6 ? '…' : ''}. Relisez-les ; ils restent
          signalés dans le rapport tant que vous ne les avez pas validés.
        </Text>
        <Button size="xs" variant="light" color="yellow" leftSection={<IconCheck size={14} />} style={{ flexShrink: 0 }}
          onClick={() => onValidate(marks.map((m) => m.target))}>
          Tout valider
        </Button>
      </Group>
    </Alert>
  );
}

// ====================================================================== bouton + fenêtre
type InputKind = 'subject' | 'note' | 'question' | 'none';

interface ButtonProps {
  action: CopilotAction;
  label: string;
  params?: Record<string, unknown>;
  input?: InputKind;
  inputLabel?: string;
  inputPlaceholder?: string;
  disabled?: boolean;
  disabledReason?: string;
  size?: 'xs' | 'sm' | 'md';
  variant?: 'light' | 'filled' | 'default';
  autoOpen?: boolean;
  onAutoOpened?: () => void;
}

export function CopilotButton({ disabled, disabledReason, size = 'sm', variant = 'light', label, autoOpen,
  onAutoOpened, ...rest }: ButtonProps) {
  const [opened, setOpened] = useState(false);
  useEffect(() => {
    if (autoOpen && !disabled) { setOpened(true); onAutoOpened?.(); }
  }, [autoOpen, disabled, onAutoOpened]);
  const button = (
    <Button size={size} variant={variant} color="grape" leftSection={<IconSparkles size={16} />}
      disabled={disabled} onClick={() => setOpened(true)}>
      {label}
    </Button>
  );
  return (
    <>
      {disabled && disabledReason ? <Tooltip label={disabledReason} multiline w={280}><span>{button}</span></Tooltip> : button}
      {opened && <CopilotModal {...rest} title={label} onClose={() => setOpened(false)} />}
    </>
  );
}

interface ModalProps {
  action: CopilotAction;
  title: string;
  params?: Record<string, unknown>;
  input?: InputKind;
  inputLabel?: string;
  inputPlaceholder?: string;
  onClose: () => void;
}

const INPUT_DEFAULTS: Record<Exclude<InputKind, 'none'>, { key: string; label: string; placeholder: string; required: boolean }> = {
  subject: {
    key: 'subject', required: false, label: 'Votre sujet en quelques lignes',
    placeholder: "Ex. : J'étudie le lien entre le temps passé sur les réseaux sociaux et la qualité du sommeil chez les étudiants de licence de mon université…",
  },
  note: {
    key: 'note', required: false, label: 'Précisions (facultatif)',
    placeholder: "Ex. : une étude pilote a trouvé d = 0,4 ; je pourrai interroger au plus 150 personnes…",
  },
  question: { key: 'question', required: true, label: 'Votre question', placeholder: 'Ex. : Quel test choisir pour comparer deux groupes ?' },
};

export function CopilotModal({ action, title, params, input = 'none', inputLabel, inputPlaceholder, onClose }: ModalProps) {
  const env = useCopilotEnv();
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [text, setText] = useState('');
  const [preview, setPreview] = useState<CopilotContext | null>(null);
  const [job, setJob] = useState<CopilotJob | null>(null);
  const [proposal, setProposal] = useState<CopilotProposal | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    call('ai.status', {}).then(setStatus).catch((err) => notifyError(err, "État de l'IA indisponible"));
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, []);

  const spec = input !== 'none' ? INPUT_DEFAULTS[input] : null;
  const fullParams = (): Record<string, unknown> => {
    const p: Record<string, unknown> = { ...(params ?? {}) };
    if (spec && text.trim()) p[spec.key] = text.trim();
    if (action === 'ask' && env) p.screen = env.screen;
    if (env && p.dataset_id === undefined && env.datasetId !== null) {
      p.dataset_id = env.datasetId;
      p.version_id = env.versionId;
    }
    return p;
  };

  const poll = (id: number) => {
    timer.current = window.setTimeout(async () => {
      try {
        const snap = (await call('ai.job', { job_id: id })) as unknown as CopilotJob;
        setJob(snap);
        if (snap.status === 'en_cours') poll(id);
        else if (snap.proposal) {
          setProposal(snap.proposal);
          const p = await call('project.current', {});
          if (p) env?.onProjectChange(p);
        }
      } catch (err) { notifyError(err, 'Proposition interrompue'); }
    }, 400);
  };

  const start = async () => {
    setProposal(null);
    try {
      const snap = await call('ai.copilot_start', { action, params: fullParams() });
      setJob(snap);
      if (snap.status === 'en_cours') poll(snap.id);
      else if (snap.proposal) setProposal(snap.proposal);
    } catch (err) { notifyError(err, 'Demande impossible'); }
  };

  const cancel = async () => {
    if (!job) return;
    if (timer.current) window.clearTimeout(timer.current);
    try { setJob((await call('ai.cancel', { job_id: job.id })) as unknown as CopilotJob); } catch (err) { notifyError(err); }
  };

  const showPreview = async () => {
    try { setPreview(await call('ai.copilot_preview', { action, params: fullParams() })); }
    catch (err) { notifyError(err, 'Contexte indisponible'); }
  };

  const doApply = async (selection: Record<string, unknown>) => {
    if (!proposal) return;
    setBusy(true);
    try {
      const r = await call('ai.copilot_apply', { proposal_id: proposal.id, selection });
      setProposal(r.proposal);
      env?.onApplied(action, r.project);
    } catch (err) { notifyError(err, 'Application refusée par le moteur'); }
    finally { setBusy(false); }
  };

  const doUndo = async () => {
    if (!proposal) return;
    setBusy(true);
    try {
      const r = await call('ai.copilot_undo', { proposal_id: proposal.id });
      setProposal(r.proposal);
      env?.onApplied(action, r.project);
    } catch (err) { notifyError(err, 'Annulation impossible'); }
    finally { setBusy(false); }
  };

  const doDiscard = async () => {
    if (!proposal) return;
    try {
      const r = await call('ai.copilot_discard', { proposal_id: proposal.id });
      setProposal(r.proposal);
      env?.onProjectChange(r.project);
    } catch (err) { notifyError(err); }
  };

  const running = job?.status === 'en_cours';
  const online = status?.settings.provider === 'claude_code';

  return (
    <Modal opened onClose={onClose} size="xl" closeOnClickOutside={!running && preview === null}
      closeOnEscape={preview === null}
      title={<Group gap="xs"><IconSparkles size={18} /><Text fw={650}>{title}</Text>
        <Badge size="xs" variant="light" color="grape">IA, à vérifier</Badge></Group>}>
      {!status ? <Loader size="sm" /> : !status.ready ? (
        <Stack gap="sm">
          <Text size="sm">
            {status.state === 'desactivee'
              ? "L'IA est désactivée. STATPFE fonctionne entièrement sans elle ; activez-la pour recevoir des propositions."
              : `${status.message} L'IA n'est pas utilisable pour l'instant.`}
          </Text>
          <Group><Button leftSection={<IconSettings size={16} />} variant="light"
            onClick={() => { onClose(); env?.openSettings(); }}>Réglages de l'IA</Button></Group>
        </Stack>
      ) : (
        <Stack gap="sm">
          <Text size="xs" c="dimmed">
            {online
              ? `Claude (${status.settings.model}), service en ligne d'Anthropic, utilisé avec votre autorisation. `
              : `Modèle ${status.settings.model} installé sur cet ordinateur : rien ne sort de votre machine. `}
            L'IA propose, le moteur de STATPFE vérifie chaque proposition et fait tous les calculs. Rien n'est modifié
            avant que vous appliquiez, et chaque élément appliqué reste marqué « proposé par l'IA » jusqu'à votre
            validation.
          </Text>
          {spec && (
            <Textarea label={inputLabel ?? spec.label} placeholder={inputPlaceholder ?? spec.placeholder} autosize
              minRows={action === 'ask' ? 2 : 3} maxRows={8} maxLength={4000} value={text} disabled={running}
              onChange={(e) => setText(e.currentTarget.value)} />
          )}
          <Group justify="flex-end" gap="sm">
            <Button variant="default" leftSection={<IconEye size={16} />} disabled={running} onClick={() => void showPreview()}>
              Voir ce qui sera transmis
            </Button>
            {running ? (
              <Button color="red" variant="light" leftSection={<IconPlayerStop size={16} />} onClick={() => void cancel()}>
                Arrêter
              </Button>
            ) : (
              <Button color="grape" leftSection={<IconSparkles size={16} />} disabled={!!spec?.required && !text.trim()}
                onClick={() => void start()}>
                {proposal ? 'Nouvelle proposition' : action === 'ask' ? 'Demander' : 'Proposer'}
              </Button>
            )}
          </Group>

          {job && running && (
            <Paper withBorder p="sm" bg="var(--mantine-color-gray-0)">
              <Group gap="xs"><Loader size="xs" /><Text size="xs" c="dimmed">
                Le modèle prépare sa proposition, {Math.round(job.elapsed)} s… (un modèle local peut prendre une à
                plusieurs minutes)
              </Text></Group>
            </Paper>
          )}
          {job?.status === 'erreur' && (
            <Alert color="red" variant="light" icon={<IconAlertTriangle size={18} />}>{job.error}</Alert>
          )}
          {job?.status === 'annule' && <Text size="sm" c="dimmed">Demande arrêtée : rien n'a été enregistré.</Text>}

          {proposal && (
            <ProposalView key={`${proposal.id}-${proposal.status}`} proposal={proposal} busy={busy}
              onApply={doApply} onUndo={doUndo} onDiscard={doDiscard} onClose={onClose} />
          )}
        </Stack>
      )}

      <Modal opened={preview !== null} onClose={() => setPreview(null)} size="xl"
        title={<Text fw={650}>Ce qui sera transmis au modèle</Text>}>
        {preview && (
          <Stack gap="sm">
            <Text size="sm">
              Exactement ce texte ({preview.chars.toLocaleString('fr-FR')} caractères), précédé des consignes, est envoyé
              au modèle {online ? "Claude d'Anthropic (en ligne)" : 'installé sur cet ordinateur'}. Rien d'autre.
            </Text>
            <List size="sm" spacing={2}>{preview.excluded.map((x) => <List.Item key={x}>{x}</List.Item>)}</List>
            <ScrollArea.Autosize mah={420}>
              <Code block style={{ whiteSpace: 'pre-wrap' }}>{preview.text}</Code>
            </ScrollArea.Autosize>
          </Stack>
        )}
      </Modal>
    </Modal>
  );
}

// ====================================================================== affichage des propositions
const LEVEL_COLOR: Record<string, string> = { bloquant: 'red', important: 'orange', information: 'gray' };

function Issues({ issues }: { issues: CopilotIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <Stack gap={4}>
      {issues.map((i, k) => (
        <Alert key={k} color={LEVEL_COLOR[i.level]} variant="light" p="xs"
          icon={i.level === 'information' ? <IconInfoCircle size={16} /> : <IconAlertTriangle size={16} />}>
          <Text size="xs">{i.text}</Text>
        </Alert>
      ))}
    </Stack>
  );
}

interface ViewProps {
  proposal: CopilotProposal;
  busy: boolean;
  onApply: (selection: Record<string, unknown>) => void;
  onUndo: () => void;
  onDiscard: () => void;
  onClose: () => void;
}

function ProposalView(props: ViewProps) {
  const { proposal: p } = props;
  const env = useCopilotEnv();
  const header = (
    <Group gap="xs">
      <Badge variant="light" color={p.status === 'appliquee' ? 'teal' : p.status === 'proposee' || p.status === 'reponse' ? 'grape' : 'gray'}>
        {p.status_label}
      </Badge>
      <Text size="xs" c="dimmed">{p.model}{p.duration ? ` · ${Math.round(p.duration)} s` : ''}</Text>
    </Group>
  );
  if (p.status === 'appliquee' || p.status === 'annulee' || p.status === 'ecartee') {
    return (
      <Paper withBorder p="md">
        {header}
        <Text size="sm" mt="xs">
          {p.status === 'appliquee'
            ? "La proposition a été appliquée. Les éléments concernés sont marqués « Proposé par l'IA, à valider » : relisez-les, modifiez-les si besoin, puis validez-les."
            : p.status === 'annulee' ? "L'application a été annulée : tout est revenu comme avant." : 'Proposition écartée : rien n\'a été modifié.'}
        </Text>
        <Group justify="flex-end" mt="sm">
          {p.status === 'appliquee' && (
            <Button variant="default" leftSection={<IconArrowBackUp size={16} />} disabled={!p.can_undo || props.busy}
              onClick={props.onUndo}>
              Annuler l'application
            </Button>
          )}
          <Button onClick={props.onClose}>Fermer</Button>
        </Group>
      </Paper>
    );
  }
  if (p.status === 'illisible') {
    return <Paper withBorder p="md">{header}<Box mt="xs"><Issues issues={p.issues} /></Box></Paper>;
  }
  const body = p.proposal;
  return (
    <Paper withBorder p="md" style={{ borderColor: 'var(--mantine-color-grape-3)' }}>
      <Stack gap="sm">
        {header}
        <Issues issues={p.issues} />
        {p.action === 'study' && <StudyView {...props} />}
        {p.action === 'variables' && <VariablesView {...props} />}
        {p.action === 'plan' && <PlanView {...props} />}
        {p.action === 'power' && <PowerView {...props} />}
        {p.action === 'report' && <ReportView {...props} />}
        {p.action === 'ask' && body.answer && (
          <Stack gap="xs">
            <Highlighted text={body.answer} checks={body.checks!} />
            {body.checks && body.checks.unverified.length > 0 && <CheckSummary checks={body.checks} />}
            <Text size="xs" c="dimmed">Réponse d'un modèle de langage : vérifiez-la avant de vous en servir.</Text>
            {body.suggestion && env && (
              <Group>
                <Button size="xs" variant="light" color="grape" leftSection={<IconSparkles size={14} />}
                  onClick={() => { props.onClose(); env.goTo(SUGGESTION_SCREEN[body.suggestion!], body.suggestion!); }}>
                  {SUGGESTION_LABEL[body.suggestion]}
                </Button>
              </Group>
            )}
          </Stack>
        )}
      </Stack>
    </Paper>
  );
}

const SUGGESTION_SCREEN: Record<string, ScreenKey> = {
  study: 'etude', variables: 'donnees', plan: 'plan', power: 'puissance', report: 'rapport',
};
const SUGGESTION_LABEL: Record<string, string> = {
  study: "Remplir l'étude avec l'IA", variables: 'Compléter les variables avec l\'IA',
  plan: "Proposer le plan d'analyse avec l'IA", power: "Proposer la taille d'échantillon avec l'IA",
  report: 'Rédiger le rapport avec l\'IA',
};

function Footer({ busy, canApply, applyLabel, onApply, onDiscard, count }: {
  busy: boolean; canApply: boolean; applyLabel: string; onApply: () => void; onDiscard: () => void; count?: number;
}) {
  return (
    <Group justify="flex-end" mt="xs">
      <Button variant="default" leftSection={<IconTrash size={16} />} disabled={busy} onClick={onDiscard}>Écarter</Button>
      <Button color="grape" leftSection={<IconCheck size={16} />} loading={busy} disabled={!canApply} onClick={onApply}>
        {applyLabel}{count !== undefined ? ` (${count})` : ''}
      </Button>
    </Group>
  );
}

function asText(v: unknown): string {
  if (Array.isArray(v)) return v.join('\n');
  if (v === null || v === undefined) return '';
  return String(v);
}

function StudyView({ proposal, busy, onApply, onDiscard }: ViewProps) {
  const fields = proposal.proposal.fields ?? [];
  const [chosen, setChosen] = useState<string[]>(fields.filter((f) => f.changed).map((f) => f.key));
  const [edits, setEdits] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f.key, asText(f.value)])));
  const value = (f: StudyFieldProposal) => (f.key === 'hypotheses'
    ? edits[f.key].split('\n').map((x) => x.trim()).filter(Boolean)
    : f.key === 'planned_sample_size' ? Number(edits[f.key]) : edits[f.key]);
  return (
    <>
      <Text size="sm">Cochez les champs à remplir ; vous pouvez corriger le texte avant d'appliquer.</Text>
      {fields.map((f) => (
        <Paper key={f.key} withBorder p="sm">
          <Checkbox fw={600} label={f.label} checked={chosen.includes(f.key)}
            onChange={(e) => { const on = e.currentTarget.checked; setChosen((c) => on ? [...c, f.key] : c.filter((x) => x !== f.key)); }} />
          {asText(f.current) && (
            <Text size="xs" c="dimmed" mt={4} lineClamp={3}>Actuellement : {asText(f.current)}</Text>
          )}
          <Textarea mt={6} autosize minRows={f.key === 'title' ? 1 : 2} maxRows={10} value={edits[f.key]}
            description={f.key === 'hypotheses' ? 'Une hypothèse par ligne.' : undefined}
            onChange={(e) => { const v = e.currentTarget.value; setEdits((x) => ({ ...x, [f.key]: v })); }} />
        </Paper>
      ))}
      <Footer busy={busy} canApply={chosen.length > 0} applyLabel="Remplir les champs choisis" count={chosen.length}
        onDiscard={onDiscard}
        onApply={() => onApply({
          fields: chosen,
          edits: Object.fromEntries(fields.filter((f) => chosen.includes(f.key) && edits[f.key] !== asText(f.value))
            .map((f) => [f.key, value(f)])),
        })} />
    </>
  );
}

const CHANGE_LABEL: Record<string, string> = {
  label: 'Libellé', level: 'Niveau', role: 'Rôle', unit: 'Unité', missing_codes: 'Codes manquants',
};

const VOCAB: Record<string, string> = {
  continu: 'quantitative continue', ordinal: 'qualitative ordinale', nominal: 'qualitative nominale',
  a_expliquer: 'à expliquer', explicative: 'explicative', non_defini: 'non défini', exclue: 'exclue',
  identifiant: 'identifiant',
};
const vocab = (k: string, v: unknown) => ((k === 'level' || k === 'role') && typeof v === 'string' ? VOCAB[v] ?? v : asText(v));

function VariablesView({ proposal, busy, onApply, onDiscard }: ViewProps) {
  const vars = proposal.proposal.variables ?? [];
  const recodes = proposal.proposal.recodes ?? [];
  const [chosen, setChosen] = useState<string[]>(vars.map((v) => v.name));
  const [rc, setRc] = useState<number[]>(recodes.map((_, i) => i));
  const toggle = <T,>(set: React.Dispatch<React.SetStateAction<T[]>>, x: T, on: boolean) =>
    set((c) => (on ? [...c, x] : c.filter((y) => y !== x)));
  return (
    <>
      {vars.length > 0 && (
        <>
          <Text size="sm" fw={600}>Dictionnaire ({vars.length} variable(s))</Text>
          <Table withTableBorder striped fz="xs" verticalSpacing={4}>
            <Table.Thead><Table.Tr><Table.Th w={30} /><Table.Th>Variable</Table.Th><Table.Th>Modifications proposées</Table.Th></Table.Tr></Table.Thead>
            <Table.Tbody>
              {vars.map((v) => (
                <Table.Tr key={v.key}>
                  <Table.Td><Checkbox size="xs" checked={chosen.includes(v.name)} onChange={(e) => toggle(setChosen, v.name, e.currentTarget.checked)} /></Table.Td>
                  <Table.Td fw={600}>{v.name}</Table.Td>
                  <Table.Td>
                    {Object.entries(v.changes).map(([k, val]) => (
                      <Text key={k} size="xs">
                        {CHANGE_LABEL[k] ?? k} : <Text span c="dimmed" td="line-through">{vocab(k, v.current[k]) || 'vide'}</Text> → <b>{vocab(k, val)}</b>
                      </Text>
                    ))}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </>
      )}
      {recodes.length > 0 && (
        <>
          <Text size="sm" fw={600}>Nettoyage : harmoniser des modalités</Text>
          <Text size="xs" c="dimmed">
            Les recodages sont ajoutés à une nouvelle version « Préparée avec l'IA » : les données d'origine ne sont
            jamais modifiées.
          </Text>
          {recodes.map((r, i) => (
            <Paper key={i} withBorder p="xs">
              <Checkbox size="xs" checked={rc.includes(i)} onChange={(e) => toggle(setRc, i, e.currentTarget.checked)}
                label={<Text size="sm"><b>{r.variable}</b> → nouvelle variable <b>{r.new_name}</b> ({r.rows} ligne(s) concernée(s))</Text>} />
              <Text size="xs" mt={4}>
                {Object.entries(r.mapping).map(([a, b]) => `« ${a} » → « ${b} »`).join(' ; ')}
              </Text>
              {r.reason && <Text size="xs" c="dimmed">{r.reason}</Text>}
            </Paper>
          ))}
        </>
      )}
      {vars.length === 0 && recodes.length === 0 && <Text size="sm" c="dimmed">Aucune modification utile proposée.</Text>}
      <Footer busy={busy} canApply={chosen.length + rc.length > 0} applyLabel="Appliquer" count={chosen.length + rc.length}
        onDiscard={onDiscard} onApply={() => onApply({ variables: chosen, recodes: rc })} />
    </>
  );
}

const VERDICT: Record<string, { color: string; label: string }> = {
  conforme: { color: 'teal', label: 'Conforme au moteur' },
  acceptable: { color: 'blue', label: 'Acceptable' },
  ecart: { color: 'orange', label: 'Écart avec le moteur' },
  impossible: { color: 'red', label: 'Impossible' },
};

function PlanView({ proposal, busy, onApply, onDiscard }: ViewProps) {
  const items = (proposal.proposal.analyses ?? []) as PlanItemProposal[];
  const [chosen, setChosen] = useState<number[]>(items.map((it, i) => (it.check.verdict === 'impossible' ? -1 : i)).filter((i) => i >= 0));
  const [engine, setEngine] = useState<number[]>(items.map((it, i) => (it.check.verdict === 'ecart' ? i : -1)).filter((i) => i >= 0));
  const toggle = (set: React.Dispatch<React.SetStateAction<number[]>>, i: number, on: boolean) =>
    set((c) => (on ? [...c, i] : c.filter((y) => y !== i)));
  return (
    <>
      <Text size="sm">
        Chaque analyse proposée a été confrontée à l'assistant méthodologique du moteur (types de variables,
        appariement, effectifs). Les analyses retenues sont ajoutées au brouillon du plan, que vous verrouillerez
        vous-même.
      </Text>
      {items.map((it, i) => (
        <Paper key={i} withBorder p="sm">
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Checkbox disabled={it.check.verdict === 'impossible'} checked={chosen.includes(i)}
              onChange={(e) => toggle(setChosen, i, e.currentTarget.checked)}
              label={<Text size="sm" fw={600}>
                {it.hypothesis !== null ? `H${it.hypothesis + 1} · ` : ''}{it.method_label}
                <Text span size="xs" c="dimmed" fw={400}> ({it.role})</Text>
              </Text>} />
            <Badge size="sm" variant="light" color={VERDICT[it.check.verdict].color}>{VERDICT[it.check.verdict].label}</Badge>
          </Group>
          <Text size="xs" mt={4}>
            {Object.entries(it.variables).map(([r, names]) => `${r} : ${names.join(', ')}`).join(' · ')}
          </Text>
          {it.justification && <Text size="xs" c="dimmed">IA : {it.justification}</Text>}
          <Text size="xs" c={VERDICT[it.check.verdict].color === 'teal' ? 'teal.8' : undefined} mt={2}>Moteur : {it.check.text}</Text>
          {(it.check.verdict === 'ecart' || it.check.verdict === 'acceptable') && it.check.recommended && (
            <Checkbox size="xs" mt={6} checked={engine.includes(i)} disabled={!chosen.includes(i)}
              onChange={(e) => toggle(setEngine, i, e.currentTarget.checked)}
              label={`Utiliser plutôt la recommandation du moteur : ${it.check.recommended_label}`} />
          )}
        </Paper>
      ))}
      {(proposal.proposal.missing_values || proposal.proposal.multiplicity) && (
        <Text size="xs" c="dimmed">
          {proposal.proposal.missing_values && <>Valeurs manquantes : {proposal.proposal.missing_values}<br /></>}
          {proposal.proposal.multiplicity && <>Tests multiples : {proposal.proposal.multiplicity}</>}
          {' '}(repris dans le plan seulement si ces champs sont vides).
        </Text>
      )}
      <Footer busy={busy} canApply={chosen.length > 0} applyLabel="Ajouter au plan" count={chosen.length}
        onDiscard={onDiscard} onApply={() => onApply({ analyses: chosen, use_engine: engine.filter((i) => chosen.includes(i)) })} />
    </>
  );
}

function PowerView({ proposal, busy, onApply, onDiscard }: ViewProps) {
  const b = proposal.proposal;
  const req = b.request ?? {};
  const effects = (req.effects as Record<string, number>[] | undefined)?.[0] ?? {};
  return (
    <>
      <Text size="sm"><b>{b.design_label}</b> · {b.effect_label} = {Object.values(effects).map((x) => String(x).replace('.', ',')).join(', ')}
        {' '}· α = {String(req.alpha).replace('.', ',')} · puissance visée = {String(req.power).replace('.', ',')}</Text>
      {b.effect_source && <Text size="xs" c="dimmed">Source de la taille d'effet selon l'IA : {b.effect_source}</Text>}
      {b.justification && <Text size="xs" c="dimmed">IA : {b.justification}</Text>}
      {b.computed && (
        <Paper withBorder p="xs" bg="var(--mantine-color-gray-0)">
          <Text size="xs" fw={600} mb={4}>Calculé par le moteur de STATPFE</Text>
          {b.computed.summary.map((s) => (
            <Text key={s.key} size="sm">{s.label} : <b>{formatStat(s.value, s.kind, s.digits)}</b></Text>
          ))}
          {b.computed.interpretation.map((t, i) => <Text key={i} size="xs" mt={4}>{t}</Text>)}
        </Paper>
      )}
      <Footer busy={busy} canApply applyLabel="Enregistrer ce calcul" onDiscard={onDiscard} onApply={() => onApply({})} />
    </>
  );
}

function ReportView({ proposal, busy, onApply, onDiscard }: ViewProps) {
  const sections = proposal.proposal.sections ?? {};
  const keys = Object.keys(sections);
  const [chosen, setChosen] = useState<string[]>(keys.filter((k) => !sections[k].checks.blocking));
  const [edits, setEdits] = useState<Record<string, string>>(Object.fromEntries(keys.map((k) => [k, sections[k].text])));
  return (
    <>
      <Text size="sm">
        Textes rédigés à partir des seuls résultats calculés. Les nombres absents des résultats sont surlignés en
        rouge : corrigez-les, le moteur revérifie chaque texte au moment d'appliquer.
      </Text>
      {keys.map((k) => (
        <Paper key={k} withBorder p="sm">
          <Checkbox fw={600} label={sections[k].label} checked={chosen.includes(k)}
            onChange={(e) => { const on = e.currentTarget.checked; setChosen((c) => on ? [...c, k] : c.filter((x) => x !== k)); }} />
          {edits[k] === sections[k].text && (
            <Box mt={6}><Highlighted text={sections[k].text} checks={sections[k].checks} /></Box>
          )}
          <Box mt={6}><CheckSummary checks={sections[k].checks} /></Box>
          <Textarea mt={6} autosize minRows={3} maxRows={12} value={edits[k]} label="Modifier"
            onChange={(e) => { const v = e.currentTarget.value; setEdits((x) => ({ ...x, [k]: v })); }} />
        </Paper>
      ))}
      <Footer busy={busy} canApply={chosen.length > 0} applyLabel="Placer dans le rapport" count={chosen.length}
        onDiscard={onDiscard}
        onApply={() => onApply({
          sections: chosen,
          edits: Object.fromEntries(chosen.filter((k) => edits[k] !== sections[k].text).map((k) => [k, edits[k]])),
        })} />
    </>
  );
}

