const dateFormatter = new Intl.DateTimeFormat('fr-FR', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

/** Date ISO (UTC) vers un affichage local en français. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : dateFormatter.format(d);
}

/** Nom d'un fichier à partir d'un chemin Windows ou Unix. */
export function fileName(path: string): string {
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

/** Ajoute l'extension .statpfe si elle manque. */
export function withProjectExtension(path: string): string {
  return path.toLowerCase().endsWith('.statpfe') ? path : `${path}.statpfe`;
}

/** Propose un nom de fichier sûr à partir du titre de l'étude. */
export function suggestFileName(title: string): string {
  const base = title
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .toLowerCase()
    .slice(0, 60);
  return `${base || 'projet'}.statpfe`;
}

/** Taille en octets lisible en français (« 15,6 Go »). */
export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return 'inconnue';
  const units = ['octets', 'Ko', 'Mo', 'Go', 'To'];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  const digits = i >= 3 ? 1 : 0;
  return `${v.toLocaleString('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits })} ${units[i]}`;
}
