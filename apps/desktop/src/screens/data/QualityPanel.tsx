import { Alert, Badge, Group, Paper, Progress, SimpleGrid, Stack, Table, Text, ThemeIcon } from '@mantine/core';
import { IconAlertCircle, IconAlertTriangle, IconBulb, IconInfoCircle, IconBan } from '@tabler/icons-react';
import type { QualityIssue, QualityReport } from '../../engine/types';
import { formatInt, formatPercent } from '../../lib/numbers';

const LEVEL = {
  bloquant: { color: 'red', label: 'Erreur bloquante', icon: IconBan },
  important: { color: 'orange', label: 'Avertissement important', icon: IconAlertTriangle },
  methodologique: { color: 'yellow', label: 'Avertissement méthodologique', icon: IconAlertCircle },
  suggestion: { color: 'brand', label: 'Suggestion', icon: IconBulb },
  information: { color: 'gray', label: 'Information', icon: IconInfoCircle },
} as const;

export function QualityPanel({ report }: { report: QualityReport }) {
  return (
    <Stack>
      <SimpleGrid cols={{ base: 2, md: 4 }}>
        <Stat label="Lignes" value={formatInt(report.rows)} />
        <Stat label="Variables" value={formatInt(report.columns)} />
        <Stat label="Lignes complètes" value={formatInt(report.complete_rows)}
          hint={report.rows ? formatPercent(report.complete_rows / report.rows) : undefined} />
        <Stat label="Doublons exacts" value={formatInt(report.duplicates)} warn={report.duplicates > 0} />
      </SimpleGrid>

      <div>
        <Text fw={600} mb="xs">Points à vérifier ({report.issues.length})</Text>
        {report.issues.length === 0 ? (
          <Alert color="teal" variant="light">Aucun problème détecté.</Alert>
        ) : (
          <Stack gap="xs">{report.issues.map((issue, i) => <IssueRow key={i} issue={issue} />)}</Stack>
        )}
      </div>

      <div>
        <Text fw={600} mb="xs">Valeurs manquantes par variable</Text>
        <Paper withBorder p="sm">
          <Table fz="sm" verticalSpacing={4}>
            <Table.Tbody>
              {report.variables.map((v) => (
                <Table.Tr key={v.key}>
                  <Table.Td w={220}><Text size="sm" truncate>{v.name}</Text></Table.Td>
                  <Table.Td>
                    <Progress value={v.missing_rate * 100} color={v.missing_rate >= 0.2 ? 'orange' : 'brand'} size="md" />
                  </Table.Td>
                  <Table.Td w={150} ta="right">
                    <Text size="xs" c="dimmed">{formatInt(v.missing)} ({formatPercent(v.missing_rate)})</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      </div>
    </Stack>
  );
}

function IssueRow({ issue }: { issue: QualityIssue }) {
  const meta = LEVEL[issue.level];
  return (
    <Paper withBorder p="sm">
      <Group align="flex-start" wrap="nowrap" gap="sm">
        <ThemeIcon variant="light" color={meta.color} size={28}><meta.icon size={16} /></ThemeIcon>
        <div>
          <Group gap={6}>
            <Badge size="xs" color={meta.color} variant="light">{meta.label}</Badge>
            {issue.variable_name && <Text size="sm" fw={600}>{issue.variable_name}</Text>}
          </Group>
          <Text size="sm" mt={4}>{issue.message}</Text>
        </div>
      </Group>
    </Paper>
  );
}

function Stat({ label, value, hint, warn }: { label: string; value: string; hint?: string; warn?: boolean }) {
  return (
    <Paper withBorder p="md">
      <Text size="xs" c="dimmed" tt="uppercase" fw={600}>{label}</Text>
      <Group gap={6} align="baseline">
        <Text fz={26} fw={700} c={warn ? 'orange.7' : undefined}>{value}</Text>
        {hint && <Text size="sm" c="dimmed">{hint}</Text>}
      </Group>
    </Paper>
  );
}
