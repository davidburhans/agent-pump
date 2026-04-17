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
