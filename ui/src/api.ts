import { ProjectStatus, ModelCatalog, WorkflowState } from './types';

export async function fetchProjects(): Promise<ProjectStatus[]> {
  const res = await fetch('/api/projects');
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

export async function fetchWorkflow(projectPath: string): Promise<WorkflowState> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/workflow`);
  if (!res.ok) throw new Error('Failed to fetch workflow');
  return res.json();
}

export async function fetchModelCatalog(): Promise<ModelCatalog> {
  const response = await fetch('/api/settings/model-catalog');
  if (!response.ok) throw new Error('Failed to fetch model catalog');
  return response.json();
}

export async function updateModelCatalog(catalog: ModelCatalog): Promise<void> {
  const response = await fetch('/api/settings/model-catalog', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
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
  const res = await fetch(`/api/projects/${encodedPath}/start`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to start project');
  return res.json();
}

export async function stopProject(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/stop`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to stop project');
  return res.json();
}

export async function resetProject(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/reset`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to reset project');
  return res.json();
}

export async function skipProjectFeature(projectPath: string): Promise<ProjectControlResponse> {
  const encodedPath = encodeURIComponent(projectPath);
  const res = await fetch(`/api/projects/${encodedPath}/skip`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to skip project feature');
  return res.json();
}

export async function addProject(projectPath: string): Promise<ProjectStatus> {
  const res = await fetch('/api/projects/add', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  const res = await fetch(`/api/projects/${encodedPath}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to remove project');
  }
  return res.json();
}

