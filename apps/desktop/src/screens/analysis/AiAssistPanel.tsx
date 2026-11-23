import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Alert, Badge, Box, Button, Checkbox, Code, Group, List, Loader, Modal, Paper, ScrollArea, Select, Stack, Text,
  Textarea,
} from '@mantine/core';
import {
  IconAlertTriangle, IconEye, IconPlayerStop, IconSettings, IconSparkles, IconTrash, IconCheck,
} from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { AiChecks, AiContext, AiJob, AiStatus, AiTask, AiText, ProjectState } from '../../engine/types';
import { formatDateTime } from '../../lib/format';
import { notifyError } from '../../App';

interface Props {
  analysisId: number;
  onProjectChange?: (p: ProjectState) => void;
  onOpenSettings?: () => void;
}

const STATUS_COLOR: Record<string, string> = { proposition: 'yellow', retenu: 'teal', ecarte: 'gray' };

/** Aide à la rédaction par l'IA locale, sous un résultat déjà calculé. */
export function AiAssistPanel({ analysisId, onProjectChange, onOpenSettings }: Props) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [tasks, setTasks] = useState<AiTask[]>([]);
  const [task, setTask] = useState<string>('paragraphe');
  const [userText, setUserText] = useState('');
  const [preview, setPreview] = useState<AiContext | null>(null);
  const [job, setJob] = useState<AiJob | null>(null);
  const [texts, setTexts] = useState<AiText[]>([]);
  const timer = useRef<number | null>(null);

  const loadTexts = useCallback(async () => {
    try { setTexts(await call('ai.texts', { analysis_id: analysisId })); } catch { /* projet fermé */ }
  }, [analysisId]);

  useEffect(() => {
    let cancelled = false;
    call('ai.status', {}).then((s) => !cancelled && setStatus(s)).catch(() => undefined);
    call('ai.tasks', {}).then((t) => !cancelled && setTasks(t)).catch(() => undefined);
    void loadTexts();
    return () => { cancelled = true; if (timer.current) window.clearTimeout(timer.current); };
  }, [loadTexts]);

  const poll = useCallback((id: number) => {
    timer.current = window.setTimeout(async () => {
      try {
        const snap = await call('ai.job', { job_id: id });
        setJob(snap);
        if (snap.status === 'en_cours') poll(id);
        else if (snap.ai_text) {
          void loadTexts();
          const p = await call('project.current', {});
          if (p) onProjectChange?.(p);
        }
      } catch (err) { notifyError(err, 'Proposition interrompue'); }
    }, 400);
  }, [loadTexts, onProjectChange]);

  const start = async () => {
    try {
      const snap = await call('ai.generate', { analysis_id: analysisId, task, user_text: userText || undefined });
      setJob(snap);
      if (snap.status === 'en_cours') poll(snap.id);
    } catch (err) { notifyError(err, 'Rédaction impossible'); }
  };

  const cancel = async () => {
    if (!job) return;
    if (timer.current) window.clearTimeout(timer.current);
    try { setJob(await call('ai.cancel', { job_id: job.id })); } catch (err) { notifyError(err); }
  };

  const updated = (t: AiText, p: ProjectState) => {
    setTexts((list) => list.map((x) => (x.id === t.id ? t : x)));
    onProjectChange?.(p);
  };

  const header = (
    <Group gap="xs" mb="xs">
      <IconSparkles size={18} />
      <Text fw={650}>Aide à l'interprétation et à la rédaction (IA)</Text>
      <Badge size="xs" variant="light" color="gray">optionnelle</Badge>
    </Group>
  );

  if (!status) return null;
  if (!status.ready) {
    return (
      <Paper withBorder p="md">
        {header}
        <Group justify="space-between" wrap="nowrap">
          <Text size="sm" c="dimmed">
            {status.state === 'desactivee'
              ? "L'IA est désactivée : la lecture ci-dessus et tout le reste de STATPFE fonctionnent sans elle."
              : `${status.message} L'IA n'est pas utilisable pour l'instant.`}
          </Text>
          {onOpenSettings && (
            <Button size="xs" variant="light" leftSection={<IconSettings size={14} />} onClick={onOpenSettings}>
              Réglages de l'IA
            </Button>
          )}
        </Group>
        {texts.length > 0 && <TextList texts={texts} onUpdated={updated} />}
      </Paper>
    );
  }

  const current = tasks.find((t) => t.key === task);
  const running = job?.status === 'en_cours';
  const fresh = job?.ai_text ? texts.find((t) => t.id === job.ai_text!.id) ?? job.ai_text : null;

  return (
    <Paper withBorder p="md">
      {header}
      <Text size="xs" c="dimmed" mb="sm">
        {status.settings.provider === 'claude_code'
          ? `Claude (${status.settings.model}), service en ligne d'Anthropic via Claude Code, avec votre autorisation. `
          : `Modèle ${status.settings.model} sur cet ordinateur. `}
        Il ne reçoit que les résultats calculés ci-dessus et ne calcule rien. Chaque texte est une proposition à vérifier.
      </Text>
      <Group align="flex-end" gap="sm">
        <Select label="Demande" data={tasks.map((t) => ({ value: t.key, label: t.label }))} value={task}
          onChange={(v) => v && setTask(v)} allowDeselect={false} w={320} disabled={running}
          description={current?.help} />
        <Button variant="default" leftSection={<IconEye size={16} />} disabled={running}
          onClick={async () => { try { setPreview(await call('ai.preview', { analysis_id: analysisId })); } catch (err) { notifyError(err, 'Contexte indisponible'); } }}>
          Voir ce qui sera transmis
        </Button>
        {running ? (
          <Button color="red" variant="light" leftSection={<IconPlayerStop size={16} />} onClick={() => void cancel()}>
            Annuler
          </Button>
        ) : (
          <Button leftSection={<IconSparkles size={16} />} onClick={() => void start()}
            disabled={!!current?.needs_text && !userText.trim()}>
            Rédiger une proposition
          </Button>
        )}
      </Group>
      {current?.needs_text && (
        <Textarea mt="sm" label="Votre texte à reformuler" autosize minRows={3} maxLength={4000} value={userText}
          onChange={(e) => setUserText(e.currentTarget.value)} disabled={running} />
      )}

      {job && running && (
        <Paper withBorder p="sm" mt="md" bg="var(--mantine-color-gray-0)">
          <Group gap="xs" mb={6}><Loader size="xs" /><Text size="xs" c="dimmed">
            Rédaction en cours ({job.meta.task_label.toLowerCase()}), {Math.round(job.elapsed)} s…
          </Text></Group>
          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{job.text || '…'}</Text>
        </Paper>
      )}
      {job && job.status === 'erreur' && (
        <Alert mt="md" color="red" variant="light" icon={<IconAlertTriangle size={18} />}>{job.error}</Alert>
      )}
      {job && job.status === 'annule' && <Text size="sm" c="dimmed" mt="md">Proposition annulée : rien n'a été enregistré.</Text>}
      {fresh && fresh.status === 'proposition' && (
        <Proposal key={fresh.id} item={fresh} onUpdated={updated} />
      )}

      {texts.filter((t) => t.id !== fresh?.id || fresh.status !== 'proposition').length > 0 && (
        <TextList texts={texts.filter((t) => t.id !== fresh?.id || fresh.status !== 'proposition')} onUpdated={updated} />
      )}

      <Modal opened={preview !== null} onClose={() => setPreview(null)} size="xl" title={<Text fw={650}>Ce qui sera transmis au modèle</Text>}>
        {preview && (
          <Stack gap="sm">
            <Text size="sm">
              Exactement ce texte ({preview.chars.toLocaleString('fr-FR')} caractères), précédé des consignes de prudence,
              est envoyé au modèle installé sur cet ordinateur. Rien d'autre.
            </Text>
            <List size="sm" spacing={2}>
              {preview.excluded.map((x) => <List.Item key={x}>{x}</List.Item>)}
            </List>
            <ScrollArea.Autosize mah={420}>
              <Code block style={{ whiteSpace: 'pre-wrap' }}>{preview.text}</Code>
            </ScrollArea.Autosize>
          </Stack>
        )}
      </Modal>
    </Paper>
  );
}

/** Texte avec les nombres non vérifiés surlignés. */
export function Highlighted({ text, checks }: { text: string; checks: AiChecks }) {
  const parts: React.ReactNode[] = [];
  let pos = 0;
  [...checks.unverified].sort((a, b) => a.start - b.start).forEach((u, i) => {
    if (u.start < pos) return;
    parts.push(text.slice(pos, u.start));
    parts.push(<mark key={i} style={{ background: 'var(--mantine-color-red-2)', padding: '0 2px', borderRadius: 3 }}
      title="Nombre absent des résultats calculés">{text.slice(u.start, u.end)}</mark>);
    pos = u.end;
  });
  parts.push(text.slice(pos));
  return <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{parts}</Text>;
}

export function CheckSummary({ checks }: { checks: AiChecks }) {
  return (
    <Stack gap={4}>
      {checks.unverified.length > 0 ? (
        <Alert color="red" variant="light" icon={<IconAlertTriangle size={16} />} p="xs">
          <Text size="sm">
            {checks.unverified.length} nombre(s) absent(s) des résultats calculés
            ({checks.unverified.map((u) => `« ${u.text} »`).join(', ')}) : corrigez-les ou supprimez-les avant de retenir
            le texte.
          </Text>
        </Alert>
      ) : (
        <Text size="xs" c="teal.8">
          <IconCheck size={12} /> {checks.numbers_total
            ? `Les ${checks.numbers_total} nombre(s) du texte figurent dans les résultats calculés.`
            : 'Le texte ne contient aucun nombre.'}
        </Text>
      )}
      {checks.warnings.map((w) => (
        <Alert key={w} color="yellow" variant="light" p="xs"><Text size="xs">{w}</Text></Alert>
      ))}
    </Stack>
  );
}

function Proposal({ item, onUpdated }: { item: AiText; onUpdated: (t: AiText, p: ProjectState) => void }) {
  const [text, setText] = useState(item.text);
  const [checks, setChecks] = useState<AiChecks>(item.checks);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (text === item.text) { setChecks(item.checks); return; }
    const t = window.setTimeout(() => {
      call('ai.check', { text_id: item.id, text }).then(setChecks).catch(() => undefined);
    }, 300);
    return () => window.clearTimeout(t);
  }, [text, item]);

  return (
    <Paper withBorder p="md" mt="md" style={{ borderColor: 'var(--mantine-color-yellow-5)' }}>
      <Group justify="space-between" mb={6}>
        <Group gap="xs">
          <Badge color="yellow" variant="light">Proposition à vérifier</Badge>
          <Text size="xs" c="dimmed">{item.task_label} · {item.model} · {formatDateTime(item.created_at)}
            {item.duration ? ` · ${Math.round(item.duration)} s` : ''}</Text>
        </Group>
      </Group>
      <Text size="xs" c="dimmed" mb="xs">
        Texte produit par un modèle de langage : il peut contenir des erreurs, des approximations ou des formulations
        trop affirmatives. Relisez-le, comparez-le aux résultats et modifiez-le librement.
      </Text>
      <Box mb="sm"><Highlighted text={text} checks={checks} /></Box>
      <CheckSummary checks={checks} />
      <Textarea mt="sm" label="Modifier le texte" autosize minRows={3} maxRows={14} value={text}
        onChange={(e) => setText(e.currentTarget.value)} />
      <Checkbox mt="sm" checked={reviewed} onChange={(e) => setReviewed(e.currentTarget.checked)}
        label="J'ai relu ce texte et vérifié qu'il correspond aux résultats calculés" />
      <Group justify="flex-end" mt="sm">
        <Button variant="default" color="gray" leftSection={<IconTrash size={16} />} disabled={busy}
          onClick={async () => { setBusy(true); try { const r = await call('ai.discard', { text_id: item.id }); onUpdated(r.ai_text, r.project); } catch (err) { notifyError(err); } finally { setBusy(false); } }}>
          Écarter
        </Button>
        <Button leftSection={<IconCheck size={16} />} disabled={busy || !reviewed || checks.blocking} loading={busy}
          onClick={async () => { setBusy(true); try { const r = await call('ai.keep', { text_id: item.id, text, reviewed }); onUpdated(r.ai_text, r.project); } catch (err) { notifyError(err, 'Texte non retenu'); } finally { setBusy(false); } }}>
          Retenir pour le rapport
        </Button>
      </Group>
    </Paper>
  );
}

function TextList({ texts, onUpdated }: { texts: AiText[]; onUpdated: (t: AiText, p: ProjectState) => void }) {
  const [open, setOpen] = useState<number | null>(null);
  return (
    <Stack gap={6} mt="md">
      <Text size="sm" fw={600}>Propositions enregistrées pour cette analyse ({texts.length})</Text>
      {texts.map((t) => (
        <Paper key={t.id} withBorder p="xs">
          <Group justify="space-between" wrap="nowrap" style={{ cursor: 'pointer' }} onClick={() => setOpen(open === t.id ? null : t.id)}>
            <Group gap="xs" wrap="nowrap" style={{ minWidth: 0 }}>
              <Badge size="xs" variant="light" color={STATUS_COLOR[t.status]}>{t.status_label}</Badge>
              <Text size="sm" truncate>{t.task_label}</Text>
              <Text size="xs" c="dimmed">{t.model} · {formatDateTime(t.created_at)}{t.edited ? ' · modifiée' : ''}</Text>
            </Group>
          </Group>
          {open === t.id && (
            t.status === 'proposition' ? <Proposal item={t} onUpdated={onUpdated} /> : (
              <Box mt="xs">
                <Highlighted text={t.text} checks={t.checks} />
                {t.status === 'retenu' && (
                  <Text size="xs" c="dimmed" mt={4}>Retenue le {formatDateTime(t.reviewed_at ?? t.updated_at)} : elle figurera
                    dans le rapport, signalée comme rédigée avec l'aide d'une IA.</Text>
                )}
              </Box>
            )
          )}
        </Paper>
      ))}
    </Stack>
  );
}
