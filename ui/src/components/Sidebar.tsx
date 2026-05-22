import { useState } from 'react';
import { ProjectStatus } from '../types';
import { cn } from '../utils/cn';
import { Folder, ChevronRight, Clock, Zap, Trash2 } from 'lucide-react';

interface SidebarProps {
  projects: ProjectStatus[];
  selectedPath: string | null;
  onSelectProject: (path: string) => void;
  onAddProject: (path: string) => Promise<void>;
  onRemoveProject: (path: string) => Promise<void>;
}

const stateColors: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  planning: { bg: 'rgba(91, 141, 239, 0.12)', text: 'var(--accent-primary)', border: 'rgba(91, 141, 239, 0.3)', glow: 'var(--accent-primary-glow)' },
  coding: { bg: 'rgba(6, 182, 212, 0.1)', text: 'var(--accent-cyan)', border: 'rgba(6, 182, 212, 0.25)', glow: 'rgba(6, 182, 212, 0.2)' },
  testing: { bg: 'rgba(245, 158, 11, 0.1)', text: 'var(--accent-amber)', border: 'rgba(245, 158, 11, 0.25)', glow: 'rgba(245, 158, 11, 0.2)' },
  reviewing: { bg: 'rgba(91, 141, 239, 0.12)', text: 'var(--accent-primary)', border: 'rgba(91, 141, 239, 0.3)', glow: 'var(--accent-primary-glow)' },
  completed: { bg: 'rgba(16, 185, 129, 0.1)', text: 'var(--accent-green)', border: 'rgba(16, 185, 129, 0.25)', glow: 'var(--glow-green)' },
  idle: { bg: 'rgba(93, 104, 120, 0.08)', text: 'var(--text-muted)', border: 'rgba(93, 104, 120, 0.2)', glow: 'none' },
};

export function Sidebar({ projects, selectedPath, onSelectProject, onAddProject, onRemoveProject }: SidebarProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [newPath, setNewPath] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [addError, setAddError] = useState('');

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError('');
    setIsSubmitting(true);
    try {
      await onAddProject(newPath);
      setIsAdding(false);
      setNewPath('');
    } catch (err: any) {
      setAddError(err.message || 'Failed to add project');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <aside
      className="w-72 flex flex-col h-full border-r relative"
      style={{
        background: 'var(--bg-secondary)',
        borderColor: 'var(--border-subtle)'
      }}
    >
      {/* Subtle grid pattern */}
      <div className="absolute inset-0 grid-pattern opacity-20 pointer-events-none" />

      {/* Header */}
      <div className="relative z-10 p-5 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))' }}
            >
              <Folder className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-sm font-semibold tracking-wide uppercase" style={{ color: 'var(--text-secondary)' }}>
                Projects
              </h2>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {projects.length} {projects.length === 1 ? 'workspace' : 'workspaces'}
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsAdding(true)}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-200"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
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
            title="Add Workspace Path"
          >
            <span className="text-lg font-light">+</span>
          </button>
        </div>
      </div>

      {isAdding && (
        <div className="relative z-10 px-5 py-3 border-b animate-entrance" style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-tertiary)' }}>
          <form onSubmit={handleAddSubmit} className="space-y-2">
            <label className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
              Local Project Path
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newPath}
                onChange={(e) => setNewPath(e.target.value)}
                placeholder="e.g. C:/projects/my-app"
                required
                className="flex-1 px-3 py-1.5 rounded-lg text-xs font-mono transition-all duration-200 outline-none"
                style={{
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-primary)'
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent-primary)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--border-subtle)'}
              />
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 bg-[var(--accent-primary)] hover:bg-[var(--accent-secondary)] text-white disabled:opacity-50"
              >
                {isSubmitting ? '...' : 'Add'}
              </button>
            </div>
            {addError && <p className="text-[10px] text-red-500 font-medium">{addError}</p>}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setIsAdding(false);
                  setNewPath('');
                  setAddError('');
                }}
                className="text-[10px] hover:underline"
                style={{ color: 'var(--text-muted)' }}
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Project list */}
      <div className="relative z-10 flex-1 overflow-y-auto p-3 space-y-2">
        {projects.map((project, index) => {
          const isSelected = selectedPath === project.path;
          const stateStyle = stateColors[project.state.toLowerCase()] || stateColors.idle;

          return (
            <button
              key={project.path}
              onClick={() => onSelectProject(project.path)}
              className={cn(
                'w-full text-left p-4 rounded-xl transition-all duration-200 animate-slide-in group relative overflow-hidden',
                isSelected && 'animate-shine',
                isSelected
                  ? 'border-2'
                  : 'border border-transparent hover:border-[var(--border-subtle)]'
              )}
              style={{
                background: isSelected ? stateStyle.bg : 'var(--bg-tertiary)',
                borderColor: isSelected ? stateStyle.border : 'transparent',
                animationDelay: `${index * 60}ms`,
                boxShadow: isSelected ? `0 0 25px ${stateStyle.glow}, inset 0 0 30px ${stateStyle.glow}` : 'none'
              }}
              onMouseEnter={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.background = 'var(--bg-hover)';
                  e.currentTarget.style.borderColor = 'var(--border-active)';
                  e.currentTarget.style.transform = 'translateX(2px)';
                }
              }}
              onMouseLeave={(e) => {
                if (!isSelected) {
                  e.currentTarget.style.background = 'var(--bg-tertiary)';
                  e.currentTarget.style.borderColor = 'transparent';
                  e.currentTarget.style.transform = 'translateX(0)';
                }
              }}
            >
              {/* Subtle left accent bar for selected items */}
              {isSelected && (
                <div
                  className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl"
                  style={{ background: stateStyle.text }}
                />
              )}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className="font-semibold truncate text-sm"
                      style={{ color: isSelected ? stateStyle.text : 'var(--text-primary)' }}
                    >
                      {project.name}
                    </span>
                    {project.iteration > 0 && (
                      <span
                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono font-medium"
                        style={{
                          background: 'rgba(91, 141, 239, 0.12)',
                          color: 'var(--accent-primary)'
                        }}
                      >
                        <Zap className="w-2.5 h-2.5" />
                        {project.iteration}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 mt-2">
                    {/* State badge */}
                    <span
                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase tracking-wider"
                      style={{
                        background: stateStyle.bg,
                        color: stateStyle.text
                      }}
                    >
                      {isSelected && (
                        <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: stateStyle.text }} />
                      )}
                      {project.state}
                    </span>

                    {/* Current activity */}
                    {project.currentActivity && (
                      <span
                        className="text-xs truncate max-w-[120px]"
                        style={{ color: 'var(--text-muted)' }}
                        title={project.currentActivity}
                      >
                        {project.currentActivity}
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-1 shrink-0 mt-0.5">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`Are you sure you want to remove workspace "${project.name}" from your active list?`)) {
                        onRemoveProject(project.path);
                      }
                    }}
                    className="p-1 rounded opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-[rgba(239,68,68,0.15)] text-[var(--text-muted)] hover:text-[var(--accent-red)]"
                    title="Remove Workspace"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                  <ChevronRight
                    className="w-4 h-4 transition-all duration-200"
                    style={{ color: isSelected ? stateStyle.text : 'var(--text-muted)', transform: isSelected ? 'translateX(2px)' : 'none' }}
                  />
                </div>
              </div>

              {/* Time in state with mini progress */}
              <div className="flex items-center gap-1.5 mt-2.5 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                <Clock className="w-3 h-3" />
                <span className="font-mono">
                  {project.timeInState > 0 ? `${Math.floor(project.timeInState / 60)}m ${project.timeInState % 60}s` : '--'}
                </span>
                {/* Mini progress bar showing time in state (capped at 5 min visual) */}
                {project.timeInState > 0 && (
                  <div
                    className="flex-1 h-1 rounded-full overflow-hidden"
                    style={{ background: 'var(--bg-primary)', maxWidth: '60px' }}
                  >
                    <div
                      className="h-full rounded-full transition-all duration-300"
                      style={{
                        width: `${Math.min((project.timeInState / 300) * 100, 100)}%`,
                        background: stateStyle.text,
                        opacity: 0.6
                      }}
                    />
                  </div>
                )}
              </div>
            </button>
          );
        })}

        {projects.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center relative">
            {/* Decorative grid */}
            <div
              className="absolute inset-0 opacity-10 pointer-events-none"
              style={{
                backgroundImage: `linear-gradient(rgba(91, 141, 239, 0.1) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(91, 141, 239, 0.1) 1px, transparent 1px)`,
                backgroundSize: '16px 16px'
              }}
            />

            {/* Animated pulsing rings */}
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div
                className="w-32 h-32 rounded-full border border-[var(--accent-primary)] opacity-5 animate-ping"
                style={{ animationDuration: '4s' }}
              />
              <div
                className="absolute w-24 h-24 rounded-full border border-[var(--accent-secondary)] opacity-5 animate-ping"
                style={{ animationDuration: '3s', animationDelay: '0.5s' }}
              />
            </div>

            <div
              className="relative w-16 h-16 rounded-2xl flex items-center justify-center mb-4 animate-entrance"
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-subtle)',
                boxShadow: '0 0 30px rgba(91, 141, 239, 0.1)'
              }}
            >
              <Folder className="w-8 h-8 animate-pulse" style={{ color: 'var(--text-muted)' }} />
            </div>
            <p className="relative text-sm font-display italic mb-1" style={{ color: 'var(--text-secondary)' }}>
              No workspaces active
            </p>
            <p className="relative text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              Start an agent to begin
            </p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        className="relative z-10 p-4 border-t"
        style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}
      >
        <p className="text-[10px] font-mono tracking-wider uppercase text-center" style={{ color: 'var(--text-muted)' }}>
          Agent Pump v0.1.0
        </p>
      </div>
    </aside>
  );
}
