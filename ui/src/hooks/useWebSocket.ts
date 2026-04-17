import { useEffect, useRef, useState } from 'react';
import { LogEntry, WorkflowState } from '../types';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export function useWebSocket(selectedProjectPath: string | null) {
  const [isConnected, setIsConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const selectedProjectPathRef = useRef<string | null>(null);

  useEffect(() => {
    selectedProjectPathRef.current = selectedProjectPath;
  }, [selectedProjectPath]);

  const sendJoinProject = (projectPath: string | null) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({
        type: 'join_project',
        project_path: projectPath,
      }));
    }
  };

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      sendJoinProject(selectedProjectPathRef.current);
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    };

    const handleMessage = (msg: WebSocketMessage) => {
      switch (msg.type) {
        case 'log_entry':
          if (msg.project_path || msg.projectPath) {
            const entry: LogEntry = {
              timestamp: msg.timestamp || new Date().toISOString(),
              level: msg.level || 'INFO',
              message: msg.message || '',
              projectPath: msg.project_path || msg.projectPath,
              state: msg.state || 'unknown',
              task: msg.task || null,
            };
            const currentProject = selectedProjectPathRef.current;
            if (!currentProject || entry.projectPath === currentProject) {
              setLogs(prev => [...prev, entry]);
            }
          }
          break;
        case 'workflow_state':
          if (msg.project_path || msg.projectPath) {
            const state: WorkflowState = {
              currentState: msg.new_state || msg.currentState || 'unknown',
              iteration: msg.iteration || 0,
              timeInState: msg.time_in_state || 0,
              availableTransitions: msg.available_transitions || [],
              nodes: msg.nodes || [],
              edges: msg.edges || [],
            };
            setWorkflow(state);
          }
          break;
        case 'connected':
        case 'heartbeat_ack':
          break;
        default:
          console.log('Unknown message type', msg.type);
      }
    };

    socket.onmessage = (event) => {
      try {
        const msg: WebSocketMessage = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.error('Failed to parse WS message', e);
      }
    };

    return () => {
      socket.close();
    };
  }, []);

  useEffect(() => {
    sendJoinProject(selectedProjectPath);
  }, [selectedProjectPath]);

  return { isConnected, logs, workflow };
}
