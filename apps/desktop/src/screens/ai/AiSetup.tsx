import { useEffect, useRef, useState } from 'react';
import {
  Alert, Anchor, Badge, Box, Button, Checkbox, Code, CopyButton, Group, Loader, Modal, Paper, Progress, Radio,
  ScrollArea, SimpleGrid, Stack, Stepper, Switch, Table, Text, TextInput,
} from '@mantine/core';
import {
  IconAlertTriangle, IconCheck, IconCopy, IconDownload, IconExternalLink, IconLogin, IconPlayerPlay, IconRefresh, IconX,
} from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { AiSettings, AiSetupJob, AiStatus, LocalModelInfo } from '../../engine/types';
import { notifyError } from '../../App';

type Update = (changes: Partial<AiSettings> & { cloud_consent?: boolean }) => Promise<void>;

interface Props { status: AiStatus; busy: boolean; update: Update; refresh: () => Promise<void> }

const openLink = async (url: string) => {
  try { await call('ai.open_link', { url }); } catch (err) { notifyError(err, "Impossible d'ouvrir le lien"); }
};

/** Suit une étape d'installation lancée dans le moteur (journal, progression, annulation). */
function useSetupJob(onDone: (job: AiSetupJob) => void) {
  const [job, setJob] = useState<AiSetupJob | null>(null);
  const done = useRef(onDone);
  done.current = onDone;
  useEffect(() => {
    if (!job || job.status !== 'en_cours') return undefined;
    const t = window.setTimeout(async () => {
      try {
        const next = await call('ai.setup_job', { job_id: job.id });
        setJob(next);
        if (next.status !== 'en_cours') done.current(next);
      } catch (err) { notifyError(err, "Suivi de l'installation impossible"); setJob(null); }
    }, 500);
    return () => window.clearTimeout(t);
  }, [job]);
  const cancel = async () => {
    if (job) { try { setJob(await call('ai.setup_cancel', { job_id: job.id })); } catch (err) { notifyError(err, 'Annulation impossible'); } }
  };
  return { job, setJob, cancel };
}

function JobView({ job, onCancel }: { job: AiSetupJob; onCancel: () => void }) {
  const color = job.status === 'termine' ? 'teal' : job.status === 'en_cours' ? 'blue' : job.status === 'annule' ? 'gray' : 'red';
  return (
    <Paper withBorder p="sm" mt="xs">
      <Group justify="space-between" mb={6}>
        <Group gap="xs">
          {job.status === 'en_cours' ? <Loader size="xs" /> : job.status === 'termine' ? <IconCheck size={16} color="var(--mantine-color-teal-7)" /> : <IconX size={16} />}
          <Text size="sm" fw={600}>{job.label}</Text>
          <Badge size="sm" variant="light" color={color}>
            {{ en_cours: 'en cours', termine: 'terminé', erreur: 'échec', annule: 'annulé' }[job.status]}
          </Badge>
          <Text size="xs" c="dimmed">{Math.round(job.elapsed)} s</Text>
        </Group>
        {job.status === 'en_cours' && <Button size="compact-xs" variant="subtle" color="red" onClick={onCancel}>Annuler</Button>}
      </Group>
      {job.progress !== null && (
        <Box mb={6}>
          <Progress value={job.progress * 100} animated={job.status === 'en_cours'} />
          <Text size="xs" c="dimmed" mt={2}>{job.detail}</Text>
        </Box>
      )}
      {job.error && <Alert color="red" variant="light" p="xs" mb={6} icon={<IconAlertTriangle size={16} />}>{job.error}</Alert>}
      {job.log.length > 0 && (
        <ScrollArea.Autosize mah={140}>
          <Code block fz="xs">{job.log.join('\n')}</Code>
        </ScrollArea.Autosize>
      )}
    </Paper>
  );
}

// --------------------------------------------------------------------------- Claude
const CLAUDE_STEP: Record<string, number> = { claude_absent: 0, claude_non_connecte: 1, consentement_requis: 2 };

export function ClaudeSetup({ status, busy, update, refresh }: Props) {
  const s = status.settings;
  const step = status.state in CLAUDE_STEP ? CLAUDE_STEP[status.state] : status.ready || status.models.length ? 3 : 0;
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [code, setCode] = useState('');
  const install = useSetupJob(() => void refresh());
  const login = useSetupJob(() => void refresh());
  const [path, setPath] = useState(s.claude_path);
  useEffect(() => setPath(s.claude_path), [s.claude_path]);

  const startInstall = async () => {
    setConfirmOpen(false);
    try { install.setJob(await call('ai.setup_claude_install', { confirm: true })); } catch (err) { notifyError(err, 'Installation impossible'); }
  };
  const startLogin = async () => {
    try { login.setJob(await call('ai.setup_claude_login', {})); } catch (err) { notifyError(err, 'Connexion impossible'); }
  };
  const sendCode = async () => {
    if (!login.job) return;
    try { login.setJob(await call('ai.setup_code', { job_id: login.job.id, code })); setCode(''); } catch (err) { notifyError(err, 'Code refusé'); }
  };

  return (
    <Stack gap="sm">
      <Stepper active={step} size="sm" orientation="vertical" allowNextStepsSelect={false}>
        <Stepper.Step label="Installer Claude Code" description={status.claude_executable ? `Installé : ${status.claude_executable}` : "Programme gratuit d'Anthropic"}>
          <Text size="sm" mb={6}>
            Claude Code n'est pas encore installé sur cet ordinateur. STATPFE peut l'installer avec la commande officielle
            d'Anthropic ({status.claude_install.shell}) :
          </Text>
          <Group gap="xs" mb="xs" wrap="nowrap">
            <Code style={{ flex: 1 }}>{status.claude_install.command}</Code>
            <CopyButton value={status.claude_install.command}>
              {({ copied, copy }) => (
                <Button size="compact-sm" variant="default" leftSection={copied ? <IconCheck size={14} /> : <IconCopy size={14} />} onClick={copy}>
                  {copied ? 'Copiée' : 'Copier'}
                </Button>
              )}
            </CopyButton>
          </Group>
          <Group gap="xs">
            <Button size="sm" leftSection={<IconDownload size={16} />} disabled={install.job?.status === 'en_cours'}
              onClick={() => setConfirmOpen(true)}>Installer Claude Code</Button>
            <Button size="sm" variant="default" leftSection={<IconRefresh size={16} />} loading={busy} onClick={() => void refresh()}>
              Je l'ai installé moi-même : vérifier
            </Button>
            <Anchor size="sm" onClick={() => void openLink(status.claude_install.doc)}>Guide d'installation <IconExternalLink size={12} /></Anchor>
          </Group>
          {install.job && <JobView job={install.job} onCancel={() => void install.cancel()} />}
        </Stepper.Step>

        <Stepper.Step label="Se connecter à votre compte Claude"
          description={status.claude_auth?.logged_in ? 'Connecté' : 'Abonnement Claude (Pro, Max…) ou compte Console'}>
          <Text size="sm" mb={6}>
            Claude Code utilise votre propre compte Claude : STATPFE ne voit ni votre mot de passe ni vos identifiants.
            Une page de connexion va s'ouvrir dans votre navigateur.
          </Text>
          <Group gap="xs">
            <Button size="sm" leftSection={<IconLogin size={16} />} disabled={login.job?.status === 'en_cours'} onClick={() => void startLogin()}>
              Se connecter à Claude
            </Button>
            <Button size="sm" variant="default" leftSection={<IconRefresh size={16} />} loading={busy} onClick={() => void refresh()}>Vérifier</Button>
          </Group>
          {login.job?.status === 'en_cours' && (
            <Paper withBorder p="sm" mt="xs" bg="var(--mantine-color-blue-0)">
              <Text size="sm">Terminez la connexion dans la page qui s'est ouverte.</Text>
              {login.job.url && (
                <Button mt={6} size="compact-sm" variant="light" leftSection={<IconExternalLink size={14} />}
                  onClick={() => void openLink(login.job!.url!)}>La page ne s'est pas ouverte : l'ouvrir</Button>
              )}
              {login.job.waiting_code && (
                <Group mt="xs" gap="xs" align="flex-end">
                  <TextInput size="xs" style={{ flex: 1 }} label="Si la page affiche un code, collez-le ici" value={code}
                    onChange={(e) => setCode(e.currentTarget.value)} onKeyDown={(e) => { if (e.key === 'Enter') void sendCode(); }} />
                  <Button size="xs" disabled={!code.trim()} onClick={() => void sendCode()}>Envoyer le code</Button>
                </Group>
              )}
            </Paper>
          )}
          {login.job && login.job.status !== 'en_cours' && <JobView job={login.job} onCancel={() => void login.cancel()} />}
        </Stepper.Step>

        <Stepper.Step label="Autoriser l'envoi des résultats" description={s.cloud_consent_at ? 'Autorisé' : 'Obligatoire pour ce mode'}>
          <ConsentPanel status={status} busy={busy} update={update} />
        </Stepper.Step>

        <Stepper.Step label="Choisir le modèle Claude" description={step >= 3 ? `Choisi : ${s.model}` : undefined}>
        <Radio.Group label="Modèle Claude" description="Vous pouvez en changer à tout moment ; le modèle utilisé est noté sous chaque texte et dans le rapport."
          value={s.model} onChange={(v) => void update({ model: v })}>
          <SimpleGrid cols={{ base: 1, md: 2 }} mt="xs">
            {status.claude_models.map((m) => (
              <Radio.Card key={m.name} value={m.name} p="sm" radius="md" disabled={busy}>
                <Group wrap="nowrap" align="flex-start">
                  <Radio.Indicator />
                  <Box>
                    <Group gap={6}><Text fw={600} size="sm">{m.label}</Text>{m.recommended && <Badge size="xs" color="teal">conseillé</Badge>}</Group>
                    <Text size="xs" c="dimmed">{m.description}</Text>
                  </Box>
                </Group>
              </Radio.Card>
            ))}
          </SimpleGrid>
        </Radio.Group>
              </Stepper.Step>
      </Stepper>

      {step >= 3 && <ConsentPanel status={status} busy={busy} update={update} />}

      <TextInput size="xs" label="Chemin de Claude Code (facultatif)"
        description={status.claude_executable ? `Trouvé automatiquement : ${status.claude_executable}` : 'Laissez vide pour le chercher automatiquement.'}
        placeholder="Par exemple C:\Users\vous\.local\bin\claude.exe" value={path}
        onChange={(e) => setPath(e.currentTarget.value)} disabled={busy}
        onBlur={() => { if (path !== s.claude_path) void update({ claude_path: path }); }} />

      <Modal opened={confirmOpen} onClose={() => setConfirmOpen(false)} title="Installer Claude Code ?" centered>
        <Stack gap="sm">
          <Text size="sm">
            STATPFE va exécuter la commande officielle d'Anthropic, qui télécharge Claude Code depuis claude.ai et
            l'installe dans votre dossier personnel (sans droits d'administrateur). Aucune donnée d'étude n'est envoyée.
          </Text>
          <Code block>{status.claude_install.command}</Code>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setConfirmOpen(false)}>Annuler</Button>
            <Button leftSection={<IconDownload size={16} />} onClick={() => void startInstall()}>Installer</Button>
          </Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

function ConsentPanel({ status, busy, update }: { status: AiStatus; busy: boolean; update: Update }) {
  const s = status.settings;
  return (
    <Paper withBorder p="sm" bg="var(--mantine-color-orange-0)">
      <Text fw={600} size="sm" mb={4}>Mode en ligne : les résultats calculés quittent cet ordinateur</Text>
      <Text size="sm">
        Claude Code envoie chaque demande au service Claude d'Anthropic, selon les conditions de votre compte. Seuls les
        résultats déjà calculés sont transmis (vous pouvez les afficher avant chaque envoi) : jamais les données brutes, ni
        les variables identifiantes, ni le titre de l'étude. Claude Code est lancé sans aucun outil : il ne peut ni lire
        vos fichiers ni exécuter de commande. Vérifiez que votre établissement autorise ce type de service pour vos données.
      </Text>
      <Switch mt="sm" checked={!!s.cloud_consent_at} disabled={busy}
        onChange={(e) => void update({ cloud_consent: e.currentTarget.checked })}
        label="J'autorise l'envoi des résultats calculés à Claude (Anthropic)"
        description={s.cloud_consent_at ? `Autorisation donnée le ${new Date(s.cloud_consent_at).toLocaleString('fr-FR')} ; vous pouvez la retirer à tout moment.` : undefined} />
    </Paper>
  );
}

// --------------------------------------------------------------------------- IA locale
export function LocalSetup({ status, busy, update, refresh }: Props) {
  const s = status.settings;
  const ollama = s.provider === 'ollama';
  const absent = status.state === 'serveur_absent';
  const [pullModel, setPullModel] = useState<LocalModelInfo | null>(null);
  const [agree, setAgree] = useState(false);
  const pull = useSetupJob((j) => {
    void (async () => {
      await refresh();
      if (j.status === 'termine' && typeof j.result.model === 'string') await update({ model: j.result.model });
    })();
  });

  const startPull = async () => {
    if (!pullModel) return;
    const name = pullModel.name;
    setPullModel(null);
    setAgree(false);
    try { pull.setJob(await call('ai.setup_ollama_pull', { model: name, confirm: true })); } catch (err) { notifyError(err, 'Téléchargement impossible'); }
  };
  const startOllama = async () => {
    try {
      await call('ai.setup_ollama_start', {});
      window.setTimeout(() => void refresh(), 2500);
    } catch (err) { notifyError(err, 'Ollama ne démarre pas'); }
  };

  return (
    <Stack gap="sm">
      {ollama && absent && status.ollama_installed === false && (
        <Paper withBorder p="sm">
          <Text fw={600} size="sm" mb={4}>1. Installer Ollama (gratuit)</Text>
          <Text size="sm" mb={6}>
            Ollama fait tourner les modèles sur votre ordinateur, sans compte ni abonnement. Téléchargez l'installateur
            officiel, installez-le, puis revenez ici.
          </Text>
          <Group gap="xs">
            <Button size="sm" leftSection={<IconExternalLink size={16} />} onClick={() => void openLink(status.ollama_download)}>
              Télécharger Ollama
            </Button>
            <Button size="sm" variant="default" leftSection={<IconRefresh size={16} />} loading={busy} onClick={() => void refresh()}>
              J'ai installé Ollama : vérifier
            </Button>
          </Group>
        </Paper>
      )}
      {ollama && absent && status.ollama_installed && (
        <Paper withBorder p="sm">
          <Text size="sm" mb={6}>Ollama est installé mais n'est pas lancé.</Text>
          <Group gap="xs">
            <Button size="sm" leftSection={<IconPlayerPlay size={16} />} onClick={() => void startOllama()}>Démarrer Ollama</Button>
            <Button size="sm" variant="default" leftSection={<IconRefresh size={16} />} loading={busy} onClick={() => void refresh()}>Vérifier</Button>
          </Group>
        </Paper>
      )}

      {ollama && !absent && (
        <Box>
          <Text fw={600} size="sm" mb={4}>Modèles gratuits conseillés</Text>
          <Text size="xs" c="dimmed" mb={6}>
            Selon la mémoire de cet ordinateur. Le téléchargement est fait par Ollama (une seule fois) ; ensuite tout
            fonctionne sans Internet.
          </Text>
          <Table withTableBorder verticalSpacing={6} fz="sm">
            <Table.Thead>
              <Table.Tr><Table.Th>Modèle</Table.Th><Table.Th>Taille</Table.Th><Table.Th>Mémoire</Table.Th><Table.Th>Remarque</Table.Th><Table.Th /></Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {status.local_catalog.map((m) => (
                <Table.Tr key={m.name} opacity={m.fits ? 1 : 0.55}>
                  <Table.Td>
                    <Group gap={6} wrap="nowrap"><Code>{m.name}</Code>{m.recommended && <Badge size="xs" color="teal">conseillé</Badge>}</Group>
                  </Table.Td>
                  <Table.Td>{m.download_gb.toLocaleString('fr-FR')} Go</Table.Td>
                  <Table.Td>{m.min_memory_gb} Go{!m.fits && ' (trop peu ici)'}</Table.Td>
                  <Table.Td><Text size="xs">{m.note}</Text></Table.Td>
                  <Table.Td>
                    {m.installed ? (
                      s.model === m.name || s.model === `${m.name}:latest`
                        ? <Badge color="teal" variant="light">utilisé</Badge>
                        : <Button size="compact-xs" variant="light" disabled={busy} onClick={() => void update({ model: m.name })}>Utiliser</Button>
                    ) : (
                      <Button size="compact-xs" variant={m.recommended ? 'filled' : 'default'} leftSection={<IconDownload size={12} />}
                        disabled={pull.job?.status === 'en_cours'} onClick={() => setPullModel(m)}>Télécharger</Button>
                    )}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {pull.job && <JobView job={pull.job} onCancel={() => void pull.cancel()} />}
        </Box>
      )}

      <Modal opened={pullModel !== null} onClose={() => { setPullModel(null); setAgree(false); }} title="Télécharger un modèle ?" centered>
        {pullModel && (
          <Stack gap="sm">
            <Text size="sm">
              Ollama va télécharger <Code>{pullModel.name}</Code> (environ {pullModel.download_gb.toLocaleString('fr-FR')} Go)
              depuis sa bibliothèque en ligne. Aucune donnée d'étude n'est envoyée ; une fois téléchargé, le modèle
              fonctionne sans Internet.
            </Text>
            {!pullModel.fits && (
              <Alert color="orange" variant="light" icon={<IconAlertTriangle size={16} />}>
                Ce modèle demande plus de mémoire que cet ordinateur n'en a : il risque d'être très lent.
              </Alert>
            )}
            <Checkbox checked={agree} onChange={(e) => setAgree(e.currentTarget.checked)}
              label={`J'ai assez d'espace disque et je confirme le téléchargement`} />
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setPullModel(null)}>Annuler</Button>
              <Button disabled={!agree} leftSection={<IconDownload size={16} />} onClick={() => void startPull()}>Télécharger</Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}
