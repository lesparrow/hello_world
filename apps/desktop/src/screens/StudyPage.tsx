import type { ReactNode } from 'react';
import { Autocomplete, Container, NumberInput, Paper, SimpleGrid, Stack, Text, Textarea, TextInput, Title } from '@mantine/core';
import type { Study } from '../engine/types';
import { HypothesesEditor } from '../components/HypothesesEditor';
import { SAMPLING_SUGGESTIONS } from '../components/studyFields';

interface Props {
  draft: Study;
  onDraft: (s: Study) => void;
  /** Appelé quand un champ perd le focus : les modifications sont transmises au moteur. */
  onCommit: () => void;
}

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <Paper withBorder p="lg">
      <Title order={4} mb={hint ? 2 : 'md'}>{title}</Title>
      {hint && <Text size="sm" c="dimmed" mb="md">{hint}</Text>}
      {children}
    </Paper>
  );
}

export function StudyPage({ draft, onDraft, onCommit }: Props) {
  const set = <K extends keyof Study>(key: K, value: Study[K]) => onDraft({ ...draft, [key]: value });

  return (
    <Container size={820} py="xl">
      <Stack gap="lg">
        <div>
          <Title order={2}>Votre étude</Title>
          <Text c="dimmed">Ces informations structureront votre plan d'analyse et votre rapport.</Text>
        </div>

        <Section title="Identité et problématique">
          <Stack>
            <TextInput label="Titre de l'étude" required maxLength={300} value={draft.title}
              onChange={(e) => set('title', e.currentTarget.value)} onBlur={onCommit}
              error={!draft.title.trim() ? 'Le titre est obligatoire.' : undefined} />
            <Textarea label="Problématique" value={draft.problem_statement} minRows={3}
              placeholder="La question principale de votre recherche."
              onChange={(e) => set('problem_statement', e.currentTarget.value)} onBlur={onCommit} />
            <Textarea label="Objectifs" value={draft.objectives} minRows={3}
              onChange={(e) => set('objectives', e.currentTarget.value)} onBlur={onCommit} />
          </Stack>
        </Section>

        <Section title="Hypothèses" hint="Formulez des hypothèses testables. Elles seront reliées à vos analyses.">
          <HypothesesEditor value={draft.hypotheses} onChange={(v) => set('hypotheses', v)} onBlur={onCommit} />
        </Section>

        <Section title="Population et échantillonnage">
          <Stack>
            <Textarea label="Population étudiée" value={draft.population} minRows={2}
              placeholder="Ex. : Étudiants de première année, faculté des sciences, année 2025-2026"
              onChange={(e) => set('population', e.currentTarget.value)} onBlur={onCommit} />
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <Autocomplete label="Méthode d'échantillonnage" data={SAMPLING_SUGGESTIONS}
                value={draft.sampling_method} placeholder="Choisir ou saisir"
                onChange={(v) => set('sampling_method', v)} onBlur={onCommit}
                onOptionSubmit={() => setTimeout(onCommit, 0)} />
              <NumberInput label="Taille d'échantillon prévue" min={1} allowDecimal={false}
                allowNegative={false} thousandSeparator=" " value={draft.planned_sample_size ?? ''}
                onChange={(v) => set('planned_sample_size', typeof v === 'number' ? v : null)}
                onBlur={onCommit} />
            </SimpleGrid>
          </Stack>
        </Section>
      </Stack>
    </Container>
  );
}
