import { useState } from 'react';
import { Button, Group, Modal, Stack, Stepper, Text, Textarea, TextInput } from '@mantine/core';
import { IconCheck } from '@tabler/icons-react';
import { call, runningInTauri } from '../engine/client';
import type { ProjectState, Study } from '../engine/types';
import { HypothesesEditor } from '../components/HypothesesEditor';
import { pickProjectDestination } from '../lib/files';
import { suggestFileName } from '../lib/format';
import { notifyError } from '../App';

const empty: Study = {
  title: '',
  problem_statement: '',
  objectives: '',
  population: '',
  sampling_method: '',
  planned_sample_size: null,
  hypotheses: [],
};

interface Props {
  opened: boolean;
  onClose: () => void;
  onCreated: (p: ProjectState) => void;
}

export function NewProjectModal({ opened, onClose, onCreated }: Props) {
  const [step, setStep] = useState(0);
  const [study, setStudy] = useState<Study>(empty);
  const [busy, setBusy] = useState(false);
  const titleMissing = !study.title.trim();

  const set = <K extends keyof Study>(key: K, value: Study[K]) => setStudy((s) => ({ ...s, [key]: value }));

  const reset = () => {
    setStep(0);
    setStudy(empty);
  };

  const create = async () => {
    const path = await pickProjectDestination(suggestFileName(study.title));
    if (!path) return;
    setBusy(true);
    try {
      // La boîte de dialogue native a déjà demandé confirmation avant de remplacer un fichier.
      const project = await call('project.create', { path, study, overwrite: runningInTauri() });
      reset();
      onClose();
      onCreated(project);
    } catch (err) {
      notifyError(err, 'Impossible de créer le projet');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={650} fz="lg">Nouveau projet d'étude</Text>}
      size="lg" centered closeOnClickOutside={false}>
      <Stepper active={step} onStepClick={(s) => !titleMissing && setStep(s)} size="sm" mb="lg">
        <Stepper.Step label="L'étude" description="Titre et problématique">
          <Stack>
            <TextInput
              data-autofocus
              label="Titre de l'étude"
              placeholder="Ex. : Effet du tutorat sur la réussite en première année"
              required
              value={study.title}
              onChange={(e) => set('title', e.currentTarget.value)}
              maxLength={300}
            />
            <Textarea
              label="Problématique"
              description="La question principale à laquelle votre étude veut répondre."
              placeholder="Ex. : Le tutorat améliore-t-il les résultats des étudiants de L1 ?"
              value={study.problem_statement}
              onChange={(e) => set('problem_statement', e.currentTarget.value)}
            />
          </Stack>
        </Stepper.Step>
        <Stepper.Step label="Objectifs" description="Et hypothèses">
          <Stack>
            <Textarea
              label="Objectifs"
              placeholder="Ex. : Comparer les notes moyennes des étudiants tutorés et non tutorés."
              value={study.objectives}
              onChange={(e) => set('objectives', e.currentTarget.value)}
            />
            <div>
              <Text size="sm" fw={500} mb={6}>Hypothèses</Text>
              <HypothesesEditor value={study.hypotheses} onChange={(v) => set('hypotheses', v)} />
            </div>
            <Text size="xs" c="dimmed">
              Vous pourrez compléter ou modifier ces informations à tout moment.
            </Text>
          </Stack>
        </Stepper.Step>
      </Stepper>
      <Group justify="space-between">
        <Button variant="default" onClick={step === 0 ? onClose : () => setStep(0)}>
          {step === 0 ? 'Annuler' : 'Retour'}
        </Button>
        {step === 0 ? (
          <Button disabled={titleMissing} onClick={() => setStep(1)}>Continuer</Button>
        ) : (
          <Button leftSection={<IconCheck size={16} />} loading={busy} disabled={titleMissing} onClick={create}>
            Choisir l'emplacement et créer
          </Button>
        )}
      </Group>
    </Modal>
  );
}
