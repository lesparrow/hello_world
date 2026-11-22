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
}

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
}

export type MethodName = keyof EngineMethods;
