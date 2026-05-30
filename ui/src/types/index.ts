export interface ProjectStatus {
  name: string;
  path: string;
  state: string;
  iteration: number;
  currentFeature?: string | null;
  currentActivity?: string | null;
  timeInState: number;
}

export interface NodeSnapshot {
  name: string;
  isActive: boolean;
  isCompleted: boolean;
  position?: [number, number] | null;
}

export interface EdgeSnapshot {
  source: string;
  target: string;
  isActive: boolean;
}

export interface WorkflowState {
  currentState: string;
  iteration: number;
  timeInState: number;
  availableTransitions: string[];
  nodes: NodeSnapshot[];
  edges: EdgeSnapshot[];
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  projectPath?: string | null;
  state: string;
  task?: string | null;
}

export interface Workspace {
  name: string;
  projects: ProjectStatus[];
}

export interface ModelCatalog {
  backends: Record<string, string[]>;
}

export interface ProjectWorkflowConfig {
  maxIterations: number;
  timeout: number;
  branch: string | null;
}

export interface ProjectVerificationConfig {
  buildCmd: string | null;
  lintCmd: string | null;
  testCmd: string | null;
  coverageCmd: string | null;
  coverageThreshold: number;
  skipVerification: boolean;
  sandboxImage: string | null;
}

export interface ProjectConfig {
  backend: string;
  workflow: ProjectWorkflowConfig;
  verification: ProjectVerificationConfig;
}

export interface BackendInstance {
  name: string;
  args: string[];
  timeout: number | null;
  concurrencyLimit: number;
}

export interface BackendFallback {
  backends: BackendInstance[];
}

export interface PhaseBackends {
  defaults: BackendFallback;
  planning: BackendFallback;
  implementing: BackendFallback;
  verifying: BackendFallback;
  brainstorming: BackendFallback;
  committing: BackendFallback;
}

export interface BackendPreset {
  name: string;
  backends: BackendFallback;
}

export interface ProjectBackends {
  defaultChain: BackendFallback | null;
  phaseBackends: PhaseBackends;
  presets: BackendPreset[];
}

export interface GeneralSettings {
  notificationsEnabled: boolean;
}

export interface PhaseMetricsDTO {
  phase: string;
  duration_seconds: number;
}

export interface VerificationResultDTO {
  command_type: string;
  command: string | null;
  status: string;
  duration_seconds: number;
  executed_at: string;
}

export interface FeatureCompletionDTO {
  name: string;
  project_path: string;
  started_at: string;
  completed_at: string;
  phases: PhaseMetricsDTO[];
  verification_results: VerificationResultDTO[];
  iterations: number;
  success: boolean;
  total_duration_seconds: number;
  verification_success_rate: number;
}

export interface ProjectMetricsDTO {
  project_path: string;
  project_name: string;
  total_features: number;
  successful_features: number;
  failed_features: number;
  average_duration_seconds: number;
  verification_success_rate: number;
  phase_durations: Record<string, number>;
  features: FeatureCompletionDTO[];
}

export interface CheckpointCommit {
  hash: string;
  short_hash: string;
  message: string;
  timestamp: string;
  author: string;
}
export interface Checkpoint {
  id: string;
  timestamp: string;
  phase: string;
  feature_name: string | null;
  git_commit_hash: string;
  description: string;
  files_modified: string[];
  auto_created: boolean;
}

export type RoadmapStatus = 'not_started' | 'in_progress' | 'deferred' | 'completed';

export interface RoadmapItem {
  title: string;
  status: RoadmapStatus;
  priority: string;
  description: string;
  metadata: Record<string, string | number | boolean>;
  status_emoji?: string;
}

export interface Roadmap {
  current_sprint: RoadmapItem[];
  future_sprints: RoadmapItem[];
  deferred: RoadmapItem[];
}

export interface IdeaSubmit {
  title: string;
  description: string;
  priority?: string;
  section?: 'current' | 'future' | 'deferred';
  position?: 'top' | 'bottom';
}

export interface RoutingChoice {
  target: string;
  description: string;
}

export interface WorkflowRouting {
  type: string;
  prompt_template: string | null;
  choices: RoutingChoice[];
}

export interface WorkflowPhase {
  name: string;
  description: string;
  icon: string;
  on_success: string;
  on_failure: string;
  allow_failure_recovery: boolean;
  timeout: number | null;
  max_retries: number;
  retry_delay: number;
  routing: WorkflowRouting | null;
}

export interface WorkflowDefinition {
  name: string;
  description: string;
  initial_state: string;
  terminal_states: string[];
  phases: WorkflowPhase[];
}


