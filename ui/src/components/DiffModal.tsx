import { useEffect, useState } from 'react';
import { X, RefreshCw, FileDiff } from 'lucide-react';
import { fetchDiffs } from '../api';

interface DiffHunk {
  header: string;
  lines: string[];
}

interface DiffFile {
  path: string;
  status: string;
  hunks: DiffHunk[];
  old_path: string | null;
}

interface DiffModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
  projectName: string;
}

export function DiffModal({ isOpen, onClose, projectPath, projectName }: DiffModalProps) {
  const [diffFiles, setDiffFiles] = useState<DiffFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && projectPath) {
      loadDiffs();
    }
  }, [isOpen, projectPath]);

  const loadDiffs = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDiffs(projectPath, 'all');
      setDiffFiles(data);
    } catch (e: any) {
      setError(e.message || 'Failed to load diffs');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      
      <div className="relative w-full max-w-5xl h-[85vh] flex flex-col rounded-xl border"
           style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}>
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b"
             style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-tertiary)' }}>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg" style={{ background: 'rgba(91,141,239,0.1)' }}>
              <FileDiff className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                Code Review & Diff
              </h2>
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                {projectName}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={loadDiffs}
              className="p-2 rounded-lg transition-colors hover:bg-white/5"
              title="Refresh"
            >
              <RefreshCw className={`w-5 h-5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg transition-colors hover:bg-white/5"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <RefreshCw className="w-8 h-8 animate-spin text-gray-400" />
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-red-400">{error}</p>
            </div>
          ) : diffFiles.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              No changes detected.
            </div>
          ) : (
            <div className="space-y-6">
              {diffFiles.map((file, idx) => (
                <div key={idx} className="rounded-lg border overflow-hidden" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="px-4 py-2 bg-white/5 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)' }}>
                    <span className="font-mono text-sm font-semibold">{file.path}</span>
                    <span className={`text-xs font-bold px-2 py-1 rounded ${
                      file.status === 'ADDED' ? 'bg-green-500/20 text-green-400' :
                      file.status === 'DELETED' ? 'bg-red-500/20 text-red-400' :
                      'bg-blue-500/20 text-blue-400'
                    }`}>
                      {file.status}
                    </span>
                  </div>
                  <div className="p-4 bg-black/40 overflow-x-auto">
                    {file.hunks.map((hunk, hIdx) => (
                      <div key={hIdx} className="mb-4 last:mb-0">
                        <div className="text-blue-400/80 font-mono text-xs mb-2 select-none">
                          {hunk.header}
                        </div>
                        <pre className="text-sm font-mono leading-relaxed" style={{ tabSize: 4 }}>
                          <code>
                            {hunk.lines.map((line, lIdx) => {
                              const isAdd = line.startsWith('+');
                              const isSub = line.startsWith('-');
                              return (
                                <div key={lIdx} className={`px-2 ${
                                  isAdd ? 'bg-green-500/10 text-green-300' :
                                  isSub ? 'bg-red-500/10 text-red-300' :
                                  'text-gray-300'
                                }`}>
                                  {line}
                                </div>
                              );
                            })}
                          </code>
                        </pre>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}