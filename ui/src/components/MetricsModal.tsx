import { useState, useEffect } from 'react';
import { ProjectMetricsDTO } from '../types';
import { fetchProjectMetrics } from '../api';
import {
  X,
  BarChart2,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  List,
  Target
} from 'lucide-react';


interface MetricsModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
  projectName: string;
}

function formatDuration(seconds: number): string {
  if (!seconds) return '0s';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

function formatPercentage(rate: number): string {
  return `${(rate * 100).toFixed(1)}%`;
}

export function MetricsModal({ isOpen, onClose, projectPath, projectName }: MetricsModalProps) {
  const [metrics, setMetrics] = useState<ProjectMetricsDTO | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && projectPath) {
      loadMetrics();
    } else {
      setMetrics(null);
      setErrorMsg(null);
    }
  }, [isOpen, projectPath]);

  async function loadMetrics() {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const data = await fetchProjectMetrics(projectPath);
      setMetrics(data);
    } catch (e: any) {
      console.error('Failed to load metrics:', e);
      setErrorMsg(e.message || 'Failed to load project metrics.');
    } finally {
      setIsLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
      style={{ background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-5xl max-h-[90vh] flex flex-col rounded-2xl animate-scale-in"
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-subtle)',
          boxShadow: '0 30px 60px -15px rgba(0, 0, 0, 0.6)',
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between p-6 border-b"
          style={{ borderColor: 'var(--border-subtle)' }}
        >
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{
                background:
                  'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              }}
            >
              <BarChart2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                Metrics: {projectName}
              </h2>
              <p
                className="text-xs mt-0.5 font-mono truncate max-w-lg"
                style={{ color: 'var(--text-muted)' }}
              >
                {projectPath}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-elevated)';
              e.currentTarget.style.color = 'var(--accent-red)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--bg-tertiary)';
              e.currentTarget.style.color = 'var(--text-secondary)';
            }}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 min-h-0">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
              <Loader2 className="w-10 h-10 animate-spin text-blue-400" />
              <p className="text-sm font-mono text-gray-400">Loading metrics...</p>
            </div>
          )}

          {errorMsg && (
            <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 text-sm flex gap-2">
              <span className="font-semibold">Error:</span> {errorMsg}
            </div>
          )}

          {!isLoading && metrics && (
            <div className="space-y-6">
              {/* Top Stats Row */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  icon={<List className="w-5 h-5 text-blue-400" />}
                  label="Total Features"
                  value={metrics.total_features}
                />
                <StatCard
                  icon={<CheckCircle2 className="w-5 h-5 text-green-400" />}
                  label="Successful"
                  value={metrics.successful_features}
                />
                <StatCard
                  icon={<XCircle className="w-5 h-5 text-red-400" />}
                  label="Failed"
                  value={metrics.failed_features}
                />
                <StatCard
                  icon={<Target className="w-5 h-5 text-purple-400" />}
                  label="Verification Success"
                  value={formatPercentage(metrics.verification_success_rate)}
                />
              </div>

              {/* Phase Durations & Avg Time */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-5 rounded-xl border" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--border-subtle)' }}>
                  <div className="flex items-center gap-2 mb-4">
                    <Clock className="w-4 h-4 text-[var(--accent-primary)]" />
                    <h3 className="font-semibold text-sm">Average Duration</h3>
                  </div>
                  <p className="text-3xl font-light tracking-tight mb-2">
                    {formatDuration(metrics.average_duration_seconds)}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">Per completed feature</p>
                </div>

                <div className="p-5 rounded-xl border" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--border-subtle)' }}>
                  <div className="flex items-center gap-2 mb-4">
                    <Activity className="w-4 h-4 text-[var(--accent-primary)]" />
                    <h3 className="font-semibold text-sm">Phase Durations (Avg)</h3>
                  </div>
                  <div className="space-y-3 max-h-32 overflow-y-auto pr-2">
                    {Object.entries(metrics.phase_durations).length === 0 ? (
                      <p className="text-xs text-[var(--text-muted)]">No phase data available</p>
                    ) : (
                      Object.entries(metrics.phase_durations).map(([phase, duration]) => (
                        <div key={phase} className="flex items-center justify-between text-sm">
                          <span className="capitalize text-[var(--text-secondary)]">{phase}</span>
                          <span className="font-mono text-[var(--text-primary)]">{formatDuration(duration)}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Features List */}
              <div className="mt-8">
                <h3 className="font-semibold text-sm mb-4 px-1" style={{ color: 'var(--text-primary)' }}>Feature History</h3>
                <div className="space-y-3">
                  {metrics.features.length === 0 ? (
                    <div className="p-8 text-center border rounded-xl border-dashed" style={{ borderColor: 'var(--border-subtle)' }}>
                      <p className="text-sm text-[var(--text-muted)]">No feature completions recorded yet.</p>
                    </div>
                  ) : (
                    metrics.features.map((feature, idx) => (
                      <div
                        key={idx}
                        className="p-4 rounded-xl border flex flex-col md:flex-row gap-4 justify-between items-start md:items-center"
                        style={{ background: 'var(--bg-primary)', borderColor: 'var(--border-subtle)' }}
                      >
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            {feature.success ? (
                              <CheckCircle2 className="w-4 h-4 text-green-500" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-500" />
                            )}
                            <h4 className="font-semibold text-sm">{feature.name}</h4>
                          </div>
                          <div className="text-xs text-[var(--text-muted)] font-mono flex items-center gap-3">
                            <span>Started: {new Date(feature.started_at).toLocaleString()}</span>
                            <span>Iters: {feature.iterations}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 text-xs">
                          <div className="flex flex-col items-end">
                            <span className="text-[var(--text-muted)] mb-0.5">Duration</span>
                            <span className="font-mono">{formatDuration(feature.total_duration_seconds)}</span>
                          </div>
                          <div className="flex flex-col items-end">
                            <span className="text-[var(--text-muted)] mb-0.5">Verification</span>
                            <span className="font-mono text-purple-400">{formatPercentage(feature.verification_success_rate)}</span>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
  return (
    <div className="p-4 rounded-xl border flex flex-col" style={{ background: 'var(--bg-tertiary)', borderColor: 'var(--border-subtle)' }}>
      <div className="flex items-center gap-2 mb-2 text-sm text-[var(--text-secondary)]">
        {icon}
        <span className="font-medium truncate">{label}</span>
      </div>
      <div className="text-2xl font-semibold mt-auto" style={{ color: 'var(--text-primary)' }}>
        {value}
      </div>
    </div>
  );
}
