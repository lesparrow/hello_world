import { useEffect, useRef, useState } from 'react';
import { Button, Group, Modal, Text, TextInput } from '@mantine/core';
import { registerBrowserPathPrompt } from '../lib/files';

/** Saisie de chemin utilisée seulement en développement dans un navigateur. */
export function BrowserPathPrompt() {
  const [state, setState] = useState<{ title: string; value: string } | null>(null);
  const resolver = useRef<((v: string | null) => void) | null>(null);

  useEffect(() => {
    registerBrowserPathPrompt(
      ({ title, defaultPath }) =>
        new Promise((resolve) => {
          resolver.current = resolve;
          setState({ title, value: defaultPath ?? '' });
        }),
    );
  }, []);

  const finish = (value: string | null) => {
    resolver.current?.(value);
    resolver.current = null;
    setState(null);
  };

  return (
    <Modal opened={state !== null} onClose={() => finish(null)} title={state?.title} centered zIndex={400}>
      <Text size="sm" c="dimmed" mb="sm">
        Mode développement : la boîte de dialogue native n'est disponible que dans l'application.
      </Text>
      <TextInput
        data-autofocus
        value={state?.value ?? ''}
        onChange={(e) => { const value = e.currentTarget.value; setState((s) => (s ? { ...s, value } : s)); }}
        onKeyDown={(e) => e.key === 'Enter' && state?.value && finish(state.value)}
      />
      <Group justify="flex-end" mt="md">
        <Button variant="default" onClick={() => finish(null)}>Annuler</Button>
        <Button disabled={!state?.value} onClick={() => finish(state!.value)}>Valider</Button>
      </Group>
    </Modal>
  );
}
