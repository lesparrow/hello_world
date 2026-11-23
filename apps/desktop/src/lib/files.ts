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

const EXPORT_FILTERS: Record<string, { name: string; extensions: string[] }> = {
  docx: { name: 'Document Word', extensions: ['docx'] },
  pdf: { name: 'PDF', extensions: ['pdf'] },
  zip: { name: 'Archive LaTeX (Overleaf)', extensions: ['zip'] },
  xlsx: { name: 'Classeur Excel', extensions: ['xlsx'] },
  png: { name: 'Image PNG', extensions: ['png'] },
  svg: { name: 'Image SVG (vectorielle)', extensions: ['svg'] },
};

/** Extension du fichier produit pour un format de rapport. */
export function reportExtension(format: 'docx' | 'pdf' | 'latex'): string {
  return format === 'latex' ? 'zip' : format;
}

/** Emplacement d'un fichier exporté (rapport, tableaux, image), avec l'extension imposée. */
export async function pickExportDestination(suggestedName: string, extension: string, title = 'Exporter'): Promise<string | null> {
  const filters = [EXPORT_FILTERS[extension] ?? { name: extension.toUpperCase(), extensions: [extension] }];
  const picked = runningInTauri()
    ? await save({ filters, defaultPath: suggestedName, title })
    : browserPrompt
      ? await browserPrompt({ title: `${title} : chemin complet`, defaultPath: `/tmp/${suggestedName}` })
      : null;
  if (!picked) return null;
  return picked.toLowerCase().endsWith(`.${extension}`) ? picked : `${picked}.${extension}`;
}

/** Emplacement d'un rapport exporté (Word, PDF ou archive LaTeX). */
export async function pickReportDestination(suggestedName: string, format: 'docx' | 'pdf' | 'latex'): Promise<string | null> {
  return pickExportDestination(suggestedName, reportExtension(format), 'Exporter le rapport');
}

/** Dossier où enregistrer plusieurs fichiers (graphiques). */
export async function pickExportDirectory(title = 'Choisir le dossier des graphiques'): Promise<string | null> {
  if (runningInTauri()) {
    const picked = await open({ directory: true, multiple: false, title });
    return typeof picked === 'string' ? picked : null;
  }
  return browserPrompt ? browserPrompt({ title: `${title} : chemin complet`, defaultPath: '/tmp' }) : null;
}
