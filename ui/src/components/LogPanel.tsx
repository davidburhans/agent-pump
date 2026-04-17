import { useEffect, useRef, useState } from 'react';
import { LogEntry } from '../types';
import { Terminal, Filter, ChevronDown, ArrowDown } from 'lucide-react';

type LogLevel = 'ALL' | 'ERROR' | 'WARNING' | 'INFO' | 'DEBUG';

interface LogPanelProps {
  logs: LogEntry[];
}

const levelConfig: Record<string, { color: string; bg: string; label: string }> = {
  ERROR: { color: 'var(--accent-red)', bg: 'rgba(244, 63, 94, 0.1)', label: 'Error' },
  WARNING: { color: 'var(--accent-amber)', bg: 'rgba(245, 158, 11, 0.1)', label: 'Warning' },
  INFO: { color: 'var(--accent-primary)', bg: 'rgba(91, 141, 239, 0.1)', label: 'Info' },
  DEBUG: { color: 'var(--text-muted)', bg: 'rgba(93, 104, 120, 0.08)', label: 'Debug' },
};

export function LogPanel({ logs }: LogPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [filter, setFilter] = useState<LogLevel>('ALL');
  const [autoScroll, setAutoScroll] = useState(true);
  const [showFilterMenu, setShowFilterMenu] = useState(false);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
    setAutoScroll(isAtBottom);
  };

  const filteredLogs = filter === 'ALL' ? logs : logs.filter(log => log.level === filter);

  const counts = logs.reduce((acc, log) => {
    acc[log.level] = (acc[log.level] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div
      className="flex-1 flex flex-col min-w-0 border-r relative"
      style={{
        background: 'var(--bg-primary)',
        borderColor: 'var(--border-subtle)'
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4 border-b backdrop-blur-sm"
        style={{
          background: 'rgba(10, 12, 16, 0.9)',
          borderColor: 'var(--border-subtle)'
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center relative"
            style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))' }}
          >
            <Terminal className="w-4 h-4 text-white" />
            {/* Live streaming indicator */}
            {logs.length > 0 && (
              <span
                className="absolute -top-1 -right-1 w-3 h-3 rounded-full"
                style={{
                  background: 'var(--accent-green)',
                  boxShadow: '0 0 8px var(--accent-green)',
                  animation: 'streaming 2s ease-out infinite'
                }}
              />
            )}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
                Activity Log
              </h2>
              {logs.length > 0 && (
                <span
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium uppercase tracking-wider"
                  style={{
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: 'var(--accent-green)',
                    animation: 'recording-pulse 1.5s ease-in-out infinite'
                  }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ background: 'var(--accent-green)' }}
                  />
                  Live
                </span>
              )}
            </div>
            <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              {filteredLogs.length} {filteredLogs.length === 1 ? 'entry' : 'entries'}
            </p>
          </div>
        </div>

        {/* Filter dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowFilterMenu(!showFilterMenu)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all duration-200"
            style={{
              background: showFilterMenu ? 'var(--bg-elevated)' : 'var(--bg-tertiary)',
              border: `1px solid ${showFilterMenu ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
              color: showFilterMenu ? 'var(--accent-primary)' : 'var(--text-secondary)',
              boxShadow: showFilterMenu ? '0 0 12px var(--accent-primary-glow)' : 'none'
            }}
            onMouseEnter={(e) => {
              if (!showFilterMenu) {
                e.currentTarget.style.borderColor = 'var(--accent-primary)';
                e.currentTarget.style.color = 'var(--accent-primary)';
              }
            }}
            onMouseLeave={(e) => {
              if (!showFilterMenu) {
                e.currentTarget.style.borderColor = 'var(--border-subtle)';
                e.currentTarget.style.color = 'var(--text-secondary)';
              }
            }}
          >
            <Filter className="w-3.5 h-3.5" />
            <span className="font-medium">{filter}</span>
            <ChevronDown
              className="w-3.5 h-3.5 transition-transform duration-200"
              style={{ transform: showFilterMenu ? 'rotate(180deg)' : 'none' }}
            />
          </button>

          {showFilterMenu && (
            <div
              className="absolute right-0 top-full mt-2 py-2 rounded-xl min-w-[160px] z-20 animate-scale-in"
              style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)'
              }}
            >
              {(['ALL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'] as LogLevel[]).map((level) => (
                <button
                  key={level}
                  onClick={() => {
                    setFilter(level);
                    setShowFilterMenu(false);
                  }}
                  className="w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors"
                  style={{
                    color: filter === level ? 'var(--accent-primary)' : 'var(--text-secondary)'
                  }}
                  onMouseEnter={(e) => {
                    if (filter !== level) {
                      e.currentTarget.style.background = 'var(--bg-hover)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <span>{level === 'ALL' ? 'All Levels' : levelConfig[level]?.label}</span>
                  {counts[level] !== undefined && (
                    <span
                      className="text-xs font-mono px-1.5 py-0.5 rounded"
                      style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}
                    >
                      {counts[level]}
                    </span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Log entries */}
      <div
        className="flex-1 overflow-y-auto p-4 font-mono text-[13px]"
        onScroll={handleScroll}
      >
        {filteredLogs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center relative">
            {/* Decorative elements */}
            <div className="absolute inset-0 opacity-5" style={{
              backgroundImage: `radial-gradient(circle at 50% 50%, var(--accent-primary) 1px, transparent 1px)`,
              backgroundSize: '16px 16px'
            }} />

            {/* Animated pulsing rings */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div
                className="w-40 h-40 rounded-full border border-[var(--accent-primary)] opacity-5 animate-ping"
                style={{ animationDuration: '4s' }}
              />
              <div
                className="absolute w-32 h-32 rounded-full border border-[var(--accent-secondary)] opacity-5 animate-ping"
                style={{ animationDuration: '3s', animationDelay: '0.5s' }}
              />
            </div>

            <div
              className="relative w-20 h-20 rounded-2xl flex items-center justify-center mb-4 animate-entrance"
              style={{
                background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-elevated))',
                border: '1px solid var(--border-subtle)',
                boxShadow: '0 0 40px rgba(91, 141, 239, 0.1)'
              }}
            >
              <Terminal className="w-10 h-10 animate-pulse" style={{ color: 'var(--text-muted)' }} />
            </div>

            <p className="relative text-sm font-display italic mb-1" style={{ color: 'var(--text-secondary)' }}>
              {filter === 'ALL' ? 'No entries recorded' : `No ${filter} entries`}
            </p>
            <p className="relative text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              {filter === 'ALL' ? 'Activity will appear in real-time' : 'Try a different filter'}
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredLogs.map((log, i) => {
              const config = levelConfig[log.level] || levelConfig.INFO;

              return (
                <div
                  key={i}
                  className="flex items-start gap-3 px-3 py-2.5 rounded-lg transition-all duration-150 hover:bg-[var(--bg-tertiary)]/60 animate-slide-up group relative"
                  style={{
                    animationDelay: `${Math.min(i * 15, 150)}ms`,
                    borderLeft: log.level === 'ERROR' ? `2px solid ${config.color}` : '2px solid transparent'
                  }}
                >
                  {/* Subtle background tint for error logs */}
                  {log.level === 'ERROR' && (
                    <div
                      className="absolute inset-0 opacity-5 rounded-lg pointer-events-none"
                      style={{ background: config.color }}
                    />
                  )}

                  {/* Timestamp */}
                  <span className="shrink-0 text-xs mt-0.5 font-mono" style={{ color: 'var(--text-muted)' }}>
                    {log.timestamp.split('T')[1]?.split('.')[0] || log.timestamp}
                  </span>

                  {/* Level badge */}
                  <span
                    className="shrink-0 inline-flex items-center justify-center w-16 px-2 py-0.5 rounded-md text-[10px] font-bold uppercase tracking-wider"
                    style={{
                      background: config.bg,
                      color: config.color
                    }}
                  >
                    {log.level}
                  </span>

                  {/* State tag */}
                  {log.state && (
                    <span
                      className="shrink-0 inline-flex items-center px-1.5 py-0.5 rounded-md text-[10px] font-medium"
                      style={{
                        background: 'var(--bg-tertiary)',
                        color: 'var(--text-muted)'
                      }}
                    >
                      {log.state}
                    </span>
                  )}

                  {/* Message */}
                  <span
                    className="flex-1 break-all whitespace-pre-wrap group-hover:text-[var(--text-primary)] transition-colors duration-150"
                    style={{ color: log.level === 'ERROR' ? 'var(--accent-red)' : 'var(--text-secondary)' }}
                  >
                    {log.message}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Scroll indicator */}
      {!autoScroll && filteredLogs.length > 0 && (
        <button
          onClick={() => {
            setAutoScroll(true);
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
          }}
          className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 animate-scale-in cursor-pointer"
          style={{
            background: 'var(--accent-primary)',
            color: 'white',
            boxShadow: 'var(--glow-primary)'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateX(-50%) translateY(-2px)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateX(-50%)';
          }}
        >
          <ArrowDown className="w-4 h-4" />
          Jump to latest
        </button>
      )}
    </div>
  );
}
