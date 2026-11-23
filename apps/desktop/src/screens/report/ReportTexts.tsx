import { useEffect, useState } from 'react';
import { Badge, Group, Paper, Stack, Text, Textarea } from '@mantine/core';
import { call } from '../../engine/client';
import type { ProjectState, ReportText } from '../../engine/types';
import { AiMarkBadge, CopilotButton, useAiMarks, useCopilotEnv } from '../../components/ai/Copilot';
import { notifyError } from '../../App';

interface Props {
  analyses: number[];
  onChange: (p: ProjectState) => void;
  /** Relance les contrôles du rapport après une modification. */
  onSaved: () => void;
}

const HINTS: Record<string, string> = {
  discussion: 'Confrontez chaque résultat à son hypothèse ; distinguez significativité et importance pratique.',
  limites: 'Ajoutées après les limites repérées automatiquement (effectifs, avertissements, valeurs manquantes).',
  conclusion: 'Une conclusion prudente qui répond à la problématique.',
};

/** Discussion, limites et conclusion : rédigées par l'étudiant ou proposées par l'IA puis relues. */
export function ReportTexts({ analyses, onChange, onSaved }: Props) {
  const env = useCopilotEnv();
  const ai = useAiMarks('report.');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [texts, setTexts] = useState<Record<string, ReportText>>({});
  const [draft, setDraft] = useState<Record<string, string>>({});

  useEffect(() => {
    call('report.texts', {}).then((r) => {
      setFields(r.fields);
      setTexts(r.texts);
      setDraft(Object.fromEntries(Object.keys(r.fields).map((k) => [k, r.texts[k]?.text ?? ''])));
    }).catch((err) => notifyError(err, 'Textes du rapport indisponibles'));
  }, [env?.marksVersion]);

  const save = async (key: string) => {
    const value = draft[key] ?? '';
    if (value.trim() === (texts[key]?.text ?? '')) return;
    try {
      const r = await call('report.save_texts', { texts: { [key]: value.trim() ? value : null } });
      setTexts(r.texts);
      onChange(r.project);
      void ai.reload();
      onSaved();
    } catch (err) { notifyError(err, 'Texte refusé'); }
  };

  return (
    <Paper withBorder p="md">
      <Group justify="space-between" mb="xs" wrap="nowrap">
        <div>
          <Text fw={650}>Rédaction : discussion, limites, conclusion</Text>
          <Text size="xs" c="dimmed">
            Laissées vides, ces sections gardent un texte d'attente à compléter dans le document exporté.
          </Text>
        </div>
        <CopilotButton action="report" label="Rédiger avec l'IA" params={{ analyses }}
          disabled={analyses.length === 0} disabledReason="Incluez au moins une analyse dans le rapport." />
      </Group>
      <Stack gap="sm">
        {Object.entries(fields).map(([key, label]) => {
          const t = texts[key];
          return (
            <Textarea key={key} autosize minRows={3} maxRows={14} maxLength={20000} value={draft[key] ?? ''}
              description={HINTS[key]}
              label={(
                <Group gap={6} component="span" style={{ display: 'inline-flex' }}>
                  {label}
                  {t?.origin === 'ia' && !ai.find(`report.${key}`) && (
                    <Badge size="xs" variant="light" color="gray">
                      {t.edited ? "proposé par l'IA, modifié et relu" : "proposé par l'IA, relu"}
                    </Badge>
                  )}
                  <AiMarkBadge mark={ai.find(`report.${key}`)} onValidate={async (targets) => { await ai.validate(targets); onSaved(); }} />
                </Group>
              )}
              onChange={(e) => { const v = e.currentTarget.value; setDraft((d) => ({ ...d, [key]: v })); }}
              onBlur={() => void save(key)} />
          );
        })}
      </Stack>
    </Paper>
  );
}
