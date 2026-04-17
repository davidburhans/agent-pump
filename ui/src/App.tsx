import { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { LogPanel } from './components/LogPanel';
import { WorkflowGraph } from './components/WorkflowGraph';
import { SettingsModal } from './components/SettingsModal';
import { ProjectStatus, LogEntry, WorkflowState } from './types';
import { fetchProjects, fetchWorkflow } from './api';
import { useWebSocket } from './hooks/useWebSocket';
import { Activity, Settings, WifiOff } from 'lucide-react';
import { cn } from './utils/cn';

function App() {
  const [projects, setProjects] = useState<ProjectStatus[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

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
    if (streamWorkflow) setWorkflow(streamWorkflow);
  }, [streamWorkflow]);

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
            <span className="text-sm font-mono animate-entrance" style={{ color: 'var(--text-muted)', animationDelay: '100ms' }}>
              {selectedPath ? selectedPath.split('/').pop() : 'No project selected'}
            </span>
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
    </div>
  );
}

export default App;
