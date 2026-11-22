import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Center, Loader, Stack, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconAlertTriangle } from '@tabler/icons-react';
import { call, errorMessage } from './engine/client';
import type { EngineInfo, ProjectState } from './engine/types';
import { Home } from './screens/Home';
import { Workspace } from './screens/Workspace';
import { BrowserPathPrompt } from './components/BrowserPathPrompt';

export function notifyError(err: unknown, title = 'Action impossible') {
  notifications.show({ color: 'red', title, message: errorMessage(err), autoClose: 8000 });
}

export function App() {
  const [engine, setEngine] = useState<EngineInfo | null>(null);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [project, setProject] = useState<ProjectState | null>(null);

  const connect = useCallback(async () => {
    setEngineError(null);
    try {
      setEngine(await call('engine.info'));
      // Si l'interface est rechargée alors qu'un projet est ouvert, on le retrouve.
      setProject(await call('project.current'));
    } catch (err) {
      setEngineError(errorMessage(err));
    }
  }, []);

  useEffect(() => {
    void connect();
  }, [connect]);

  let content;
  if (engineError) {
    content = (
      <Center h="100%" p="xl">
        <Stack maw={520}>
          <Alert color="red" icon={<IconAlertTriangle />} title="Le moteur de calcul ne répond pas">
            <Text size="sm">{engineError}</Text>
            <Text size="sm" mt="xs">
              Vos fichiers de projet ne sont pas concernés. Réessayez, puis redémarrez
              l'application si le problème persiste.
            </Text>
          </Alert>
          <Button onClick={connect}>Réessayer</Button>
        </Stack>
      </Center>
    );
  } else if (!engine) {
    content = (
      <Center h="100%">
        <Stack align="center" gap="xs">
          <Loader />
          <Text c="dimmed" size="sm">Démarrage du moteur de calcul…</Text>
        </Stack>
      </Center>
    );
  } else if (project) {
    content = <Workspace project={project} onChange={setProject} onClosed={() => setProject(null)} />;
  } else {
    content = <Home engine={engine} onOpened={setProject} />;
  }

  return (
    <>
      <BrowserPathPrompt />
      {content}
    </>
  );
}
