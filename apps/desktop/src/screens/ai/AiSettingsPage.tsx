import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import {
  Accordion, Alert, Badge, Box, Button, Code, Group, List, Loader, NumberInput, Paper, SegmentedControl, Select,
  SimpleGrid, Slider, Stack, Switch, Table, Text, TextInput, Title, UnstyledButton,
} from '@mantine/core';
import {
  IconAlertTriangle, IconCheck, IconCloud, IconCpu, IconDeviceDesktop, IconLock, IconPlugConnected, IconRefresh,
  IconSparkles,
} from '@tabler/icons-react';
import { ClaudeSetup, LocalSetup } from './AiSetup';
import { call } from '../../engine/client';
import type { AiProvider, AiSettings, AiState, AiStatus } from '../../engine/types';
import { formatBytes } from '../../lib/format';
import { notifyError } from '../../App';

export const AI_STATE_COLOR: Record<AiState, string> = {
  desactivee: 'gray', serveur_absent: 'red', aucun_modele: 'orange', modele_absent: 'orange',
  modele_a_choisir: 'yellow', prete: 'teal', inconnu: 'gray', consentement_requis: 'orange', claude_absent: 'red',
  claude_non_connecte: 'orange',
};

const COMPARISON: [string, string, string][] = [
  ['Qualité de rédaction', 'Très bonne, nuancée', 'Correcte à bonne selon le modèle et le PC'],
  ['Vitesse', 'Quelques secondes', 'De quelques secondes à une minute sans carte graphique'],
  ['Coût', 'Compte dans votre abonnement Claude', 'Gratuit'],
  ['Confidentialité', 'Résultats calculés envoyés à Anthropic (avec votre autorisation)', "Rien ne quitte l'ordinateur"],
  ['Internet', 'Nécessaire', "Seulement pour télécharger le modèle, une fois"],
  ['Installation', 'Claude Code + connexion au compte (assistée)', 'Ollama + un modèle de 1 à 5 Go (assistée)'],
];

function ChoiceCard({ active, disabled, onClick, icon, title, badge, text }: {
  active: boolean; disabled: boolean; onClick: () => void; icon: ReactNode; title: string; badge: ReactNode; text: string;
}) {
  return (
    <UnstyledButton onClick={onClick} disabled={disabled} aria-pressed={active}>
      <Paper withBorder p="md" radius="md" h="100%"
        style={{ borderColor: active ? 'var(--mantine-color-blue-6)' : undefined, borderWidth: active ? 2 : 1,
          background: active ? 'var(--mantine-color-blue-0)' : undefined }}>
        <Group gap="xs" mb={4}>{icon}<Text fw={650}>{title}</Text>{badge}{active && <Badge size="sm" variant="outline">choisie</Badge>}</Group>
        <Text size="sm" c="dimmed">{text}</Text>
      </Paper>
    </UnstyledButton>
  );
}

interface Props { onStatus?: (s: AiStatus) => void }

/** Réglages de l'IA locale : application entière (pas un projet). Désactivée par défaut. */
export function AiSettingsPage({ onStatus }: Props) {
  const [status, setStatus] = useState<AiStatus | null>(null);
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);

  const apply = useCallback((s: AiStatus) => {
    setStatus(s);
    setUrl(s.settings.base_url);
    onStatus?.(s);
  }, [onStatus]);

  const refresh = useCallback(async () => {
    setBusy(true);
    try { apply(await call('ai.status', {})); } catch (err) { notifyError(err, "État de l'IA indisponible"); }
    finally { setBusy(false); }
  }, [apply]);

  useEffect(() => { void refresh(); }, [refresh]);

  const update = async (changes: Partial<AiSettings> & { cloud_consent?: boolean }) => {
    setBusy(true);
    try { apply(await call('ai.update_settings', { changes })); } catch (err) {
      notifyError(err, 'Réglage refusé');
      if (status) setUrl(status.settings.base_url);
    } finally { setBusy(false); }
  };

  if (!status) return <Box p="xl"><Loader size="sm" /></Box>;
  const s = status.settings;
  const r = status.resources;
  const rec = r.recommendation;
  const cloud = s.provider === 'claude_code';

  return (
    <Stack p="xl" gap="lg" maw={980}>
      <Group justify="space-between" align="flex-start">
        <Box>
          <Group gap="xs">
            <IconSparkles size={22} />
            <Title order={2}>IA (aide à la rédaction)</Title>
            <Badge variant="light" color="gray">optionnelle</Badge>
          </Group>
          <Text c="dimmed" size="sm" mt={4} maw={700}>
            Un modèle de langage peut vous aider à expliquer une méthode ou un tableau, à interpréter les résultats et à
            proposer des paragraphes prudents, à partir des résultats déjà calculés. Deux possibilités : un modèle
            installé sur cet ordinateur, ou Claude d'Anthropic via Claude Code (en ligne). STATPFE fonctionne entièrement
            sans IA.
          </Text>
        </Box>
        <Badge size="lg" variant="light" color={AI_STATE_COLOR[status.state]}>
          {status.state === 'prete' ? 'Prête' : status.state === 'desactivee' ? 'Désactivée' : 'Non disponible'}
        </Badge>
      </Group>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Paper withBorder p="md">
          <Text fw={600} mb={6}>Ce que fait l'IA</Text>
          <List size="sm" spacing={4} icon={<IconCheck size={14} color="var(--mantine-color-teal-7)" />}>
            <List.Item>Explique une méthode, un tableau ou une figure.</List.Item>
            <List.Item>Propose un paragraphe de résultats, des pistes de discussion, les limites visibles, une conclusion.</List.Item>
            <List.Item>Reformule un texte que vous avez écrit.</List.Item>
          </List>
        </Paper>
        <Paper withBorder p="md">
          <Text fw={600} mb={6}>Ce qu'elle ne fait jamais</Text>
          <List size="sm" spacing={4} icon={<IconLock size={14} color="var(--mantine-color-red-7)" />}>
            <List.Item>Calculer, modifier les données ou une analyse : les nombres viennent du moteur.</List.Item>
            <List.Item>Lire vos données brutes ou les variables identifiantes.</List.Item>
            <List.Item>Envoyer quoi que ce soit hors de cet ordinateur sans votre autorisation explicite.</List.Item>
            <List.Item>Valider un résultat : chaque texte est une proposition à vérifier.</List.Item>
          </List>
        </Paper>
      </SimpleGrid>

      <Paper withBorder p="md">
        <Switch size="md" checked={s.enabled} disabled={busy} onChange={(e) => void update({ enabled: e.currentTarget.checked })}
          label={<Text fw={600}>Activer l'IA</Text>}
          description="Désactivée par défaut. Vous pouvez la désactiver à tout moment ; vos projets restent identiques." />
      </Paper>

      {s.enabled && (
        <Paper withBorder p="md">
          <Text fw={600} mb="sm">Choisissez votre IA</Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} mb="sm">
            <ChoiceCard active={cloud} disabled={busy} onClick={() => { if (!cloud) void update({ provider: 'claude_code' }); }}
              icon={<IconCloud size={22} />} title="Claude (en ligne)" badge={<Badge size="sm" color="violet">meilleure qualité</Badge>}
              text="Claude d'Anthropic, via Claude Code. Rédaction la plus fiable et la plus nuancée. Nécessite un compte Claude et Internet ; les résultats calculés sont envoyés à Anthropic avec votre autorisation." />
            <ChoiceCard active={!cloud} disabled={busy} onClick={() => { if (cloud) void update({ provider: 'ollama' }); }}
              icon={<IconDeviceDesktop size={22} />} title="IA locale" badge={<Badge size="sm" color="teal">gratuite</Badge>}
              text="Un modèle libre (Qwen, Llama, Mistral…) qui tourne sur cet ordinateur avec Ollama. Gratuit, sans compte, rien ne quitte l'ordinateur ; qualité selon la puissance du PC." />
          </SimpleGrid>
          <Table withTableBorder fz="sm" mb="md" verticalSpacing={4}>
            <Table.Thead>
              <Table.Tr><Table.Th /><Table.Th>Claude (en ligne)</Table.Th><Table.Th>IA locale</Table.Th></Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {COMPARISON.map(([k, c, l]) => (
                <Table.Tr key={k}><Table.Td fw={550}>{k}</Table.Td><Table.Td>{c}</Table.Td><Table.Td>{l}</Table.Td></Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <Group justify="space-between" mb="sm">
            <Group gap="xs"><IconPlugConnected size={18} /><Text fw={600}>{cloud ? 'Mise en route de Claude' : 'Mise en route de l\'IA locale'}</Text></Group>
            <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} loading={busy} onClick={() => void refresh()}>
              Vérifier
            </Button>
          </Group>
          <Alert variant="light" mb="sm" color={AI_STATE_COLOR[status.state]}
            icon={status.ready ? <IconCheck size={18} /> : <IconAlertTriangle size={18} />}>
            <Text size="sm" fw={550}>{status.message}</Text>
            {status.server?.error && !cloud && <Text size="xs" c="dimmed">{status.server.error}</Text>}
          </Alert>

          {cloud ? <ClaudeSetup status={status} busy={busy} update={update} refresh={refresh} /> : (
            <Stack gap="sm">
              <LocalSetup status={status} busy={busy} update={update} refresh={refresh} />
              {status.models.length > 0 && (
                <Select label="Modèle utilisé" placeholder="Choisir un modèle installé" value={s.model || null} disabled={busy}
                  allowDeselect={false}
                  data={status.models.map((m) => ({
                    value: m.name,
                    label: [m.name, m.parameters, m.quantization, m.size ? formatBytes(m.size) : null].filter(Boolean).join(' · '),
                  }))}
                  onChange={(v) => v && void update({ model: v })} />
              )}
              <Accordion variant="contained">
                <Accordion.Item value="serveur">
                  <Accordion.Control><Text size="sm">Serveur de modèles (avancé)</Text></Accordion.Control>
                  <Accordion.Panel>
                    <Stack gap="xs">
                      <SegmentedControl value={s.provider} disabled={busy}
                        data={status.providers.filter((p) => p.key !== 'claude_code').map((p) => ({ value: p.key, label: p.label }))}
                        onChange={(v) => void update({ provider: v as AiProvider })} />
                      <TextInput label="Adresse" description="Uniquement une adresse de cet ordinateur (127.0.0.1, localhost ou ::1)."
                        value={url} onChange={(e) => setUrl(e.currentTarget.value)} disabled={busy}
                        onBlur={() => { if (url !== s.base_url) void update({ base_url: url }); }}
                        onKeyDown={(e) => { if (e.key === 'Enter' && url !== s.base_url) void update({ base_url: url }); }} />
                    </Stack>
                  </Accordion.Panel>
                </Accordion.Item>
              </Accordion>
            </Stack>
          )}
        </Paper>
      )}

      <Paper withBorder p="md">
        <Group gap="xs" mb="sm"><IconCpu size={18} /><Text fw={600}>Ressources de cet ordinateur</Text></Group>
        <SimpleGrid cols={{ base: 2, md: 4 }} mb="sm">
          <Stat label="Mémoire totale" value={formatBytes(r.memory_total)} />
          <Stat label="Mémoire libre" value={formatBytes(r.memory_available)} />
          <Stat label="Processeurs (cœurs)" value={r.cpu_cores ? String(r.cpu_cores) : 'inconnu'} />
          <Stat label="Espace disque libre" value={formatBytes(r.disk_free)} />
        </SimpleGrid>
        {rec && (
          <Text size="sm">
            Taille de modèle conseillée : <b>{rec.size}</b> (par exemple {rec.examples.map((e, i) => (
              <span key={e}>{i > 0 ? ', ' : ''}<Code>{e}</Code></span>))}). {rec.note}
          </Text>
        )}
        {r.warnings.map((w) => (
          <Alert key={w} mt="xs" color="orange" variant="light" icon={<IconAlertTriangle size={16} />}>{w}</Alert>
        ))}
        <Text size="xs" c="dimmed" mt="xs">Conseil indicatif, fondé sur la mémoire de l'ordinateur ; une carte graphique accélère nettement la rédaction.</Text>
      </Paper>

      {s.enabled && !cloud && (
        <Paper withBorder p="md">
          <Text fw={600} mb="sm">Réglages avancés</Text>
          <SimpleGrid cols={{ base: 1, md: 3 }}>
            <Box>
              <Text size="sm" fw={500}>Créativité (température) : {s.temperature.toLocaleString('fr-FR')}</Text>
              <Text size="xs" c="dimmed" mb={8}>Basse = plus fidèle et plus stable. Conseillé : 0,2.</Text>
              <Slider min={0} max={1} step={0.1} value={s.temperature} disabled={busy}
                onChangeEnd={(v) => void update({ temperature: v })} label={(v) => v.toLocaleString('fr-FR')} />
            </Box>
            <NumberInput label="Longueur maximale (jetons)" min={64} max={2048} step={50} value={s.max_tokens}
              disabled={busy} onBlur={(e) => { const v = Number(e.currentTarget.value.replace(/\s/g, '')); if (v && v !== s.max_tokens) void update({ max_tokens: v }); }} />
            <NumberInput label="Délai maximal (secondes)" min={10} max={900} step={30} value={s.timeout}
              disabled={busy} onBlur={(e) => { const v = Number(e.currentTarget.value.replace(/\s/g, '')); if (v && v !== s.timeout) void update({ timeout: v }); }} />
          </SimpleGrid>
        </Paper>
      )}
    </Stack>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Box>
      <Text size="xs" c="dimmed">{label}</Text>
      <Text fw={650}>{value}</Text>
    </Box>
  );
}
