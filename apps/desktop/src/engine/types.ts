// Types des échanges avec le moteur Python (engine/statpfe/rpc/server.py).

export interface Study {
  title: string;
  problem_statement: string;
  objectives: string;
  population: string;
  sampling_method: string;
  planned_sample_size: number | null;
  hypotheses: string[];
}

export interface JournalEntry {
  id: number;
  at: string;
  action: string;
  summary: string;
}

export interface ProjectState {
  path: string;
  file_name: string;
  project_id: string;
  format_version: number;
  created_at: string;
  created_with: string;
  dirty: boolean;
  study: Study;
  journal: JournalEntry[];
  datasets: DatasetSummary[];
  analyses_count: number;
}

export interface DatasetSummary {
  id: number;
  name: string;
  source_file: string;
  imported_at: string;
}

export interface ReadOptions {
  encoding: string | null;
  delimiter: string | null;
  sheet: string | null;
  header: boolean;
}

export interface InspectResult {
  file_name: string;
  size: number;
  kind: 'csv' | 'excel';
  sheets: string[];
  options: ReadOptions;
  rows: number;
  columns: { key: string; type: string; type_label: string; potential_identifier: boolean }[];
  preview: (string | null)[][];
  notes: string[];
}

export type VarType = 'numerique' | 'texte' | 'booleen' | 'date';
export type VarLevel = 'nominal' | 'ordinal' | 'continu';
export type VarRole = 'non_defini' | 'a_expliquer' | 'explicative' | 'identifiant' | 'exclue';

export interface Category { value: string; label: string }

export interface Variable {
  key: string;
  name: string;
  type: VarType;
  level: VarLevel;
  role: VarRole;
  label: string;
  unit: string;
  missing_codes: string[];
  categories: Category[];
  potential_identifier: boolean;
  identifier_reasons: string[];
  detected_type: string;
  computed: boolean;
  type_label: string;
  level_label: string;
  role_label: string;
}

export interface QualityIssue {
  level: 'bloquant' | 'important' | 'methodologique' | 'suggestion' | 'information';
  variable: string | null;
  variable_name: string | null;
  message: string;
}

export interface QualityReport {
  rows: number;
  columns: number;
  duplicates: number;
  complete_rows: number;
  variables: {
    key: string; name: string; missing: number; missing_rate: number; distinct: number;
    invalid: number; invalid_examples: string[]; declared_missing: number; constant: boolean;
  }[];
  issues: QualityIssue[];
}

export type Step = Record<string, unknown> & { op: string };

export interface VersionStep {
  index: number;
  op: string;
  step: Step;
  description: string;
  rows_before: number;
  rows_after: number | null;
  warnings: string[];
  error?: string;
}

export interface DataVersion {
  id: number;
  name: string;
  created_at: string;
  steps: VersionStep[];
  error: string | null;
  rows: number | null;
  columns: number | null;
  fingerprint: string | null;
  variables: Variable[];
}

export interface Dataset {
  id: number;
  name: string;
  source: {
    file_name: string; sha256: string; kind: string; read_options: ReadOptions;
    imported_at: string; notes: string[];
  };
  original: { rows: number; columns: number; fingerprint: string };
  variables: Variable[];
  quality: QualityReport;
  versions: DataVersion[];
  vocabulary: {
    types: Record<VarType, string>; levels: Record<VarLevel, string>;
    roles: Record<VarRole, string>; operations: Record<string, string>;
  };
}

export interface PreviewPage {
  total: number;
  offset: number;
  columns: { key: string; name: string; type: VarType; masked: boolean }[];
  rows: (string | number | null)[][];
  row_numbers: number[];
}

interface DatasetAndProject { dataset: Dataset; project: ProjectState }

export interface RecentProject {
  path: string;
  title: string;
  opened_at: string;
  exists: boolean;
}

export interface EngineInfo {
  name: string;
  version: string;
  project_format_version: number;
  python: string;
  platform: string;
}


// ---------------------------------------------------------------- analyses
export type Alternative = 'two-sided' | 'less' | 'greater';
export type VariableKind = 'quantitative' | 'qualitative' | 'any';

export interface MethodVariable {
  name: string;
  label: string;
  kind: VariableKind;
  multiple: boolean;
  optional: boolean;
}

export interface MethodInfo {
  key: string;
  label: string;
  family: string;
  objective: string;
  variables: MethodVariable[];
  conditions: string[];
  params: string[];
  results: string[];
  warnings: string[];
  r_equivalent: string;
}

export interface Catalog {
  families: Record<string, string>;
  methods: MethodInfo[];
  param_labels: Record<string, string>;
}

export type AnalysisParams = Record<string, unknown>;
export type CellKind = 'text' | 'int' | 'num' | 'pct';
export type StatKind = 'value' | 'p' | 'df' | 'ci' | 'effect' | 'estimate';
export type DiagLevel = 'bloquant' | 'important' | 'methodologique' | 'information';

export interface SummaryStat {
  key: string;
  label: string;
  value: number | string | null;
  kind: StatKind;
  digits: number;
}

export interface ResultTable {
  title: string;
  columns: string[];
  rows: (string | number | boolean | null)[][];
  note: string;
  kinds: CellKind[];
}

export interface BoxSeries {
  label: string;
  variable: string;
  q1: number;
  median: number;
  q3: number;
  mean: number;
  whisker_low: number;
  whisker_high: number;
  outliers: number[];
  outlier_count: number;
  n: number;
}

export type Chart =
  | { type: 'histogram'; title: string; data: { variable: string; unit: string; edges: number[]; counts: number[]; n: number } }
  | { type: 'boxplot'; title: string; data: { series: BoxSeries[]; unit: string } }
  | { type: 'bar'; title: string; data: { bars: { label: string; count: number; percent: number }[]; n: number } }
  | { type: 'stacked'; title: string; data: { rows: string[]; columns: string[]; percent: number[][]; counts: number[][] } }
  | { type: 'scatter'; title: string; data: { x_label: string; y_label: string; points: [number, number][]; n: number; truncated: boolean } };

export interface AnalysisResult {
  method: string;
  method_label: string;
  title: string;
  variables: string[];
  n_used: number | null;
  missing: { strategy: string; total: number; used: number | null; excluded: number | null; text: string } | null;
  summary: SummaryStat[];
  tables: ResultTable[];
  charts: Chart[];
  diagnostics: { level: DiagLevel; title: string; detail: string }[];
  interpretation: string[];
  values: Record<string, unknown>;
}

export type AnalysisStatus = 'a_jour' | 'donnees_modifiees' | 'version_supprimee' | 'jeu_supprime' | 'version_a_corriger';

export interface AnalysisSummary {
  id: number;
  title: string;
  method: string;
  method_label: string;
  dataset_id: number;
  dataset_name: string | null;
  version_id: number | null;
  version_name: string;
  data_fingerprint: string;
  created_at: string;
  status: AnalysisStatus;
  status_label: string;
}

export interface Analysis extends AnalysisSummary {
  note: string;
  current_fingerprint: string | null;
  params: AnalysisParams;
  result: AnalysisResult;
  environment: Record<string, string>;
}

export interface ReproductionReport {
  status: AnalysisStatus;
  status_label: string;
  identical_data: boolean;
  identical_results: boolean;
  differences: { path: string; stored: unknown; recomputed: unknown }[];
  same_environment?: boolean;
  environment?: Record<string, string>;
  error?: string;
  checked_at: string;
}

export interface EngineMethods {
  'engine.info': { params: Record<string, never>; result: EngineInfo };
  'app.recent_projects': { params: Record<string, never>; result: RecentProject[] };
  'app.forget_recent': { params: { path: string }; result: null };
  'project.create': {
    params: { path: string; study: Partial<Study>; overwrite?: boolean };
    result: ProjectState;
  };
  'project.open': { params: { path: string }; result: ProjectState };
  'project.current': { params: Record<string, never>; result: ProjectState | null };
  'project.update_study': { params: { changes: Partial<Study> }; result: ProjectState };
  'project.save': { params: Record<string, never>; result: ProjectState };
  'project.save_as': { params: { path: string; overwrite?: boolean }; result: ProjectState };
  'project.close': { params: { discard_changes?: boolean }; result: null };
  'data.inspect_file': { params: { path: string; options?: Partial<ReadOptions> }; result: InspectResult };
  'data.import': {
    params: { path: string; options: Partial<ReadOptions>; name: string };
    result: { dataset_id: number; project: ProjectState };
  };
  'data.get': { params: { dataset_id: number }; result: Dataset };
  'data.delete': { params: { dataset_id: number }; result: ProjectState };
  'data.preview': {
    params: { dataset_id: number; version_id: number | null; offset: number; limit: number; reveal_identifiers: boolean };
    result: PreviewPage;
  };
  'data.quality': { params: { dataset_id: number; version_id: number | null }; result: QualityReport };
  'data.update_variable': {
    params: { dataset_id: number; key: string; changes: Partial<Variable> };
    result: DatasetAndProject;
  };
  'data.create_version': {
    params: { dataset_id: number; name: string; from_version_id: number | null };
    result: DatasetAndProject & { version_id: number };
  };
  'data.rename_version': { params: { dataset_id: number; version_id: number; name: string }; result: DatasetAndProject };
  'data.delete_version': { params: { dataset_id: number; version_id: number }; result: DatasetAndProject };
  'data.add_step': { params: { dataset_id: number; version_id: number; step: Step }; result: DatasetAndProject };
  'data.remove_step': { params: { dataset_id: number; version_id: number; index: number }; result: DatasetAndProject };
  'analysis.catalog': { params: Record<string, never>; result: Catalog };
  'analysis.run': {
    params: { dataset_id: number; version_id: number | null; method: string; params: AnalysisParams; title?: string };
    result: { analysis: Analysis; project: ProjectState };
  };
  'analysis.levels': {
    params: { dataset_id: number; version_id: number | null; key: string };
    result: { value: string; label: string; count: number }[];
  };
  'analysis.list': { params: Record<string, never>; result: AnalysisSummary[] };
  'analysis.get': { params: { analysis_id: number }; result: Analysis };
  'analysis.update': {
    params: { analysis_id: number; changes: { title?: string; note?: string } };
    result: { analysis: Analysis; project: ProjectState };
  };
  'analysis.delete': { params: { analysis_id: number }; result: ProjectState };
  'analysis.reproduce': { params: { analysis_id: number }; result: { report: ReproductionReport; project: ProjectState } };
}

export type MethodName = keyof EngineMethods;
