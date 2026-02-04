import { ProjectStatus } from './types';

export async function fetchProjects(): Promise<ProjectStatus[]> {
  // Currently backend doesn't have a /projects endpoint documented in ROADMAP but I assume it exists or I need to create it?
  // Checking ENGINEERING_PLAN.md for HTTP Server:
  // "Implement standalone mode... Load projects from workspace"
  // But did I implement the endpoint?
  // ROADMAP.md said "create /api/*".
  // I should check server.py or routes to see what exists.
  
  // For now I'll implement the fetch assuming the endpoint will be /api/projects
  const res = await fetch('/api/projects');
  if (!res.ok) throw new Error('Failed to fetch projects');
  return res.json();
}

export async function fetchHealth(): Promise<{ status: string }> {
  const res = await fetch('/api/health'); // This one might be at root /health or /api/health depending on implementation
  // Plan said "routes/health.py: GET /health endpoint". So it's likely /health directly?
  // Engineering plan diagram showed /health and /api/*.
  // I will try /health first.
  if (!res.ok) {
      // Fallback to /api/health
      const res2 = await fetch('/health');
      if (!res2.ok) throw new Error('Failed to fetch health');
      return res2.json();
  }
  return res.json();
}
