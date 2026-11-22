import { open, save } from '@tauri-apps/plugin-dialog';
import { runningInTauri } from '../engine/client';
import { withProjectExtension } from './format';

const filters = [{ name: 'Projet STATPFE', extensions: ['statpfe'] }];

/**
 * Hors de Tauri (développement dans un navigateur), il n'existe pas de boîte de
 * dialogue native : l'application fournit une saisie de chemin à la place.
 */
type PathPrompt = (opts: { title: string; defaultPath?: string }) => Promise<string | null>;
let browserPrompt: PathPrompt | null = null;
export function registerBrowserPathPrompt(prompt: PathPrompt) {
  browserPrompt = prompt;
}

export async function pickProjectToOpen(): Promise<string | null> {
  if (runningInTauri()) {
    const picked = await open({ multiple: false, directory: false, filters, title: 'Ouvrir un projet' });
    return typeof picked === 'string' ? picked : null;
  }
  return browserPrompt ? browserPrompt({ title: 'Chemin du projet à ouvrir' }) : null;
}

export async function pickProjectDestination(suggestedName: string): Promise<string | null> {
  const picked = runningInTauri()
    ? await save({ filters, defaultPath: suggestedName, title: 'Enregistrer le projet' })
    : browserPrompt
      ? await browserPrompt({ title: 'Chemin complet du nouveau projet', defaultPath: `/tmp/${suggestedName}` })
      : null;
  return picked ? withProjectExtension(picked) : null;
}

const dataFilters = [
  { name: 'Données (CSV, Excel)', extensions: ['csv', 'txt', 'tsv', 'xlsx', 'xlsm'] },
];

export async function pickDataFile(): Promise<string | null> {
  if (runningInTauri()) {
    const picked = await open({ multiple: false, directory: false, filters: dataFilters, title: 'Importer des données' });
    return typeof picked === 'string' ? picked : null;
  }
  return browserPrompt ? browserPrompt({ title: 'Chemin du fichier de données à importer' }) : null;
}

/** Emplacement d'un rapport exporté (Word ou PDF). */
export async function pickReportDestination(suggestedName: string, format: 'docx' | 'pdf'): Promise<string | null> {
  const filters = [format === 'docx' ? { name: 'Document Word', extensions: ['docx'] } : { name: 'PDF', extensions: ['pdf'] }];
  const picked = runningInTauri()
    ? await save({ filters, defaultPath: suggestedName, title: 'Exporter le rapport' })
    : browserPrompt
      ? await browserPrompt({ title: 'Chemin complet du rapport à exporter', defaultPath: `/tmp/${suggestedName}` })
      : null;
  if (!picked) return null;
  return picked.toLowerCase().endsWith(`.${format}`) ? picked : `${picked}.${format}`;
}
