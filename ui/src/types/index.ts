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
