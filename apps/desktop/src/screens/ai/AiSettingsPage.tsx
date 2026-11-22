import { useCallback, useEffect, useState } from 'react';
import {
  Alert, Badge, Box, Button, Code, Group, List, Loader, NumberInput, Paper, SegmentedControl, Select, SimpleGrid,
  Slider, Stack, Switch, Text, TextInput, Title,
} from '@mantine/core';
import {
  IconAlertTriangle, IconCheck, IconCpu, IconLock, IconPlugConnected, IconRefresh, IconSparkles,
} from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { AiProvider, AiSettings, AiState, AiStatus } from '../../engine/types';
import { formatBytes } from '../../lib/format';
import { notifyError } from '../../App';

export const AI_STATE_COLOR: Record<AiState, string> = {
  desactivee: 'gray', serveur_absent: 'red', aucun_modele: 'orange', modele_absent: 'orange',
  modele_a_choisir: 'yellow', prete: 'teal', inconnu: 'gray', consentement_requis: 'orange', claude_absent: 'red',
};

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

  const [path, setPath] = useState('');
  useEffect(() => { if (status) setPath(status.settings.claude_path); }, [status]);

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
          <Group justify="space-between" mb="sm">
            <Group gap="xs"><IconPlugConnected size={18} /><Text fw={600}>Modèle utilisé</Text></Group>
            <Button size="xs" variant="light" leftSection={<IconRefresh size={14} />} loading={busy} onClick={() => void refresh()}>
              Tester la connexion
            </Button>
          </Group>
          <Stack gap="sm">
            <SegmentedControl value={s.provider} disabled={busy}
              data={status.providers.map((p) => ({ value: p.key, label: p.label }))}
              onChange={(v) => void update({ provider: v as AiProvider })} />
            {!cloud && (
              <TextInput label="Adresse" description="Uniquement une adresse de cet ordinateur (127.0.0.1, localhost ou ::1)."
                value={url} onChange={(e) => setUrl(e.currentTarget.value)} disabled={busy}
                onBlur={() => { if (url !== s.base_url) void update({ base_url: url }); }}
                onKeyDown={(e) => { if (e.key === 'Enter' && url !== s.base_url) void update({ base_url: url }); }} />
            )}
            {cloud && (
              <Paper withBorder p="sm" bg="var(--mantine-color-orange-0)">
                <Text fw={600} size="sm" mb={4}>Mode en ligne : les résultats calculés quittent cet ordinateur</Text>
                <List size="sm" spacing={2}>
                  <List.Item>Claude Code (programme d'Anthropic, à installer et à connecter à votre compte Claude) envoie
                    la demande au service Claude d'Anthropic, selon les conditions de votre compte.</List.Item>
                  <List.Item>Seuls les résultats déjà calculés sont transmis (vous pouvez les afficher avant chaque envoi) :
                    jamais les données brutes, ni les variables identifiantes, ni le titre de l'étude.</List.Item>
                  <List.Item>Claude Code est lancé sans aucun outil : il ne peut ni lire vos fichiers ni exécuter de commande.</List.Item>
                  <List.Item>Vérifiez que votre établissement et votre comité d'éthique autorisent ce type de service pour vos données.</List.Item>
                </List>
                <Switch mt="sm" checked={!!s.cloud_consent_at} disabled={busy}
                  onChange={(e) => void update({ cloud_consent: e.currentTarget.checked })}
                  label="J'autorise l'envoi des résultats calculés à Claude (Anthropic)"
                  description={s.cloud_consent_at ? `Autorisation donnée le ${new Date(s.cloud_consent_at).toLocaleString('fr-FR')} ; vous pouvez la retirer à tout moment.` : undefined} />
              </Paper>
            )}
            {cloud && (
              <TextInput label="Chemin de Claude Code (facultatif)"
                description={status.claude_executable ? `Trouvé automatiquement : ${status.claude_executable}` : "Laissez vide pour le chercher automatiquement."}
                placeholder="Par exemple C:\Users\vous\.local\bin\claude.exe" value={path}
                onChange={(e) => setPath(e.currentTarget.value)} disabled={busy}
                onBlur={() => { if (path !== s.claude_path) void update({ claude_path: path }); }} />
            )}
            <Alert variant="light" color={AI_STATE_COLOR[status.state]}
              icon={status.ready ? <IconCheck size={18} /> : <IconAlertTriangle size={18} />}>
              <Text size="sm" fw={550}>{status.message}</Text>
              {status.server?.error && <Text size="xs" c="dimmed">{status.server.error}</Text>}
              {status.state === 'serveur_absent' && s.provider === 'ollama' && (
                <Text size="sm" mt={6}>
                  Installez Ollama (gratuit, ollama.com), lancez-le, puis installez un modèle, par exemple
                  {' '}<Code>ollama pull {rec?.examples[0] ?? 'qwen2.5:3b'}</Code>. Revenez ensuite ici et testez la connexion.
                </Text>
              )}
              {status.state === 'claude_absent' && (
                <Text size="sm" mt={6}>
                  Installez Claude Code (claude.com/claude-code), lancez <Code>claude</Code> une fois dans un terminal pour
                  vous connecter à votre compte, puis testez à nouveau la connexion.
                </Text>
              )}
              {status.state === 'aucun_modele' && (
                <Text size="sm" mt={6}>
                  Installez un modèle, par exemple <Code>ollama pull {rec?.examples[0] ?? 'qwen2.5:3b'}</Code>, puis
                  testez à nouveau la connexion.
                </Text>
              )}
            </Alert>
            {status.models.length > 0 && (status.state !== 'consentement_requis') && (
              <Select label="Modèle" placeholder="Choisir un modèle installé" value={s.model || null} disabled={busy}
                allowDeselect={false}
                data={status.models.map((m) => ({
                  value: m.name,
                  label: [m.name, m.parameters, m.quantization, m.size ? formatBytes(m.size) : null].filter(Boolean).join(' · '),
                }))}
                onChange={(v) => v && void update({ model: v })} />
            )}
          </Stack>
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
