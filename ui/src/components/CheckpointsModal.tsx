import { useEffect, useState } from 'react';
import { X, History, RotateCcw, AlertTriangle } from 'lucide-react';
import { CheckpointCommit } from '../types';
import { fetchCheckpoints, createCheckpoint, rollbackCheckpoint } from '../api';

interface CheckpointsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
  projectName: string;
}

export function CheckpointsModal({ isOpen, onClose, projectPath, projectName }: CheckpointsModalProps) {
  const [checkpoints, setCheckpoints] = useState<CheckpointCommit[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (isOpen && projectPath) {
      loadCheckpoints();
    }
  }, [isOpen, projectPath]);

  const loadCheckpoints = async () => {
    setIsLoading(true);
    setError('');
    try {
      const data = await fetchCheckpoints(projectPath);
      setCheckpoints(data);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch checkpoints');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newDescription.trim()) return;
    setIsCreating(true);
    setError('');
    try {
      await createCheckpoint(projectPath, newDescription);
      setNewDescription('');
      await loadCheckpoints();
    } catch (err: any) {
      setError(err.message || 'Failed to create checkpoint');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRollback = async (commitHash: string) => {
    if (!confirm('Are you sure you want to rollback to this checkpoint? All uncommitted changes will be lost.')) {
      return;
    }
    setError('');
    try {
      await rollbackCheckpoint(projectPath, commitHash);
      await loadCheckpoints();
    } catch (err: any) {
      setError(err.message || 'Failed to rollback');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" onClick={onClose} />
      
      <div
        className="relative w-full max-w-3xl rounded-xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden animate-entrance"
        style={{
          background: 'var(--bg-primary)',
          border: '1px solid var(--border-active)'
        }}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-[rgba(245,158,11,0.1)]">
              <History className="w-4 h-4 text-[var(--accent-amber)]" />
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
                Checkpoints & Rollbacks
              </h2>
              <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                {projectName}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg transition-colors hover:bg-[var(--bg-hover)] text-[var(--text-muted)] hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 flex-1 overflow-y-auto space-y-6">
          {error && (
            <div className="p-3 rounded-lg flex items-start gap-2 bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.2)] text-[var(--accent-red)]">
              <AlertTriangle className="w-4 h-4 mt-0.5" />
              <div className="text-sm">{error}</div>
            </div>
          )}

          <div className="flex gap-2 items-center">
            <input
              type="text"
              placeholder="Description for manual checkpoint..."
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="flex-1 px-3 py-2 rounded-lg text-sm transition-all duration-200 outline-none font-mono"
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)'
              }}
              onFocus={(e) => e.target.style.borderColor = 'var(--accent-amber)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--border-subtle)'}
            />
            <button
              onClick={handleCreate}
              disabled={isCreating || !newDescription.trim()}
              className="px-4 py-2 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50"
              style={{
                background: 'var(--accent-amber)',
                color: '#fff',
              }}
            >
              {isCreating ? 'Creating...' : 'Create Checkpoint'}
            </button>
          </div>

          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-[var(--text-secondary)]">History</h3>
            {isLoading ? (
              <div className="text-sm text-[var(--text-muted)]">Loading checkpoints...</div>
            ) : checkpoints.length === 0 ? (
              <div className="text-sm text-[var(--text-muted)]">No checkpoints found for this project.</div>
            ) : (
              <div className="space-y-2">
                {checkpoints.map((cp) => (
                  <div key={cp.hash} className="p-3 rounded-lg border flex items-center justify-between" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-tertiary)' }}>
                    <div>
                      <div className="text-sm font-medium text-[var(--text-primary)]">
                        {cp.message}
                      </div>
                      <div className="text-xs text-[var(--text-muted)] font-mono flex items-center gap-2 mt-1">
                        <span>{cp.short_hash}</span>
                        <span>•</span>
                        <span>{new Date(cp.timestamp).toLocaleString()}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleRollback(cp.hash)}
                      className="px-3 py-1.5 rounded flex items-center gap-1.5 text-xs font-semibold transition-colors hover:bg-[rgba(239,68,68,0.1)] text-[var(--text-muted)] hover:text-[var(--accent-red)]"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      Rollback
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
