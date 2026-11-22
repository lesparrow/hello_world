import { useCallback, useEffect, useState, type ReactNode } from 'react';
import {
  ActionIcon, Badge, Box, Card, Container, Group, Paper, SimpleGrid, Stack, Text, ThemeIcon,
  Title, Tooltip, UnstyledButton,
} from '@mantine/core';
import {
  IconFilePlus, IconFolderOpen, IconLock, IconFileDescription, IconX, IconClock,
} from '@tabler/icons-react';
import { call } from '../engine/client';
import type { EngineInfo, ProjectState, RecentProject } from '../engine/types';
import { Logo } from '../components/Logo';
import { NewProjectModal } from './NewProjectModal';
import { pickProjectToOpen } from '../lib/files';
import { fileName, formatDateTime } from '../lib/format';
import { notifyError } from '../App';

interface Props {
  engine: EngineInfo;
  onOpened: (p: ProjectState) => void;
}

export function Home({ engine, onOpened }: Props) {
  const [recent, setRecent] = useState<RecentProject[]>([]);
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setRecent(await call('app.recent_projects'));
    } catch (err) {
      notifyError(err);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openPath = async (path: string) => {
    try {
      onOpened(await call('project.open', { path }));
    } catch (err) {
      notifyError(err, "Impossible d'ouvrir le projet");
      void refresh();
    }
  };

  const openDialog = async () => {
    const path = await pickProjectToOpen();
    if (path) await openPath(path);
  };

  const forget = async (path: string) => {
    try {
      await call('app.forget_recent', { path });
      await refresh();
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <Box mih="100%" className="hero-gradient">
      <Container size={880} py={56}>
        <Stack gap={40}>
          <Stack gap="md">
            <Logo size="lg" />
            <Title order={1} fz={34} lh={1.2} maw={640}>
              De la question de recherche au rapport académique.
            </Title>
            <Text c="dimmed" fz="lg" maw={620}>
              Des calculs fiables, une méthode expliquée et une traçabilité complète pour
              votre PFE, votre mémoire ou votre thèse.
            </Text>
          </Stack>

          <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="lg">
            <ActionCard
              icon={<IconFilePlus size={26} />}
              color="brand"
              title="Nouveau projet"
              text="Décrivez votre étude : titre, problématique, objectifs et hypothèses."
              onClick={() => setCreating(true)}
            />
            <ActionCard
              icon={<IconFolderOpen size={26} />}
              color="teal"
              title="Ouvrir un projet"
              text="Reprenez une étude enregistrée dans un fichier .statpfe."
              onClick={openDialog}
            />
          </SimpleGrid>

          <Stack gap="sm">
            <Group gap={8}>
              <IconClock size={18} color="var(--mantine-color-dimmed)" />
              <Text fw={600}>Projets récents</Text>
            </Group>
            {recent.length === 0 ? (
              <Paper withBorder p="lg">
                <Text c="dimmed" size="sm">
                  Aucun projet récent. Créez votre premier projet pour commencer.
                </Text>
              </Paper>
            ) : (
              <Paper withBorder>
                {recent.map((r, i) => (
                  <Group
                    key={r.path}
                    justify="space-between"
                    wrap="nowrap"
                    px="md"
                    py="sm"
                    style={{ borderTop: i ? '1px solid var(--mantine-color-default-border)' : undefined }}
                  >
                    <UnstyledButton
                      style={{ flex: 1, minWidth: 0 }}
                      disabled={!r.exists}
                      onClick={() => openPath(r.path)}
                    >
                      <Group wrap="nowrap" gap="sm">
                        <ThemeIcon variant="light" color={r.exists ? 'brand' : 'gray'} size={36}>
                          <IconFileDescription size={20} />
                        </ThemeIcon>
                        <Box style={{ minWidth: 0 }}>
                          <Group gap={6}>
                            <Text fw={550} truncate c={r.exists ? undefined : 'dimmed'}>
                              {r.title || fileName(r.path)}
                            </Text>
                            {!r.exists && <Badge size="xs" color="gray" variant="light">Introuvable</Badge>}
                          </Group>
                          <Text size="xs" c="dimmed" truncate>
                            {r.path} · {formatDateTime(r.opened_at)}
                          </Text>
                        </Box>
                      </Group>
                    </UnstyledButton>
                    <Tooltip label="Retirer de la liste (le fichier n'est pas supprimé)">
                      <ActionIcon variant="subtle" color="gray" onClick={() => forget(r.path)} aria-label="Retirer">
                        <IconX size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                ))}
              </Paper>
            )}
          </Stack>

          <Group gap={8} c="dimmed">
            <IconLock size={15} />
            <Text size="xs">
              Vos données restent sur votre ordinateur. Moteur {engine.version} · format de projet v
              {engine.project_format_version}
            </Text>
          </Group>
        </Stack>
      </Container>
      <NewProjectModal opened={creating} onClose={() => setCreating(false)} onCreated={onOpened} />
    </Box>
  );
}

function ActionCard(props: {
  icon: ReactNode;
  color: string;
  title: string;
  text: string;
  onClick: () => void;
}) {
  return (
    <Card withBorder padding="xl" className="action-card" component="button" onClick={props.onClick}
      style={{ textAlign: 'left', cursor: 'pointer', background: 'var(--mantine-color-body)' }}>
      <Stack gap="sm">
        <ThemeIcon size={48} radius="md" variant="light" color={props.color}>
          {props.icon}
        </ThemeIcon>
        <Text fw={650} fz="lg">{props.title}</Text>
        <Text size="sm" c="dimmed">{props.text}</Text>
      </Stack>
    </Card>
  );
}
