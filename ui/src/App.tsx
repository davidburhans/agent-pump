import { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { LogPanel } from './components/LogPanel';
import { WorkflowGraph } from './components/WorkflowGraph';
import { ProjectStatus, LogEntry, WorkflowState } from './types';
import { fetchProjects } from './api';
import { useWebSocket } from './hooks/useWebSocket';

function App() {
  const [projects, setProjects] = useState<ProjectStatus[]>([]);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  
  const { isConnected, logs: streamLogs, workflow: streamWorkflow } = useWebSocket(selectedPath);
  
  // Local state for logs/workflow until we have full data fetching
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);

  useEffect(() => {
    // Initial fetch
    fetchProjects().then(setProjects).catch(console.error);

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '?') {
        alert("Help: \n- Click a project to select\n- Logs update automatically");
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    // Append streamed logs
    if (streamLogs.length > 0) {
        // This logic is slightly flawed as streamLogs grows indefinitely in the hook
        // We should probably expose the latest log or handle it differently
        // For MVP, assume hook manages accumulated logs
        setLogs(streamLogs);
    }
  }, [streamLogs]);

  useEffect(() => {
      if (streamWorkflow) setWorkflow(streamWorkflow);
  }, [streamWorkflow]);

  const handleSelectProject = (path: string) => {
    setSelectedPath(path);
    // Clear logs or fetch logs for this project
    // Fetch workflow state for this project
  };

  return (
    <div className="flex h-screen bg-gray-950 text-white overflow-hidden">
      <Sidebar 
        projects={projects} 
        selectedPath={selectedPath} 
        onSelectProject={handleSelectProject} 
      />
      
      <div className="flex-1 flex flex-col min-w-0">
        <LogPanel logs={logs} />
      </div>

      <WorkflowGraph workflow={workflow} />
      
      {/* Status Bar */}
      <div className="fixed bottom-4 right-4">
        <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} title={isConnected ? "Connected" : "Disconnected"} />
      </div>
    </div>
  );
}

export default App;