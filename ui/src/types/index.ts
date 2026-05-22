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

