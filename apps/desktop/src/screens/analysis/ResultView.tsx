import { useState } from 'react';
import {
  Accordion, Alert, Badge, Box, Button, Code, Group, Menu, Paper, SimpleGrid, Stack, Table, Text,
  Textarea, ThemeIcon, Title, Tooltip,
} from '@mantine/core';
import {
  IconAlertCircle, IconAlertTriangle, IconBan, IconCheck, IconCopy, IconDots, IconInfoCircle,
  IconRefresh, IconTrash,
} from '@tabler/icons-react';
import type { Analysis, DiagLevel, ProjectState, ReproductionReport, ResultTable, SummaryStat } from '../../engine/types';
import { AiAssistPanel } from './AiAssistPanel';
import { ChartView } from '../../components/charts/Charts';
import { formatCellOf, formatStat } from '../../lib/stats';
import { formatDateTime } from '../../lib/format';

const LEVEL: Record<DiagLevel, { color: string; label: string; icon: typeof IconBan }> = {
  bloquant: { color: 'red', label: 'Erreur bloquante', icon: IconBan },
  important: { color: 'orange', label: 'Avertissement important', icon: IconAlertTriangle },
  methodologique: { color: 'yellow', label: 'Avertissement méthodologique', icon: IconAlertCircle },
  information: { color: 'gray', label: 'Information', icon: IconInfoCircle },
};
const ORDER: DiagLevel[] = ['bloquant', 'important', 'methodologique', 'information'];

export const STATUS_COLOR: Record<string, string> = {
  a_jour: 'teal', donnees_modifiees: 'orange', version_supprimee: 'red', jeu_supprime: 'red', version_a_corriger: 'red',
};

interface Props {
  analysis: Analysis;
  onReproduce: () => Promise<ReproductionReport | null>;
  onDuplicate: () => void;
  onDelete: () => void;
  onSaveNote: (note: string) => void;
  onProjectChange?: (p: ProjectState) => void;
  onOpenAiSettings?: () => void;
}

export function ResultView({ analysis, onReproduce, onDuplicate, onDelete, onSaveNote, onProjectChange, onOpenAiSettings }: Props) {
  const r = analysis.result;
  const [note, setNote] = useState(analysis.note);
  const [report, setReport] = useState<ReproductionReport | null>(null);
  const [checking, setChecking] = useState(false);

  const stats = r.summary;
  const ci = pairCi(stats);
  const diagnostics = [...r.diagnostics].sort((a, b) => ORDER.indexOf(a.level) - ORDER.indexOf(b.level));

  return (
    <Stack gap="lg" maw={1100}>
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <Box style={{ minWidth: 0 }}>
          <Group gap="xs" mb={4}>
            <Badge variant="light">{analysis.method_label}</Badge>
            <Tooltip label={analysis.status_label} multiline w={260}>
              <Badge variant="dot" color={STATUS_COLOR[analysis.status]}>
                {analysis.status === 'a_jour' ? 'Données inchangées' : 'À vérifier'}
              </Badge>
            </Tooltip>
          </Group>
          <Title order={3}>{analysis.title}</Title>
          <Text size="sm" c="dimmed">
            {analysis.dataset_name ?? 'Jeu de données supprimé'} · {analysis.version_name} · calculée le{' '}
            {formatDateTime(analysis.created_at)}
          </Text>
        </Box>
        <Group gap="xs" wrap="nowrap">
          <Tooltip label="Recalculer avec les mêmes paramètres et comparer au résultat enregistré" multiline w={240}>
            <Button variant="light" leftSection={<IconRefresh size={16} />} loading={checking}
              onClick={async () => { setChecking(true); try { setReport(await onReproduce()); } finally { setChecking(false); } }}>
              Reproduire
            </Button>
          </Tooltip>
          <Menu position="bottom-end" withinPortal>
            <Menu.Target>
              <Button variant="default" px="xs" aria-label="Autres actions"><IconDots size={18} /></Button>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconCopy size={16} />} onClick={onDuplicate}>
                Dupliquer (nouvelle analyse avec ces réglages)
              </Menu.Item>
              <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={onDelete}>Supprimer l'analyse</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>

      {analysis.status !== 'a_jour' && (
        <Alert color={STATUS_COLOR[analysis.status]} variant="light" icon={<IconAlertTriangle size={18} />}>
          {analysis.status_label}. Le résultat ci-dessous correspond aux données au moment du calcul.
        </Alert>
      )}

      {report && <ReproductionAlert report={report} onClose={() => setReport(null)} />}

      {stats.length > 0 && (
        <SimpleGrid cols={{ base: 2, md: 4 }}>
          {stats.filter((s) => s.kind !== 'ci').map((s) => <StatCard key={s.key} stat={s} />)}
          {ci && (
            <Paper withBorder p="sm">
              <Text size="xs" c="dimmed">Intervalle de confiance</Text>
              <Text fw={650} size="lg">[{formatStat(ci[0].value, 'ci', 3)} ; {formatStat(ci[1].value, 'ci', 3)}]</Text>
            </Paper>
          )}
        </SimpleGrid>
      )}

      {r.interpretation.length > 0 && (
        <Paper withBorder p="md" bg="var(--mantine-color-brand-0)">
          <Text size="xs" fw={700} c="brand.8" tt="uppercase" mb={6}>Lecture du résultat</Text>
          <Stack gap={6}>
            {r.interpretation.map((line, i) => <Text key={i} size="sm">{line}</Text>)}
          </Stack>
          <Text size="xs" c="dimmed" mt="sm">
            Texte produit par des règles fixes à partir des valeurs calculées ; il ne remplace pas votre analyse
            de la question de recherche.
          </Text>
        </Paper>
      )}

      {diagnostics.length > 0 && (
        <div>
          <Text fw={600} mb="xs">Diagnostics et avertissements ({diagnostics.length})</Text>
          <Stack gap="xs">
            {diagnostics.map((d, i) => {
              const meta = LEVEL[d.level];
              return (
                <Paper key={i} withBorder p="sm">
                  <Group gap="sm" wrap="nowrap" align="flex-start">
                    <ThemeIcon color={meta.color} variant="light" size="md"><meta.icon size={16} /></ThemeIcon>
                    <Box style={{ minWidth: 0 }}>
                      <Text size="sm" fw={550}>{d.title}</Text>
                      {d.detail && <Text size="xs" c="dimmed">{d.detail}</Text>}
                      <Text size="xs" c={meta.color === 'gray' ? 'dimmed' : meta.color}>{meta.label}</Text>
                    </Box>
                  </Group>
                </Paper>
              );
            })}
          </Stack>
        </div>
      )}

      {r.charts.length > 0 && (
        <SimpleGrid cols={{ base: 1, lg: r.charts.length > 1 ? 2 : 1 }}>
          {r.charts.map((c, i) => <ChartView key={i} chart={c} />)}
        </SimpleGrid>
      )}

      {r.tables.map((t, i) => <ResultTableView key={i} table={t} />)}

      <AiAssistPanel analysisId={analysis.id} onProjectChange={onProjectChange} onOpenSettings={onOpenAiSettings} />

      <Accordion variant="contained" chevronPosition="left">
        <Accordion.Item value="choice">
          <Accordion.Control>
            Choix de la méthode{' '}
            {analysis.choice?.mode === 'assistant' && (
              <Badge size="xs" ml={4} variant="light" color={analysis.choice.followed ? 'teal' : 'yellow'}>
                {analysis.choice.followed ? 'recommandation suivie' : 'autre méthode, justifiée'}
              </Badge>
            )}
          </Accordion.Control>
          <Accordion.Panel><ChoiceView analysis={analysis} /></Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="trace">
          <Accordion.Control>Traçabilité et reproductibilité</Accordion.Control>
          <Accordion.Panel>
            <Stack gap={6}>
              {r.missing && <Line label="Valeurs manquantes" value={r.missing.text} />}
              <Line label="Jeu de données" value={analysis.dataset_name ?? '—'} />
              <Line label="Version des données" value={analysis.version_name} />
              <Line label="Empreinte des données (SHA-256)" value={<Code>{analysis.data_fingerprint}</Code>} />
              <Line label="Méthode" value={analysis.method_label} />
              <Line label="Paramètres" value={<Code block>{JSON.stringify(analysis.params, null, 2)}</Code>} />
              <Line label="Environnement de calcul"
                value={Object.entries(analysis.environment).map(([k, v]) => `${k} ${v}`).join(' · ')} />
              <Line label="Date du calcul" value={formatDateTime(analysis.created_at)} />
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
        <Accordion.Item value="note">
          <Accordion.Control>Note personnelle {analysis.note ? '(1)' : ''}</Accordion.Control>
          <Accordion.Panel>
            <Textarea value={note} onChange={(e) => setNote(e.currentTarget.value)} maxLength={5000}
              placeholder="Par exemple : analyse prévue dans le protocole, choix justifié par…" />
            <Group justify="flex-end" mt="xs">
              <Button size="xs" variant="light" disabled={note === analysis.note} onClick={() => onSaveNote(note)}>
                Enregistrer la note
              </Button>
            </Group>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}

function ChoiceView({ analysis }: { analysis: Analysis }) {
  const c = analysis.choice ?? { mode: 'direct' };
  return (
    <Stack gap={6}>
      <Line label="Mode" value={c.mode === 'assistant' ? "Choisie avec l'assistant méthodologique"
        : c.mode === 'direct' ? "Choisie directement, sans l'assistant" : 'Non enregistré (analyse antérieure à cette version)'} />
      {c.mode === 'assistant' && (
        <>
          <Line label="Objectif" value={c.objective_label ?? '—'} />
          <Line label="Méthode recommandée" value={c.recommended_label ?? 'Aucune (situation non couverte)'} />
          {c.recommendation_reasons && c.recommendation_reasons.length > 0 && (
            <Line label="Raisons de la recommandation" value={c.recommendation_reasons.join(' ')} />
          )}
          <Line label="Méthode retenue" value={c.chosen_label ?? analysis.method_label} />
          {!c.followed && <Line label="Justification de l'écart" value={c.reason || '—'} />}
          {c.missing_information && c.missing_information.length > 0 && (
            <Line label="Informations manquantes au moment du choix" value={c.missing_information.join(' ')} />
          )}
          <Line label="Version des règles" value={c.rules_version ?? '—'} />
        </>
      )}
      {c.mode === 'direct' && c.reason && <Line label="Justification" value={c.reason} />}
      <Line label="Nature de l'analyse" value={c.purpose_label ?? 'Non précisée'} />
      <Line label="Hypothèse liée" value={c.hypothesis_text != null && c.hypothesis != null
        ? `H${c.hypothesis + 1} : ${c.hypothesis_text}` : 'Aucune'} />
      <Line label="Plan d'analyse" value={c.plan
        ? `Prévue au plan : ${c.plan.planned} (version ${c.plan.version})`
        : 'Non rattachée au plan (présentée dans le rapport comme non prévue ou antérieure au plan)'} />
      {c.plan?.deviation && (
        <Line label="Écart au plan" value={`${c.plan.deviations.join(' ; ')}. Raison : ${c.plan.reason || '—'}`} />
      )}
    </Stack>
  );
}

function pairCi(stats: SummaryStat[]): [SummaryStat, SummaryStat] | null {
  const lo = stats.find((s) => s.key === 'ci_low');
  const hi = stats.find((s) => s.key === 'ci_high');
  return lo && hi ? [lo, hi] : null;
}

function StatCard({ stat }: { stat: SummaryStat }) {
  const highlight = stat.kind === 'p' || stat.kind === 'effect';
  return (
    <Paper withBorder p="sm">
      <Text size="xs" c="dimmed" lineClamp={2}>{stat.label}</Text>
      <Text fw={650} size="lg" c={highlight ? 'brand.8' : undefined}>
        {stat.kind === 'p' && typeof stat.value === 'number' && stat.value >= 0.001 ? 'p = ' : stat.kind === 'p' ? 'p ' : ''}
        {formatStat(stat.value, stat.kind, stat.digits)}
      </Text>
    </Paper>
  );
}

export function ResultTableView({ table }: { table: ResultTable }) {
  return (
    <div>
      <Text fw={600} mb="xs">{table.title}</Text>
      <Paper withBorder style={{ overflowX: 'auto' }}>
        <Table fz="sm" striped highlightOnHover withColumnBorders verticalSpacing={6}>
          <Table.Thead>
            <Table.Tr>
              {table.columns.map((c, i) => (
                <Table.Th key={i} style={{ whiteSpace: 'nowrap' }} ta={i === 0 ? 'left' : 'right'}>{c}</Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {table.rows.map((row, i) => (
              <Table.Tr key={i}>
                {row.map((cell, j) => (
                  <Table.Td key={j} ta={table.kinds[j] === 'text' || j === 0 ? 'left' : 'right'}
                    style={{ whiteSpace: 'nowrap', fontVariantNumeric: 'tabular-nums' }}>
                    {formatCellOf(cell, table.kinds[j])}
                  </Table.Td>
                ))}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
      {table.note && <Text size="xs" c="dimmed" mt={4}>{table.note}</Text>}
    </div>
  );
}

export function Line({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Group gap="sm" align="flex-start" wrap="nowrap">
      <Text size="sm" c="dimmed" w={230} style={{ flexShrink: 0 }}>{label}</Text>
      <Box style={{ minWidth: 0, fontSize: 'var(--mantine-font-size-sm)', overflowWrap: 'anywhere' }}>{value}</Box>
    </Group>
  );
}

function ReproductionAlert({ report, onClose }: { report: ReproductionReport; onClose: () => void }) {
  const ok = report.identical_results;
  return (
    <Alert withCloseButton onClose={onClose} color={ok ? 'teal' : 'orange'} variant="light"
      icon={ok ? <IconCheck size={18} /> : <IconAlertTriangle size={18} />}
      title={ok ? 'Analyse reproduite : résultats identiques' : 'Les résultats recalculés diffèrent'}>
      <Stack gap={4}>
        <Text size="sm">{report.status_label}.</Text>
        {report.error && <Text size="sm">Recalcul impossible : {report.error}</Text>}
        {!ok && report.differences.length > 0 && (
          <Text size="sm">
            {report.differences.length} valeur(s) différente(s), par exemple :{' '}
            {report.differences.slice(0, 4).map((d) => `${d.path} (${String(d.stored)} → ${String(d.recomputed)})`).join(' ; ')}.
            Pour conserver un résultat sur les données actuelles, utilisez « Dupliquer ».
          </Text>
        )}
        {report.same_environment === false && (
          <Text size="xs" c="dimmed">L'environnement de calcul (versions des bibliothèques) a changé depuis le calcul initial.</Text>
        )}
        <Text size="xs" c="dimmed">Vérifié le {formatDateTime(report.checked_at)}.</Text>
      </Stack>
    </Alert>
  );
}
