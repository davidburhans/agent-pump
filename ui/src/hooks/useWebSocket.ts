import { useEffect, useRef, useState } from 'react';
import { LogEntry, WorkflowState } from '../types';

interface WebSocketMessage {
  type: string;
  data: any;
}

export function useWebSocket(selectedProjectPath: string | null) {
  const [isConnected, setIsConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowState | null>(null);
  
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSocket
    // Note: In prod build, we might use relative path if served from same origin
    // For dev, vite proxy handles /ws
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws`;

    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    socket.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
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
  }, []); // Connect once on mount

  const handleMessage = (msg: WebSocketMessage) => {
    // Dispatch based on type
    switch (msg.type) {
      case 'log_entry':
        // Append log if it matches selected project (or all?)
        // The DTO has project_path.
        const entry = msg.data as LogEntry;
        if (!selectedProjectPath || entry.projectPath === selectedProjectPath) {
             setLogs(prev => [...prev, entry]);
        }
        break;
      case 'workflow_state':
        // Update workflow if matches selected project
        const state = msg.data as WorkflowState;
        // We assume message contains project path, filtering needed?
        // Ideally msg.data has projectPath or similar.
        // DTO WorkflowStateDTO doesn't have path directly, but WorkflowStateChangedEvent does.
        // Assuming the WS sends what we expect.
        setWorkflow(state);
        break;
      default:
        console.log('Unknown message type', msg.type);
    }
  };

  return { isConnected, logs, workflow };
}
