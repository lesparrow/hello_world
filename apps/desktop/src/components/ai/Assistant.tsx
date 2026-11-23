import { useState } from 'react';
import { Alert, Badge, Button, Drawer, Group, List, Stepper, Text } from '@mantine/core';
import { IconArrowRight, IconPlayerPlay, IconSparkles } from '@tabler/icons-react';
import { call } from '../../engine/client';
import type { PlanRunResult, ProjectState } from '../../engine/types';
import { CopilotButton, useCopilotEnv } from './Copilot';
import { notifyError } from '../../App';

interface Props {
  opened: boolean;
  onClose: () => void;
  project: ProjectState;
}

/**
 * Assistant complet : le parcours de l'étude, de la fiche au rapport exporté. À chaque étape, l'IA propose et le
 * moteur vérifie ; l'étudiant applique, relit et valide. Les étapes sans IA (import, verrouillage, export) restent
 * entre ses mains.
 */
export function AssistantDrawer({ opened, onClose, project }: Props) {
  const env = useCopilotEnv();
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<PlanRunResult | null>(null);
  if (!env) return null;

  const s = project.study;
  const hasStudy = !!s.problem_statement.trim() && s.hypotheses.length > 0;
  const hasData = project.datasets.length > 0;
  const plan = project.plan_status;
  const locked = plan?.locked_version != null;
  const steps = [
    hasStudy, hasData, !!plan, locked && project.analyses_count > 0, project.power_count > 0,
    project.analyses_count > 0, false,
  ];
  const active = steps.findIndex((x) => !x);
  const go = (screen: Parameters<typeof env.goTo>[0]) => { onClose(); env.goTo(screen); };

  const runAll = async () => {
    if (env.datasetId === null) return;
    setRunning(true);
    try {
      const r = await call('plan.run_all', { dataset_id: env.datasetId, version_id: env.versionId });
      setRun(r.run);
      env.onProjectChange(r.project);
    } catch (err) { notifyError(err, 'Lancement impossible'); }
    finally { setRunning(false); }
  };

  const open = (label: string, screen: Parameters<typeof env.goTo>[0]) => (
    <Button size="xs" variant="subtle" rightSection={<IconArrowRight size={14} />} onClick={() => go(screen)}>{label}</Button>
  );

  return (
    <Drawer opened={opened} onClose={onClose} position="right" size={560}
      title={<Group gap="xs"><IconSparkles size={18} /><Text fw={650}>Assistant complet</Text></Group>}>
      <Text size="sm" c="dimmed" mb="md">
        Suivez les étapes dans l'ordre. À chaque étape, l'IA vous fait une proposition que le moteur vérifie ; rien
        n'est modifié sans votre accord, et tout ce que vous appliquez reste marqué « proposé par l'IA » jusqu'à votre
        validation. L'import des données, le verrouillage du plan et l'export restent entre vos mains.
      </Text>
      <Stepper active={active < 0 ? steps.length : active} orientation="vertical" size="sm" allowNextStepsSelect={false}>
        <Stepper.Step label="1. L'étude" description={hasStudy ? 'Problématique et hypothèses renseignées' : 'Titre, problématique, objectifs, hypothèses'}>
        </Stepper.Step>
        <Stepper.Step label="2. Les données et les variables" description={hasData ? `${project.datasets.length} jeu(x) de données importé(s)` : 'Importez votre fichier Excel ou CSV'} />
        <Stepper.Step label="3. Le plan d'analyse et le choix des tests" description={plan ? `Version ${plan.version} (${plan.status === 'verrouille' ? 'verrouillée' : 'brouillon'})` : 'Une analyse par hypothèse'} />
        <Stepper.Step label="4. Verrouiller le plan et lancer les analyses" description={locked ? `${project.analyses_count} analyse(s) enregistrée(s)` : 'Le verrouillage se fait sur l\'écran Plan, avec un motif'} />
        <Stepper.Step label="5. La taille d'échantillon" description={project.power_count ? `${project.power_count} calcul(s) enregistré(s)` : 'Facultatif, mais attendu dans un mémoire'} />
        <Stepper.Step label="6. La rédaction" description="Discussion, limites, conclusion" />
        <Stepper.Step label="7. Les exports" description="Word, PDF, LaTeX, tableaux Excel, graphiques" />
      </Stepper>

      <Text fw={650} mt="lg" mb="xs">Actions</Text>
      <List spacing="sm" size="sm" listStyleType="none">
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">1</Badge>
            <CopilotButton action="study" input="subject" params={{ mode: 'remplir' }} size="xs"
              label={hasStudy ? "Compléter l'étude avec l'IA" : "Remplir l'étude avec l'IA"} />
            {open('Ouvrir', 'etude')}</Group>
        </List.Item>
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">2</Badge>
            {hasData ? (
              <CopilotButton action="variables" size="xs" label="Compléter et nettoyer les variables"
                params={env.datasetId !== null ? { dataset_id: env.datasetId, version_id: null } : undefined} />
            ) : <Button size="xs" variant="light" onClick={() => go('donnees')}>Importer les données</Button>}
            {hasData && open('Ouvrir', 'donnees')}</Group>
        </List.Item>
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">3</Badge>
            <CopilotButton action="plan" size="xs" label="Proposer le plan et les tests"
              disabled={!hasData || s.hypotheses.length === 0 || plan?.status === 'verrouille'}
              disabledReason={!hasData ? "Importez d'abord les données." : s.hypotheses.length === 0
                ? "Ajoutez d'abord des hypothèses (étape 1)." : 'Plan verrouillé : modifiez-le sur l\'écran Plan (nouvelle version).'} />
            {open('Ouvrir', 'plan')}</Group>
        </List.Item>
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">4</Badge>
            {locked ? (
              <Button size="xs" variant="light" color="teal" leftSection={<IconPlayerPlay size={14} />} loading={running}
                disabled={env.datasetId === null} onClick={() => void runAll()}>
                Lancer toutes les analyses prévues
              </Button>
            ) : <Button size="xs" variant="light" onClick={() => go('plan')}>Verrouiller le plan</Button>}
            {locked && open('Voir les analyses', 'analyses')}</Group>
          {run && (
            <Alert mt="xs" color={run.results.some((r) => r.status === 'erreur') ? 'orange' : 'teal'} variant="light" p="xs">
              <Text size="xs">
                {run.ran} analyse(s) calculée(s) par le moteur
                {run.results.filter((r) => r.status === 'deja_lancee').length
                  ? `, ${run.results.filter((r) => r.status === 'deja_lancee').length} déjà lancée(s)` : ''}
                {run.results.filter((r) => r.status === 'erreur').length
                  ? `, ${run.results.filter((r) => r.status === 'erreur').length} impossible(s) : ${run.results.filter((r) => r.status === 'erreur').map((r) => `${r.label} (${r.message})`).join(' ; ')}` : ''}.
              </Text>
            </Alert>
          )}
        </List.Item>
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">5</Badge>
            <CopilotButton action="power" input="note" size="xs" label="Proposer la taille d'échantillon" />
            {open('Ouvrir', 'puissance')}</Group>
        </List.Item>
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">6</Badge>
            <CopilotButton action="report" size="xs" label="Rédiger avec l'IA" disabled={project.analyses_count === 0}
              disabledReason="Lancez d'abord des analyses (étape 4)." />
            {project.analyses_count > 0 && open('Ouvrir', 'rapport')}</Group>
        </List.Item>
        <List.Item>
          <Group gap="xs"><Badge size="sm" variant="light">7</Badge>
            <Button size="xs" variant="light" disabled={project.analyses_count === 0} onClick={() => go('rapport')}>
              Exporter le rapport, les tableaux et les graphiques
            </Button></Group>
        </List.Item>
      </List>
      {(project.ai_marks ?? 0) > 0 && (
        <Alert mt="lg" color="yellow" variant="light" icon={<IconSparkles size={16} />}>
          <Text size="sm">
            {project.ai_marks} élément(s) proposé(s) par l'IA restent à valider. Le contrôle du rapport le signale
            tant qu'ils ne sont pas relus.
          </Text>
        </Alert>
      )}
    </Drawer>
  );
}
