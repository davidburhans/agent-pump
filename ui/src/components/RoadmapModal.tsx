import React, { useState, useEffect } from 'react';
import { X, Plus, AlertCircle } from 'lucide-react';
import { Roadmap, IdeaSubmit, RoadmapItem } from '../types';
import { fetchRoadmap, submitIdea } from '../api';

interface RoadmapModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
  projectName: string;
}

export function RoadmapModal({ isOpen, onClose, projectPath, projectName }: RoadmapModalProps) {
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [isAddingIdea, setIsAddingIdea] = useState(false);
  const [newIdea, setNewIdea] = useState<IdeaSubmit>({
    title: '',
    description: '',
    priority: 'Medium',
    section: 'future',
    position: 'bottom',
  });

  const loadRoadmap = async () => {
    if (!projectPath) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchRoadmap(projectPath);
      setRoadmap(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load roadmap');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadRoadmap();
      setIsAddingIdea(false);
      setNewIdea({
        title: '',
        description: '',
        priority: 'Medium',
        section: 'future',
        position: 'bottom',
      });
    }
  }, [isOpen, projectPath]);

  const handleSubmitIdea = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectPath || !newIdea.title.trim()) return;

    setLoading(true);
    setError(null);
    try {
      await submitIdea(projectPath, newIdea);
      await loadRoadmap();
      setIsAddingIdea(false);
      setNewIdea({
        title: '',
        description: '',
        priority: 'Medium',
        section: 'future',
        position: 'bottom',
      });
    } catch (err: any) {
      setError(err.message || 'Failed to submit idea');
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const getStatusEmoji = (status: string) => {
    switch (status) {
      case 'not_started': return '🔴';
      case 'in_progress': return '🟡';
      case 'deferred': return '⚫';
      case 'completed': return '✅';
      default: return '🔴';
    }
  };

  const renderSection = (title: string, items: RoadmapItem[] | undefined) => {
    if (!items || items.length === 0) return null;
    return (
      <div className="mb-6">
        <h3 className="text-sm font-semibold text-[var(--text-secondary)] mb-3 uppercase tracking-wider">{title}</h3>
        <div className="space-y-3">
          {items.map((item, idx) => (
            <div key={idx} className="bg-[var(--bg-tertiary)] border border-[var(--border-subtle)] rounded-lg p-3">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <span>{getStatusEmoji(item.status)}</span>
                  <span className="font-medium text-[var(--text-primary)]">{item.title}</span>
                </div>
                <span className="text-xs px-2 py-1 rounded bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-secondary)]">
                  {item.priority}
                </span>
              </div>
              {item.description && (
                <p className="mt-2 text-sm text-[var(--text-muted)] whitespace-pre-wrap">{item.description}</p>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-entrance">
      <div 
        className="w-full max-w-3xl flex flex-col rounded-xl overflow-hidden border shadow-2xl"
        style={{
          background: 'var(--bg-primary)',
          borderColor: 'var(--border-subtle)',
          maxHeight: '85vh'
        }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b bg-[var(--bg-elevated)] border-[var(--border-subtle)]">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">Project Roadmap</h2>
            <span className="px-2 py-0.5 rounded text-xs font-mono text-[var(--text-muted)] border border-[var(--border-subtle)]">
              {projectName}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {!isAddingIdea && (
              <button
                onClick={() => setIsAddingIdea(true)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-hover)]"
              >
                <Plus className="w-4 h-4" />
                Submit Idea
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {error && (
            <div className="mb-6 p-4 rounded-lg bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.2)] flex items-start gap-3 text-[var(--accent-red)]">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <div className="text-sm">{error}</div>
            </div>
          )}

          {isAddingIdea ? (
            <div className="bg-[var(--bg-elevated)] border border-[var(--border-subtle)] rounded-xl p-5 mb-6">
              <h3 className="text-base font-medium text-[var(--text-primary)] mb-4">Submit a New Idea</h3>
              <form onSubmit={handleSubmitIdea} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Title</label>
                  <input
                    type="text"
                    required
                    className="w-full bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] transition-colors"
                    value={newIdea.title}
                    onChange={(e) => setNewIdea({ ...newIdea, title: e.target.value })}
                    placeholder="E.g., Implement dark mode toggle"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Description</label>
                  <textarea
                    className="w-full bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] transition-colors h-24 resize-none"
                    value={newIdea.description}
                    onChange={(e) => setNewIdea({ ...newIdea, description: e.target.value })}
                    placeholder="Provide detailed description..."
                  />
                </div>
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Priority</label>
                    <select
                      className="w-full bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] transition-colors"
                      value={newIdea.priority}
                      onChange={(e) => setNewIdea({ ...newIdea, priority: e.target.value })}
                    >
                      <option value="Low">Low</option>
                      <option value="Medium">Medium</option>
                      <option value="High">High</option>
                      <option value="Critical">Critical</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Section</label>
                    <select
                      className="w-full bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] transition-colors"
                      value={newIdea.section}
                      onChange={(e) => setNewIdea({ ...newIdea, section: e.target.value as any })}
                    >
                      <option value="current">Current Sprint</option>
                      <option value="future">Future Sprints</option>
                      <option value="deferred">Deferred</option>
                    </select>
                  </div>
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-1">Position</label>
                    <select
                      className="w-full bg-[var(--bg-primary)] border border-[var(--border-subtle)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-primary)] transition-colors"
                      value={newIdea.position}
                      onChange={(e) => setNewIdea({ ...newIdea, position: e.target.value as any })}
                    >
                      <option value="top">Top</option>
                      <option value="bottom">Bottom</option>
                    </select>
                  </div>
                </div>
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddingIdea(false)}
                    className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)] transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading || !newIdea.title.trim()}
                    className="px-4 py-2 rounded-lg text-sm font-medium bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-primary-hover)] transition-colors disabled:opacity-50"
                  >
                    {loading ? 'Submitting...' : 'Submit'}
                  </button>
                </div>
              </form>
            </div>
          ) : null}

          {loading && !isAddingIdea ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-[var(--accent-primary)] border-t-transparent" />
            </div>
          ) : roadmap ? (
            <>
              {renderSection('Current Sprint', roadmap.current_sprint)}
              {renderSection('Future Sprints', roadmap.future_sprints)}
              {renderSection('Deferred', roadmap.deferred)}
              
              {!roadmap.current_sprint?.length && !roadmap.future_sprints?.length && !roadmap.deferred?.length && (
                <div className="text-center py-12 text-[var(--text-muted)]">
                  Roadmap is empty.
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
