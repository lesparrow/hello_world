import type { ReactNode } from 'react';
import { Autocomplete, Container, Group, NumberInput, Paper, SimpleGrid, Stack, Text, Textarea, TextInput, Title } from '@mantine/core';
import { AiMarkBadge, AiMarksBanner, CopilotButton, useAiMarks } from '../components/ai/Copilot';
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
  const ai = useAiMarks('study.');
  const L = (text: string, field: keyof Study) => (
    <Group gap={6} component="span" style={{ display: 'inline-flex' }}>
      {text}
      <AiMarkBadge mark={ai.find(`study.${field}`)} onValidate={(t) => void ai.validate(t)} />
    </Group>
  );
  const empty = !draft.problem_statement.trim() && !draft.objectives.trim() && draft.hypotheses.length === 0;

  return (
    <Container size={820} py="xl">
      <Stack gap="lg">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <div>
            <Title order={2}>Votre étude</Title>
            <Text c="dimmed">Ces informations structureront votre plan d'analyse et votre rapport.</Text>
          </div>
          <Group gap="xs" wrap="nowrap">
            <CopilotButton action="study" input="subject" params={{ mode: 'remplir' }}
              label={empty ? "Remplir avec l'IA" : "Compléter avec l'IA"} variant={empty ? 'filled' : 'light'} />
            {!empty && (
              <CopilotButton action="study" input="none" params={{ mode: 'ameliorer' }} label="Améliorer la rédaction" variant="default" />
            )}
          </Group>
        </Group>
        <AiMarksBanner marks={ai.marks} onValidate={(t) => void ai.validate(t)} />

        <Section title="Identité et problématique">
          <Stack>
            <TextInput label={L("Titre de l'étude", 'title')} required maxLength={300} value={draft.title}
              onChange={(e) => set('title', e.currentTarget.value)} onBlur={onCommit}
              error={!draft.title.trim() ? 'Le titre est obligatoire.' : undefined} />
            <Textarea label={L('Problématique', 'problem_statement')} value={draft.problem_statement} minRows={3}
              placeholder="La question principale de votre recherche."
              onChange={(e) => set('problem_statement', e.currentTarget.value)} onBlur={onCommit} />
            <Textarea label={L('Objectifs', 'objectives')} value={draft.objectives} minRows={3}
              onChange={(e) => set('objectives', e.currentTarget.value)} onBlur={onCommit} />
          </Stack>
        </Section>

        <Section title="Hypothèses" hint="Formulez des hypothèses testables. Elles seront reliées à vos analyses.">
          <Group mb="xs"><AiMarkBadge mark={ai.find('study.hypotheses')} onValidate={(t) => void ai.validate(t)} /></Group>
          <HypothesesEditor value={draft.hypotheses} onChange={(v) => set('hypotheses', v)} onBlur={onCommit} />
        </Section>

        <Section title="Population et échantillonnage">
          <Stack>
            <Textarea label={L('Population étudiée', 'population')} value={draft.population} minRows={2}
              placeholder="Ex. : Étudiants de première année, faculté des sciences, année 2025-2026"
              onChange={(e) => set('population', e.currentTarget.value)} onBlur={onCommit} />
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <Autocomplete label={L("Méthode d'échantillonnage", 'sampling_method')} data={SAMPLING_SUGGESTIONS}
                value={draft.sampling_method} placeholder="Choisir ou saisir"
                onChange={(v) => set('sampling_method', v)} onBlur={onCommit}
                onOptionSubmit={() => setTimeout(onCommit, 0)} />
              <NumberInput label={L("Taille d'échantillon prévue", 'planned_sample_size')} min={1} allowDecimal={false}
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
