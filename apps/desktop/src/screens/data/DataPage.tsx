import { useState } from 'react';
import {
  Alert, Badge, Button, Center, Container, Group, Paper, Select, Stack, Tabs, Text, ThemeIcon, Title, Tooltip,
} from '@mantine/core';
import {
  IconAlertTriangle, IconDatabase, IconFileImport, IconFingerprint, IconListDetails, IconShieldCheck, IconTable,
} from '@tabler/icons-react';
import type { Dataset, ProjectState, Variable } from '../../engine/types';
import { call } from '../../engine/client';
import { pickDataFile } from '../../lib/files';
import { formatDateTime } from '../../lib/format';
import { formatInt } from '../../lib/numbers';
import { notifyError } from '../../App';
import { ImportModal } from './ImportModal';
import { DataTable } from './DataTable';
import { DictionaryPanel } from './DictionaryPanel';
import { QualityPanel } from './QualityPanel';

interface Props {
  project: ProjectState;
  dataset: Dataset | null;
  onSelectDataset: (id: number) => void;
  onImported: (id: number, project: ProjectState) => void;
  onResult: (r: { dataset: Dataset; project: ProjectState }) => void;
}

export function DataPage({ project, dataset, onSelectDataset, onImported, onResult }: Props) {
  const [importPath, setImportPath] = useState<string | null>(null);

  const startImport = async () => {
    const path = await pickDataFile();
    if (path) setImportPath(path);
  };

  const updateVariable = async (key: string, changes: Partial<Variable>): Promise<boolean> => {
    if (!dataset) return false;
    try {
      onResult(await call('data.update_variable', { dataset_id: dataset.id, key, changes }));
      return true;
    } catch (err) {
      notifyError(err, 'Modification refusée');
      return false;
    }
  };

  const modal = (
    <ImportModal path={importPath} onClose={() => setImportPath(null)}
      onImported={(id, p) => { setImportPath(null); onImported(id, p); }} />
  );

  if (project.datasets.length === 0) {
    return (
      <Container size={720} py={60}>
        <Center>
          <Stack align="center" gap="md" ta="center">
            <ThemeIcon size={72} radius="xl" variant="light"><IconDatabase size={38} /></ThemeIcon>
            <Title order={2}>Importez vos données</Title>
            <Text c="dimmed" maw={520}>
              Fichiers CSV (export Google Forms, LimeSurvey, Kobo…) ou Excel. Le fichier original est conservé
              tel quel dans le projet et n'est jamais modifié.
            </Text>
            <Button size="md" leftSection={<IconFileImport size={18} />} onClick={startImport}>
              Choisir un fichier
            </Button>
            <Text size="xs" c="dimmed">Formats acceptés : .csv, .txt, .tsv, .xlsx. SPSS (.sav) : prévu ultérieurement.</Text>
          </Stack>
        </Center>
        {modal}
      </Container>
    );
  }

  return (
    <Container size="xl" py="lg">
      <Stack>
        <Group justify="space-between">
          <Group>
            <Title order={2}>Données</Title>
            {project.datasets.length > 1 && (
              <Select size="sm" w={260} allowDeselect={false} value={dataset ? String(dataset.id) : null}
                data={project.datasets.map((d) => ({ value: String(d.id), label: d.name }))}
                onChange={(v) => v && onSelectDataset(Number(v))} />
            )}
          </Group>
          <Button variant="light" leftSection={<IconFileImport size={16} />} onClick={startImport}>
            Importer un autre fichier
          </Button>
        </Group>

        {dataset && (
          <>
            <Paper withBorder p="md">
              <Group justify="space-between" align="flex-start">
                <div>
                  <Text fw={650} fz="lg">{dataset.name}</Text>
                  <Text size="sm" c="dimmed">
                    Source : {dataset.source.file_name} · importé le {formatDateTime(dataset.source.imported_at)}
                    {dataset.source.read_options.encoding && ` · ${dataset.source.read_options.encoding}`}
                    {dataset.source.read_options.sheet && ` · feuille « ${dataset.source.read_options.sheet} »`}
                  </Text>
                </div>
                <Group gap="xs">
                  <Badge size="lg" variant="light">{formatInt(dataset.original.rows)} lignes</Badge>
                  <Badge size="lg" variant="light">{dataset.original.columns} variables</Badge>
                  <Tooltip multiline w={300} label={`Empreinte SHA-256 du fichier original : ${dataset.source.sha256}. Elle prouve que les données n'ont pas été modifiées.`}>
                    <Badge size="lg" variant="outline" color="teal" leftSection={<IconShieldCheck size={14} />}>
                      Original protégé
                    </Badge>
                  </Tooltip>
                </Group>
              </Group>
              {dataset.source.notes.map((n) => (
                <Alert key={n} mt="sm" color="orange" variant="light" icon={<IconAlertTriangle size={16} />}>{n}</Alert>
              ))}
            </Paper>

            <Tabs defaultValue="apercu" keepMounted={false}>
              <Tabs.List>
                <Tabs.Tab value="apercu" leftSection={<IconTable size={16} />}>Aperçu (original)</Tabs.Tab>
                <Tabs.Tab value="dictionnaire" leftSection={<IconListDetails size={16} />}>Dictionnaire des variables</Tabs.Tab>
                <Tabs.Tab value="qualite" leftSection={<IconFingerprint size={16} />}
                  rightSection={dataset.quality.issues.length ? <Badge size="xs" circle color="orange">{dataset.quality.issues.length}</Badge> : null}>
                  Qualité
                </Tabs.Tab>
              </Tabs.List>
              <Tabs.Panel value="apercu" pt="md">
                <DataTable datasetId={dataset.id} versionId={null}
                  revision={JSON.stringify(dataset.variables)} />
              </Tabs.Panel>
              <Tabs.Panel value="dictionnaire" pt="md">
                <DictionaryPanel dataset={dataset} onChange={updateVariable} />
              </Tabs.Panel>
              <Tabs.Panel value="qualite" pt="md">
                <QualityPanel report={dataset.quality} />
              </Tabs.Panel>
            </Tabs>
          </>
        )}
      </Stack>
      {modal}
    </Container>
  );
}
