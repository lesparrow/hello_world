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
  power_count: number;
  ai_count: number;
  plan_status: { version: number; status: PlanVersionStatus; locked_version: number | null } | null;
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
  | { type: 'scatter'; title: string; data: { x_label: string; y_label: string; points: [number, number][]; n: number; truncated: boolean } }
  | { type: 'power_curve'; title: string; data: PowerCurveData };

export interface PowerCurveData {
  x_label: string;
  series: { label: string; points: [number, number | null][] }[];
  target: number | null;
  marker: number | null;
}

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

export type AdviceObjective = 'describe' | 'compare_groups' | 'compare_paired' | 'relate';
export type AnalysisPurpose = 'confirmatoire' | 'exploratoire';

export interface AdviceRequest {
  objective: AdviceObjective;
  variables: Record<string, string | string[]>;
  levels?: string[];
  independent?: boolean;
  purpose?: AnalysisPurpose | null;
  hypothesis?: number | null;
}

export interface AdviceAlternative {
  method: string | null;
  label: string;
  params: AnalysisParams;
  when: string;
  available: boolean;
}

export interface Advice {
  rules_version: string;
  objective: AdviceObjective;
  objective_label: string;
  recommendation: {
    method: string;
    label: string;
    params: AnalysisParams;
    reasons: string[];
    conditions: string[];
    checks: string[];
    limits: string[];
  } | null;
  blocking: string | null;
  alternatives: AdviceAlternative[];
  missing_information: string[];
  observations: string[];
  principle: string;
  request: AdviceRequest;
}

/** Choix transmis au moteur avec l'analyse (le moteur recalcule la recommandation). */
export interface ChoiceInput {
  mode: 'assistant' | 'direct';
  request?: AdviceRequest;
  reason?: string;
  purpose?: AnalysisPurpose | null;
  hypothesis?: number | null;
  plan_item?: string | null;
  plan_reason?: string;
}

/** Choix enregistré avec l'analyse. */
export interface MethodChoice {
  mode: 'assistant' | 'direct';
  chosen?: string;
  chosen_label?: string;
  reason?: string;
  purpose?: AnalysisPurpose | null;
  purpose_label?: string | null;
  hypothesis?: number | null;
  hypothesis_text?: string | null;
  rules_version?: string;
  objective?: AdviceObjective;
  objective_label?: string;
  recommended?: string | null;
  recommended_label?: string | null;
  recommendation_reasons?: string[];
  followed?: boolean;
  missing_information?: string[];
  plan?: PlanLink;
}

export interface PlanLink {
  item: string;
  version: number;
  locked_at: string;
  planned: string;
  planned_method: string;
  planned_variables: string[];
  deviation: boolean;
  deviations: string[];
  reason: string;
}

// ------------------------------------------------------------------ puissance
export type PowerDesign = 't_two' | 't_paired' | 't_one' | 'prop_two' | 'chi2' | 'correlation';
export type PowerMode = 'sample_size' | 'power' | 'effect';
export type PowerSides = 'two-sided' | 'one-sided';

export interface PowerDesignInfo {
  key: PowerDesign;
  label: string;
  effect: 'd' | 'h' | 'w' | 'r';
  effect_label: string;
  groups: 1 | 2;
  sided: boolean;
  benchmarks: number[];
  unit: string;
  n_min: number;
  methods: string[];
  assumptions: string[];
  r_equivalent: string;
}

export interface PowerCatalog {
  designs: PowerDesignInfo[];
  modes: { key: PowerMode; label: string }[];
  alternatives: { key: PowerSides; label: string }[];
  max_effects: number;
  alpha_range: [number, number];
  power_range: [number, number];
}

export type PowerEffect = { d?: number; diff?: number; sd?: number; p1?: number; p2?: number; h?: number; w?: number; r?: number };

export interface PowerRequest {
  design: PowerDesign;
  mode: PowerMode;
  alpha?: number;
  power?: number;
  alternative?: PowerSides;
  effects?: PowerEffect[];
  ratio?: number;
  attrition?: number;
  n?: number;
  n1?: number;
  n2?: number;
  df?: number;
  rows?: number;
  cols?: number;
  p_ref?: number;
  effect_source?: string;
  source_analysis?: number | null;
}

export interface PowerRow {
  effect: number;
  effect_text?: string;
  n1: number;
  n2: number | null;
  n_total: number;
  power: number;
  recruit_total?: number;
}

export interface PowerResult {
  request: PowerRequest;
  design: PowerDesign;
  design_label: string;
  mode: PowerMode;
  mode_label: string;
  title: string;
  summary: SummaryStat[];
  tables: ResultTable[];
  charts: Chart[];
  diagnostics: { level: DiagLevel; title: string; detail: string }[];
  interpretation: string[];
  assumptions: string[];
  rows: PowerRow[];
  method_note: string;
  r_equivalent: string;
  disclaimer: string;
}

export interface PowerCalcSummary {
  id: number;
  created_at: string;
  title: string;
  design: PowerDesign;
  design_label: string;
  mode: PowerMode;
  mode_label: string;
  headline: string;
  locked_in_plan: number[];
}

export interface PowerCalc {
  id: number;
  created_at: string;
  title: string;
  request: PowerRequest;
  result: PowerResult;
  environment: Record<string, string>;
  locked_in_plan: number[];
}

// ------------------------------------------------------------------ plan d'analyse
export type PlanVersionStatus = 'brouillon' | 'verrouille';

export interface PlanItem {
  id?: string | null;
  method: string;
  variables: Record<string, string[]>;
  hypothesis: number | null;
  role: 'principale' | 'secondaire';
  alternative: 'two-sided' | 'less' | 'greater';
  description: string;
  power_calc: number | null;
}

export interface PlanContent {
  objectives: string;
  hypotheses: string[];
  primary_variables: string[];
  secondary_variables: string[];
  analyses: PlanItem[];
  exclusion_criteria: string;
  missing_values: string;
  exploratory: string;
  multiplicity: string;
  alpha: number;
  sample_size: number | null;
  power_calc: number | null;
}

export interface PlanChange { field: string; label: string; kind: 'ajoute' | 'retire' | 'modifie'; detail: string }

export interface PlanVersion {
  version: number;
  status: PlanVersionStatus;
  created_at: string;
  updated_at: string;
  locked_at: string | null;
  change_reason: string;
  changes: PlanChange[];
  content?: PlanContent;
}

export interface PlanState {
  current: (PlanVersion & { content: PlanContent }) | null;
  locked: (PlanVersion & { content: PlanContent }) | null;
  versions: PlanVersion[];
  empty: PlanContent;
  pending_changes: PlanChange[];
}

export interface Analysis extends AnalysisSummary {
  note: string;
  choice: MethodChoice;
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

export type ReportFormat = 'docx' | 'pdf';
export type CheckLevel = 'bloquant' | 'important' | 'methodologique' | 'information';

export interface ReportTemplates {
  templates: { key: string; label: string; document: string; sections: string[] }[];
  sections: { key: string; label: string }[];
  cover_fields: { key: string; label: string }[];
  formats: { key: ReportFormat; label: string }[];
}

export interface ReportOptions {
  template: string;
  cover: Record<string, string>;
  sections: Record<string, boolean>;
  analyses: number[];
  power: number[];
  figures: boolean;
  ai_texts: boolean;
}

export interface ReportCheck {
  items: { level: CheckLevel; title: string; detail: string; analysis_id: number | null }[];
  passed: string[];
  blocking: number;
}

export interface OutlineItem {
  kind: 'heading' | 'table' | 'figure';
  level?: number;
  text: string;
}

export interface ReportExport {
  path: string;
  file_name: string;
  size: number;
  tables: number;
  figures: number;
  checks: ReportCheck;
}

// ---------------------------------------------------------------- IA locale (optionnelle)
export type AiProvider = 'ollama' | 'openai';
export type AiState = 'desactivee' | 'serveur_absent' | 'aucun_modele' | 'modele_absent' | 'modele_a_choisir'
  | 'prete' | 'inconnu';

export interface AiSettings {
  enabled: boolean;
  provider: AiProvider;
  base_url: string;
  model: string;
  temperature: number;
  max_tokens: number;
  timeout: number;
}

export interface AiModel { name: string; size: number | null; parameters: string | null; quantization: string | null }

export interface AiResources {
  memory_total: number | null;
  memory_available: number | null;
  disk_free: number | null;
  cpu_cores: number | null;
  recommendation: { size: string; examples: string[]; note: string } | null;
  warnings: string[];
}

export interface AiStatus {
  settings: AiSettings;
  providers: { key: AiProvider; label: string; default_url: string }[];
  resources: AiResources;
  server: { reachable: boolean; error: string | null } | null;
  models: AiModel[];
  state: AiState;
  message: string;
  ready: boolean;
}

export interface AiTask { key: string; label: string; help: string; needs_text: boolean }

export interface AiContext {
  text: string;
  hash: string;
  sections: string[];
  excluded: string[];
  truncated: boolean;
  chars: number;
}

export interface AiChecks {
  numbers_total: number;
  unverified: { text: string; start: number; end: number }[];
  warnings: string[];
  empty: boolean;
  blocking: boolean;
}

export type AiTextStatus = 'proposition' | 'retenu' | 'ecarte';

export interface AiText {
  id: number;
  analysis_id: number;
  created_at: string;
  task: string;
  task_label: string;
  provider: AiProvider;
  model: string;
  settings: AiSettings;
  prompt_version: string;
  context: string;
  context_hash: string;
  raw_text: string;
  text: string;
  checks: AiChecks;
  status: AiTextStatus;
  status_label: string;
  edited: boolean;
  reviewed_at: string | null;
  updated_at: string;
  duration: number | null;
}

export interface AiJob {
  id: number;
  status: 'en_cours' | 'termine' | 'erreur' | 'annule';
  text: string;
  error: string | null;
  elapsed: number;
  finish: { finish?: string; model?: string };
  meta: { analysis_id: number; task: string; task_label: string };
  ai_text: AiText | null;
}

export interface EngineMethods {
  'ai.status': { params: { probe?: boolean }; result: AiStatus };
  'ai.update_settings': { params: { changes: Partial<AiSettings> }; result: AiStatus };
  'ai.tasks': { params: Record<string, never>; result: AiTask[] };
  'ai.preview': { params: { analysis_id: number }; result: AiContext };
  'ai.generate': { params: { analysis_id: number; task: string; user_text?: string }; result: AiJob };
  'ai.job': { params: { job_id: number }; result: AiJob };
  'ai.cancel': { params: { job_id: number }; result: AiJob };
  'ai.texts': { params: { analysis_id?: number }; result: AiText[] };
  'ai.check': { params: { text_id: number; text: string }; result: AiChecks };
  'ai.keep': { params: { text_id: number; text: string; reviewed: boolean }; result: { ai_text: AiText; project: ProjectState } };
  'ai.discard': { params: { text_id: number }; result: { ai_text: AiText; project: ProjectState } };
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
    params: { dataset_id: number; version_id: number | null; method: string; params: AnalysisParams; title?: string;
      choice?: ChoiceInput;
    };
    result: { analysis: Analysis; project: ProjectState };
  };
  'power.catalog': { params: Record<string, never>; result: PowerCatalog };
  'power.compute': { params: { request: PowerRequest }; result: PowerResult };
  'power.save': { params: { request: PowerRequest; title?: string }; result: { calc: PowerCalc; project: ProjectState } };
  'power.list': { params: Record<string, never>; result: PowerCalcSummary[] };
  'power.get': { params: { power_id: number }; result: PowerCalc };
  'power.rename': { params: { power_id: number; title: string }; result: { calc: PowerCalc; project: ProjectState } };
  'power.delete': { params: { power_id: number }; result: ProjectState };
  'power.from_analysis': {
    params: { analysis_id: number };
    result: { request: PowerRequest; analysis_id: number; analysis_title: string; design_label: string };
  };
  'plan.get': { params: Record<string, never>; result: PlanState };
  'plan.save': { params: { content: PlanContent }; result: { plan: PlanState; project: ProjectState } };
  'plan.lock': { params: { reason: string }; result: { plan: PlanState; project: ProjectState } };
  'plan.discard': { params: Record<string, never>; result: { plan: PlanState; project: ProjectState } };
  'plan.version': { params: { version: number }; result: PlanVersion & { content: PlanContent } };
  'report.templates': { params: Record<string, never>; result: ReportTemplates };
  'report.options': { params: Record<string, never>; result: ReportOptions };
  'report.check': {
    params: { options: ReportOptions };
    result: { options: ReportOptions; checks: ReportCheck; outline: OutlineItem[]; project: ProjectState };
  };
  'report.export': {
    params: { path: string; format: ReportFormat; options: ReportOptions };
    result: { export: ReportExport; project: ProjectState };
  };
  'analysis.advise': {
    params: { dataset_id: number; version_id: number | null; request: AdviceRequest };
    result: Advice;
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
