import { useEffect, useState } from 'react';
import { Group, Loader, Pagination, ScrollArea, Switch, Table, Text, Tooltip } from '@mantine/core';
import { IconEyeOff } from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { PreviewPage } from '../../engine/types';
import { formatCell, formatInt } from '../../lib/numbers';
import { notifyError } from '../../App';

const PAGE = 100;

interface Props {
  datasetId: number;
  versionId: number | null;
  /** Change quand les données sous-jacentes changent, pour recharger l'aperçu. */
  revision: string;
}

export function DataTable({ datasetId, versionId, revision }: Props) {
  const [page, setPage] = useState(1);
  const [reveal, setReveal] = useState(false);
  const [data, setData] = useState<PreviewPage | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => setPage(1), [datasetId, versionId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    call('data.preview', {
      dataset_id: datasetId, version_id: versionId, offset: (page - 1) * PAGE, limit: PAGE,
      reveal_identifiers: reveal,
    })
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && notifyError(err, "Impossible d'afficher les données"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [datasetId, versionId, page, reveal, revision]);

  if (!data) return <Loader size="sm" />;
  const pages = Math.max(1, Math.ceil(data.total / PAGE));
  const masked = data.columns.some((c) => c.masked) || reveal;

  return (
    <div>
      <Group justify="space-between" mb="xs">
        <Text size="sm" c="dimmed">
          {formatInt(data.total)} lignes · {data.columns.length} variables
          {loading && <Loader size={12} ml={8} />}
        </Text>
        {masked && (
          <Tooltip label="Les colonnes identifiantes ou personnelles sont masquées par défaut." withArrow>
            <Switch size="sm" label="Afficher les colonnes identifiantes" checked={reveal}
              onChange={(e) => setReveal(e.currentTarget.checked)} />
          </Tooltip>
        )}
      </Group>
      <ScrollArea h={460} type="auto" style={{ border: '1px solid var(--mantine-color-default-border)', borderRadius: 8 }}>
        <Table striped highlightOnHover withColumnBorders stickyHeader fz="sm" style={{ userSelect: 'text' }}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th w={56} c="dimmed">#</Table.Th>
              {data.columns.map((c) => (
                <Table.Th key={c.key} style={{ whiteSpace: 'nowrap' }}>
                  <Group gap={4} wrap="nowrap">
                    {c.masked && <IconEyeOff size={14} color="var(--mantine-color-orange-6)" />}
                    {c.name}
                  </Group>
                </Table.Th>
              ))}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.rows.map((row, i) => (
              <Table.Tr key={data.row_numbers[i]}>
                <Table.Td c="dimmed">{data.row_numbers[i]}</Table.Td>
                {row.map((v, j) => (
                  <Table.Td key={j} ta={typeof v === 'number' ? 'right' : undefined}
                    style={{ whiteSpace: 'nowrap', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {v === null ? <Text span size="xs" c="dimmed" fs="italic">manquant</Text> : formatCell(v)}
                  </Table.Td>
                ))}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </ScrollArea>
      {pages > 1 && <Pagination mt="sm" size="sm" total={pages} value={page} onChange={setPage} />}
    </div>
  );
}
