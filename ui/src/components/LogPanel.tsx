import { useEffect, useRef } from 'react';
import { LogEntry } from '../types';
import { cn } from '../utils/cn';

interface LogPanelProps {
  logs: LogEntry[];
}

export function LogPanel({ logs }: LogPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  return (
    <div className="flex-1 bg-gray-950 flex flex-col h-full overflow-hidden">
      <div className="p-4 border-b border-gray-800 bg-gray-900">
        <h2 className="text-xl font-bold text-white">Activity Log</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-sm">
        {logs.map((log, i) => (
          <div key={i} className="flex gap-2 hover:bg-gray-900/50 p-0.5 rounded">
            <span className="text-gray-500 shrink-0 select-none">
              [{log.timestamp}]
            </span>
            <span className={cn(
              "shrink-0 w-16 font-bold",
              log.level === 'ERROR' ? "text-red-500" :
              log.level === 'WARNING' ? "text-yellow-500" :
              "text-blue-500"
            )}>
              {log.level}
            </span>
            <span className={cn(
              "break-all whitespace-pre-wrap",
              log.level === 'ERROR' ? "text-red-400" : "text-gray-300"
            )}>
              {log.message}
            </span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
