import { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { LogPanel } from './components/LogPanel';
import { WorkflowGraph } from './components/WorkflowGraph';
import { SettingsModal } from './components/SettingsModal';
import { ProjectConfigModal } from './components/ProjectConfigModal';
import { RoadmapModal } from './components/RoadmapModal';
import { DiffModal } from './components/DiffModal';
import { WorkflowDesignerModal } from './components/WorkflowDesignerModal';
import { ProjectStatus, LogEntry, WorkflowState } from './types';
import {
  fetchProjects,
  fetchWorkflow,
  startProject,
  stopProject,
  resetProject,
  skipProjectFeature,
  addProject,
  removeProject
} from './api';
import { useWebSocket } from './hooks/useWebSocket';
import {
  Activity,
  Settings,
  WifiOff,
  Play,
  Square,
  RotateCcw,
  SkipForward,
  Map as MapIcon,
  FileDiff,
  GitBranch
} from 'lucide-react';
import { cn } from './utils/cn';

function App() {
  const [projects, setProjects] = useState<ProjectStatus[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [showProjectConfig, setShowProjectConfig] = useState(false);
  const [showRoadmap, setShowRoadmap] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [showWorkflowDesigner, setShowWorkflowDesigner] = useState(false);

  const { isConnected, logs: streamLogs, workflow: streamWorkflow } = useWebSocket(selectedPath);

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);

  useEffect(() => {
    fetchProjects().then(setProjects).catch(console.error);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '?' && !showSettings) {
        e.preventDefault();
        setShowSettings(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [showSettings]);

  useEffect(() => {
    if (streamLogs.length > 0) {
      setLogs(streamLogs);
    }
  }, [streamLogs]);

  useEffect(() => {
    if (streamWorkflow) {
      setWorkflow(streamWorkflow);
      // Real-time workflow state change triggers a list refresh to update state badges in sidebar
      fetchProjects().then(setProjects).catch(console.error);
    }
  }, [streamWorkflow]);

  const selectedProject = projects.find(p => p.path === selectedPath) || null;

  const isRunning = selectedProject
    ? !['idle', 'completed', 'error'].includes(selectedProject.state.toLowerCase())
    : false;

  const canStart = selectedProject?.state.toLowerCase() === 'idle';
  const canStop = isRunning;
  const canReset = selectedProject
    ? ['idle', 'completed', 'error'].includes(selectedProject.state.toLowerCase())
    : false;
  const canSkip = selectedProject ? !!selectedProject.currentFeature : false;

  const handleStart = async () => {
    if (!selectedPath) return;
    try {
      await startProject(selectedPath);
      const updated = await fetchProjects();
      setProjects(updated);
    } catch (e) {
      console.error('Failed to start project:', e);
    }
  };

  const handleStop = async () => {
    if (!selectedPath) return;
    try {
      await stopProject(selectedPath);
      const updated = await fetchProjects();
      setProjects(updated);
    } catch (e) {
      console.error('Failed to stop project:', e);
    }
  };

  const handleReset = async () => {
    if (!selectedPath) return;
    try {
      await resetProject(selectedPath);
      const updated = await fetchProjects();
      setProjects(updated);
      const wf = await fetchWorkflow(selectedPath);
      setWorkflow(wf);
    } catch (e) {
      console.error('Failed to reset project:', e);
    }
  };

  const handleSkip = async () => {
    if (!selectedPath) return;
    try {
      await skipProjectFeature(selectedPath);
      const updated = await fetchProjects();
      setProjects(updated);
    } catch (e) {
      console.error('Failed to skip project feature:', e);
    }
  };

  const handleAddProject = async (path: string) => {
    const newProj = await addProject(path);
    setProjects(prev => [...prev, newProj]);
    await handleSelectProject(newProj.path);
  };

  const handleRemoveProject = async (path: string) => {
    await removeProject(path);
    setProjects(prev => prev.filter(p => p.path !== path));
    if (selectedPath === path) {
      setSelectedPath(null);
      setWorkflow(null);
      setLogs([]);
    }
  };

  const handleSelectProject = async (path: string) => {
    setSelectedPath(path);
    setLogs([]);
    try {
      const workflowState = await fetchWorkflow(path);
      setWorkflow(workflowState);
    } catch (e) {
      console.error('Failed to fetch workflow:', e);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
      {/* Atmospheric background */}
      <div className="fixed inset-0 atmosphere pointer-events-none" />

      {/* Subtle grain texture overlay */}
      <div className="fixed inset-0 grain-overlay pointer-events-none" />

      <Sidebar
        projects={projects}
        selectedPath={selectedPath}
        onSelectProject={handleSelectProject}
        onAddProject={handleAddProject}
        onRemoveProject={handleRemoveProject}
      />

      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Header */}
        <header
          className="flex items-center justify-between px-6 py-4 border-b backdrop-blur-sm"
          style={{
            background: 'rgba(10, 12, 16, 0.85)',
            borderColor: 'var(--border-subtle)'
          }}
        >
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div
                className={cn(
                  "w-9 h-9 rounded-xl flex items-center justify-center animate-entrance relative",
                  isConnected && "animate-breathing"
                )}
                style={{
                  background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
                  boxShadow: isConnected ? '0 0 20px rgba(91, 141, 239, 0.3)' : 'none'
                }}
              >
                <Activity className="w-5 h-5 text-white" />
              </div>
              <h1 className="text-lg font-display italic tracking-wide animate-entrance" style={{ color: 'var(--text-primary)', animationDelay: '50ms' }}>
                Agent Pump
              </h1>
            </div>
            <div className="h-5 w-px" style={{ background: 'var(--border-subtle)' }} />
            <span className="text-sm font-mono animate-entrance animate-shine flex items-center gap-2" style={{ color: 'var(--text-muted)', animationDelay: '100ms' }}>
              {selectedPath ? selectedPath.split(/[/\\]/).pop() : 'No project selected'}
              {selectedProject && (
                <>
                  <button
                    onClick={() => setShowRoadmap(true)}
                    title="Project Roadmap"
                    className="p-1.5 rounded-lg border transition-all duration-200 flex items-center justify-center text-xs font-semibold backdrop-blur-sm hover:bg-[rgba(139,92,246,0.15)] hover:border-[var(--accent-purple)] text-[var(--text-muted)] hover:text-[var(--accent-purple)] border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] cursor-pointer"
                  >
                    <MapIcon className="w-3.5 h-3.5" />
                    <span className="ml-1 text-xs">Roadmap</span>
                  </button>
                  <button
                    onClick={() => setShowDiff(true)}
                    title="Code Review & Diff"
                    className="p-1.5 rounded-lg border transition-all duration-200 flex items-center justify-center text-xs font-semibold backdrop-blur-sm hover:bg-[rgba(59,130,246,0.15)] hover:border-[rgba(59,130,246,0.5)] text-[var(--text-muted)] hover:text-[rgba(96,165,250,1)] border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] cursor-pointer"
                  >
                    <FileDiff className="w-3.5 h-3.5" />
                    <span className="ml-1 text-xs">Diff</span>
                  </button>
                </>
              )}
            </span>
            {selectedProject && (
              <div className="flex items-center gap-2 animate-entrance ml-6" style={{ animationDelay: '120ms' }}>
                <button
                  onClick={handleStart}
                  disabled={!canStart}
                  title="Start Workflow"
                  className={cn(
                    "px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center justify-center gap-1.5 text-xs font-semibold backdrop-blur-sm",
                    canStart
                      ? "hover:bg-[rgba(16,185,129,0.15)] hover:border-[var(--accent-green)] text-[var(--accent-green)] border-[rgba(16,185,129,0.25)] bg-[rgba(16,185,129,0.05)] cursor-pointer"
                      : "opacity-45 cursor-not-allowed border-transparent bg-transparent text-[var(--text-muted)]"
                  )}
                  style={{
                    boxShadow: isRunning ? '0 0 15px rgba(16, 185, 129, 0.25)' : 'none'
                  }}
                >
                  <Play className={cn("w-3.5 h-3.5 fill-current", isRunning && "animate-pulse")} />
                  <span>Start</span>
                </button>

                <button
                  onClick={handleStop}
                  disabled={!canStop}
                  title="Stop Workflow"
                  className={cn(
                    "px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center justify-center gap-1.5 text-xs font-semibold backdrop-blur-sm",
                    canStop
                      ? "hover:bg-[rgba(239,68,68,0.15)] hover:border-[var(--accent-red)] text-[var(--accent-red)] border-[rgba(239,68,68,0.25)] bg-[rgba(239,68,68,0.05)] cursor-pointer"
                      : "opacity-45 cursor-not-allowed border-transparent bg-transparent text-[var(--text-muted)]"
                  )}
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Stop</span>
                </button>

                <button
                  onClick={handleReset}
                  disabled={!canReset}
                  title="Reset Iteration Count & State"
                  className={cn(
                    "px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center justify-center gap-1.5 text-xs font-semibold backdrop-blur-sm",
                    canReset
                      ? "hover:bg-[rgba(245,158,11,0.15)] hover:border-[var(--accent-amber)] text-[var(--accent-amber)] border-[rgba(245,158,11,0.25)] bg-[rgba(245,158,11,0.05)] cursor-pointer"
                      : "opacity-45 cursor-not-allowed border-transparent bg-transparent text-[var(--text-muted)]"
                  )}
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>Reset</span>
                </button>

                <button
                  onClick={handleSkip}
                  disabled={!canSkip}
                  title="Skip Current Feature"
                  className={cn(
                    "px-3 py-1.5 rounded-lg border transition-all duration-200 flex items-center justify-center gap-1.5 text-xs font-semibold backdrop-blur-sm",
                    canSkip
                      ? "hover:bg-[rgba(91,141,239,0.15)] hover:border-[var(--accent-primary)] text-[var(--accent-primary)] border-[rgba(91,141,239,0.25)] bg-[rgba(91,141,239,0.05)] cursor-pointer"
                      : "opacity-45 cursor-not-allowed border-transparent bg-transparent text-[var(--text-muted)]"
                  )}
                >
                  <SkipForward className="w-3.5 h-3.5" />
                  <span>Skip</span>
                </button>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <div
              className="flex items-center gap-2 px-3 py-1.5 rounded-full animate-entrance"
              style={{ background: 'var(--bg-tertiary)', animationDelay: '150ms' }}
            >
              {isConnected ? (
                <>
                  <span className="relative flex h-2.5 w-2.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ background: 'var(--accent-green)' }} />
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5" style={{ background: 'var(--accent-green)' }} />
                  </span>
                  <span className="text-xs font-medium" style={{ color: 'var(--accent-green)' }}>Connected</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3.5 h-3.5" style={{ color: 'var(--accent-red)' }} />
                  <span className="text-xs font-medium" style={{ color: 'var(--accent-red)' }}>Disconnected</span>
                </>
              )}
            </div>

            {/* Keyboard shortcut hint */}
            <div
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg animate-entrance cursor-pointer transition-all duration-200"
              style={{
                background: 'var(--bg-tertiary)',
                animationDelay: '180ms',
                border: '1px solid var(--border-subtle)'
              }}
              onClick={() => setShowSettings(true)}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
                e.currentTarget.style.color = 'var(--accent-primary)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
              }}
            >
              <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>Press</span>
              <kbd
                className="px-1.5 py-0.5 rounded text-[10px] font-mono font-semibold"
                style={{
                  background: 'var(--bg-elevated)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-active)'
                }}
              >
                ?
              </kbd>
              <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>for settings</span>
            </div>

            {selectedProject && (
              <button
                onClick={() => setShowWorkflowDesigner(true)}
                className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 animate-entrance"
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                  animationDelay: '190ms'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = 'var(--accent-primary)';
                  e.currentTarget.style.color = 'var(--accent-primary)';
                  e.currentTarget.style.background = 'var(--bg-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = 'var(--border-subtle)';
                  e.currentTarget.style.color = 'var(--text-secondary)';
                  e.currentTarget.style.background = 'var(--bg-tertiary)';
                }}
              >
                <GitBranch className="w-4 h-4" style={{ color: 'var(--accent-primary)' }} />
                <span className="text-sm font-medium">Design Workflow</span>
              </button>
            )}

            <button
              onClick={() => setShowSettings(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 animate-entrance"
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-secondary)',
                animationDelay: '200ms'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
                e.currentTarget.style.color = 'var(--accent-primary)';
                e.currentTarget.style.background = 'var(--bg-hover)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
                e.currentTarget.style.color = 'var(--text-secondary)';
                e.currentTarget.style.background = 'var(--bg-tertiary)';
              }}
            >
              <Settings className="w-4 h-4" />
              <span className="text-sm font-medium">Settings</span>
            </button>
          </div>
        </header>

        {/* Main content */}
        <div className="flex-1 flex min-h-0">
          <LogPanel logs={logs} />
          <WorkflowGraph workflow={workflow} />
        </div>
      </div>

      <SettingsModal
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
      />

      <ProjectConfigModal
        isOpen={showProjectConfig}
        onClose={() => setShowProjectConfig(false)}
        projectPath={selectedPath || ''}
        projectName={selectedPath ? selectedPath.split(/[/\\]/).pop() || '' : ''}
      />

      <RoadmapModal
        isOpen={showRoadmap}
        onClose={() => setShowRoadmap(false)}
        projectPath={selectedPath || ''}
        projectName={selectedPath ? selectedPath.split(/[/\\]/).pop() || '' : ''}
      />

      <DiffModal
        isOpen={showDiff}
        onClose={() => setShowDiff(false)}
        projectPath={selectedPath || ''}
        projectName={selectedPath ? selectedPath.split(/[/\\]/).pop() || '' : ''}
      />

      <WorkflowDesignerModal
        isOpen={showWorkflowDesigner}
        onClose={() => setShowWorkflowDesigner(false)}
        projectPath={selectedPath || ''}
      />
    </div>
  );
}

export default App;
