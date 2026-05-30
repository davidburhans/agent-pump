import {
  ProjectStatus,
  ModelCatalog,
  WorkflowState,
  ProjectConfig,
  ProjectBackends,
  GeneralSettings,
  BackendPreset,
  ProjectMetricsDTO,
  CheckpointCommit,
  Checkpoint,
} from './types';

function getApiKey(): string | null {
  const params = new URLSearchParams(window.location.search);
  const key = params.get('api_key') || params.get('apiKey');
  if (key) {
    sessionStorage.setItem('agent_pump_api_key', key);
    return key;
  }
  return sessionStorage.getItem('agent_pump_api_key');
}

function getHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extraHeaders };
  const apiKey = getApiKey();
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }
  return headers;
}

export async function fetchProjects(): Promise<ProjectStatus[]> {
  const res = await fetch('/api/projects', { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

export async function fetchWorkflow(projectPath: string): Promise<WorkflowState> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/workflow`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch workflow');
  return res.json();
}

export async function fetchModelCatalog(): Promise<ModelCatalog> {
  const response = await fetch('/api/settings/model-catalog', { headers: getHeaders() });
  if (!response.ok) throw new Error('Failed to fetch model catalog');
  return response.json();
}

export async function updateModelCatalog(catalog: ModelCatalog): Promise<void> {
  const response = await fetch('/api/settings/model-catalog', {
    method: 'PUT',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(catalog),
  });
  if (!response.ok) throw new Error('Failed to update model catalog');
}

export interface ProjectControlResponse {
  success: boolean;
  message: string;
}

export async function startProject(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/start`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to start project');
  return res.json();
}

export async function stopProject(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/stop`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to stop project');
  return res.json();
}

export async function resetProject(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/reset`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to reset project');
  return res.json();
}

export async function skipProjectFeature(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/skip`, {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to skip project feature');
  return res.json();
}

export async function addProject(projectPath: string): Promise<ProjectStatus> {
  const res = await fetch('/api/projects/add', {
    method: 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ path: projectPath }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to add project');
  }
  return res.json();
}

export async function removeProject(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}`, {
    method: 'DELETE',
    headers: getHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to remove project');
  }
  return res.json();
}

export async function fetchProjectConfig(projectPath: string): Promise<ProjectConfig> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/config`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch project configuration');
  return res.json();
}

export async function updateProjectConfig(projectPath: string, config: ProjectConfig): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/config`, {
    method: 'PUT',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error('Failed to update project configuration');
  return res.json();
}

export async function fetchProjectBackends(projectPath: string): Promise<ProjectBackends> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/backends`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch project backends');
  return res.json();
}

export async function updateProjectBackends(projectPath: string, backends: ProjectBackends): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/backends`, {
    method: 'PUT',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(backends),
  });
  if (!res.ok) throw new Error('Failed to update project backends');
  return res.json();
}

export async function fetchGeneralSettings(): Promise<GeneralSettings> {
  const res = await fetch('/api/settings/general', { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch general settings');
  return res.json();
}

export async function updateGeneralSettings(settings: GeneralSettings): Promise<GeneralSettings> {
  const res = await fetch('/api/settings/general', {
    method: 'PUT',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new Error('Failed to update general settings');
  return res.json();
}

export async function testNotification(): Promise<{ status: string; message: string }> {
  const res = await fetch('/api/settings/test-notification', {
    method: 'POST',
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error('Failed to trigger test notification');
  return res.json();
}

export async function saveBackendPreset(preset: BackendPreset): Promise<BackendPreset> {
  const res = await fetch('/api/settings/presets', {
    method: 'POST',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(preset),
  });
  if (!res.ok) throw new Error('Failed to save backend preset');
  return res.json();
}

export async function fetchProjectMetrics(projectPath: string): Promise<ProjectMetricsDTO> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/metrics/projects/${encodedPath}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch project metrics');
  return res.json();
}



export async function fetchCheckpoints(projectPath: string): Promise<CheckpointCommit[]> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/checkpoints`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch checkpoints");
  return res.json();
}

export async function createCheckpoint(projectPath: string, description: string): Promise<Checkpoint> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/checkpoints`, {
    method: "POST",
    headers: getHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error("Failed to create checkpoint");
  return res.json();
}

export async function rollbackCheckpoint(projectPath: string, commitHash: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/checkpoints/${commitHash}/rollback`, {
    method: "POST",
    headers: getHeaders(),
  });
  if (!res.ok) throw new Error("Failed to rollback checkpoint");
  return res.json();
}

export async function fetchRoadmap(projectPath: string): Promise<any> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/roadmap`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch roadmap");
  return res.json();
}

export async function submitIdea(projectPath: string, idea: any): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/roadmap/ideas`, {
    method: "POST",
    headers: getHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(idea),
  });
  if (!res.ok) throw new Error("Failed to submit idea");
  return res.json();
}

export async function fetchDiffs(projectPath: string, diffType: string = "all"): Promise<any[]> {
  const encodedPath = encodeURIComponent(projectPath);
  const params = new URLSearchParams({ diff_type: diffType });
  const res = await fetch(`/api/projects/${encodedPath}/diff?${params.toString()}`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch diffs");
  return res.json();
}

export async function fetchProjectWorkflowDef(projectPath: string): Promise<any> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/workflow/definition`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch workflow definition');
  return res.json();
}

export async function updateProjectWorkflowDef(projectPath: string, def: any): Promise<void> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/workflow/definition`, {
    method: 'PUT',
    headers: getHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(def),
  });
  if (!res.ok) throw new Error('Failed to update workflow definition');
}

export async function fetchWorkflowTemplate(name: string): Promise<any> {
  const res = await fetch(`/api/projects/workflows/templates/${name}`, { headers: getHeaders() });
  if (!res.ok) throw new Error('Failed to fetch template');
  return res.json();
}

