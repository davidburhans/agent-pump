import { useState, useEffect } from 'react';
import {
  ProjectConfig,
  ProjectBackends,
  ModelCatalog,
  BackendInstance,
} from '../types';
import {
  fetchProjectConfig,
  updateProjectConfig,
  fetchProjectBackends,
  updateProjectBackends,
  fetchModelCatalog,
  saveBackendPreset,
} from '../api';
import {
  X,
  Settings,
  Database,
  Plus,
  Trash2,
  Loader2,
  Check,
  ArrowUp,
  ArrowDown,
  Copy,
  Save,
  CheckSquare,
  Square,
  Shield,
  Zap,
} from 'lucide-react';

interface ProjectConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
  projectName: string;
}

type Tab = 'workflow' | 'verification' | 'backends';

const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'workflow', label: 'Workflow', icon: <Settings className="w-4 h-4" /> },
  { id: 'verification', label: 'Verification', icon: <Shield className="w-4 h-4" /> },
  { id: 'backends', label: 'Backend Fallbacks', icon: <Database className="w-4 h-4" /> },
];

export function ProjectConfigModal({
  isOpen,
  onClose,
  projectPath,
  projectName,
}: ProjectConfigModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>('workflow');
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog>({ backends: {} });
  const [config, setConfig] = useState<ProjectConfig>({
    backend: 'gemini',
    workflow: { maxIterations: 10, timeout: 1800, branch: null },
    verification: {
      buildCmd: null,
      lintCmd: null,
      testCmd: null,
      coverageCmd: null,
      coverageThreshold: 0,
      skipVerification: false,
      sandboxImage: null,
    },
  });
  const [backends, setBackends] = useState<ProjectBackends>({
    defaultChain: null,
    phaseBackends: {
      defaults: { backends: [] },
      planning: { backends: [] },
      implementing: { backends: [] },
      verifying: { backends: [] },
      brainstorming: { backends: [] },
      committing: { backends: [] },
    },
    presets: [],
  });

  const [activePhase, setActivePhase] = useState<string>('defaults');
  const [presetName, setPresetName] = useState<string>('');
  const [copySourcePhase, setCopySourcePhase] = useState<string>('');
  const [copySourcePreset, setCopySourcePreset] = useState<string>('');

  const [isLoading, setIsLoading] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && projectPath) {
      loadData();
    }
  }, [isOpen, projectPath]);

  async function loadData() {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const [cfg, bks, cat] = await Promise.all([
        fetchProjectConfig(projectPath),
        fetchProjectBackends(projectPath),
        fetchModelCatalog(),
      ]);
      setConfig(cfg);
      setBackends(bks);
      setModelCatalog(cat);
    } catch (e: any) {
      console.error('Failed to load project details:', e);
      setErrorMsg(e.message || 'Failed to load project configuration details.');
    } finally {
      setIsLoading(false);
    }
  }

  async function handleSave() {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      await Promise.all([
        updateProjectConfig(projectPath, config),
        updateProjectBackends(projectPath, backends),
      ]);
      setIsSaved(true);
      setTimeout(() => {
        setIsSaved(false);
        onClose();
      }, 800);
    } catch (e: any) {
      console.error('Failed to save settings:', e);
      setErrorMsg(e.message || 'Failed to save configuration updates.');
    } finally {
      setIsLoading(false);
    }
  }

  function handleAddBackendInstance(phase: string) {
    const defaultInstance: BackendInstance = {
      name: 'gemini',
      args: [],
      timeout: null,
      concurrencyLimit: 1,
    };

    setBackends((prev) => {
      if (phase === 'defaultChain') {
        const currentChain = prev.defaultChain || { backends: [] };
        return {
          ...prev,
          defaultChain: {
            backends: [...currentChain.backends, defaultInstance],
          },
        };
      } else {
        const phases = { ...prev.phaseBackends };
        const key = phase as keyof typeof prev.phaseBackends;
        phases[key] = {
          backends: [...phases[key].backends, defaultInstance],
        };
        return { ...prev, phaseBackends: phases };
      }
    });
  }

  function handleRemoveBackendInstance(phase: string, index: number) {
    setBackends((prev) => {
      if (phase === 'defaultChain') {
        if (!prev.defaultChain) return prev;
        return {
          ...prev,
          defaultChain: {
            backends: prev.defaultChain.backends.filter((_, i) => i !== index),
          },
        };
      } else {
        const phases = { ...prev.phaseBackends };
        const key = phase as keyof typeof prev.phaseBackends;
        phases[key] = {
          backends: phases[key].backends.filter((_, i) => i !== index),
        };
        return { ...prev, phaseBackends: phases };
      }
    });
  }

  function handleUpdateBackendField<K extends keyof BackendInstance>(
    phase: string,
    index: number,
    field: K,
    value: BackendInstance[K]
  ) {
    setBackends((prev) => {
      const updateList = (list: BackendInstance[]) =>
        list.map((b, i) => (i === index ? { ...b, [field]: value } : b));

      if (phase === 'defaultChain') {
        if (!prev.defaultChain) return prev;
        return {
          ...prev,
          defaultChain: {
            backends: updateList(prev.defaultChain.backends),
          },
        };
      } else {
        const phases = { ...prev.phaseBackends };
        const key = phase as keyof typeof prev.phaseBackends;
        phases[key] = {
          backends: updateList(phases[key].backends),
        };
        return { ...prev, phaseBackends: phases };
      }
    });
  }

  function moveBackendInstance(phase: string, index: number, direction: 'up' | 'down') {
    setBackends((prev) => {
      const move = (list: BackendInstance[]) => {
        const targetIdx = direction === 'up' ? index - 1 : index + 1;
        if (targetIdx < 0 || targetIdx >= list.length) return list;
        const copy = [...list];
        const temp = copy[index];
        copy[index] = copy[targetIdx];
        copy[targetIdx] = temp;
        return copy;
      };

      if (phase === 'defaultChain') {
        if (!prev.defaultChain) return prev;
        return {
          ...prev,
          defaultChain: {
            backends: move(prev.defaultChain.backends),
          },
        };
      } else {
        const phases = { ...prev.phaseBackends };
        const key = phase as keyof typeof prev.phaseBackends;
        phases[key] = {
          backends: move(phases[key].backends),
        };
        return { ...prev, phaseBackends: phases };
      }
    });
  }

  function handleInheritToggle(phase: string, checked: boolean) {
    setBackends((prev) => {
      const phases = { ...prev.phaseBackends };
      const key = phase as keyof typeof prev.phaseBackends;
      if (checked) {
        // Inherited is represented by having an empty list of backends
        phases[key] = { backends: [] };
      } else {
        // Copy the default chain to start customizing
        const defaults = prev.defaultChain?.backends || prev.phaseBackends.defaults?.backends || [];
        phases[key] = { backends: JSON.parse(JSON.stringify(defaults)) };
      }
      return { ...prev, phaseBackends: phases };
    });
  }

  async function handleSavePreset() {
    if (!presetName.trim()) return;
    setIsLoading(true);
    try {
      const activeChain =
        activePhase === 'defaultChain'
          ? backends.defaultChain
          : backends.phaseBackends[activePhase as keyof typeof backends.phaseBackends];

      if (!activeChain || activeChain.backends.length === 0) {
        alert('Cannot save an empty fallback chain as preset');
        return;
      }

      const preset = await saveBackendPreset({
        name: presetName.trim(),
        backends: activeChain,
      });

      setBackends((prev) => ({
        ...prev,
        presets: [...prev.presets, preset],
      }));
      setPresetName('');
    } catch (e: any) {
      alert(`Failed to save preset: ${e.message}`);
    } finally {
      setIsLoading(false);
    }
  }

  function handleCopyFromPhase() {
    if (!copySourcePhase) return;
    const sourceChain =
      copySourcePhase === 'defaultChain'
        ? backends.defaultChain
        : backends.phaseBackends[copySourcePhase as keyof typeof backends.phaseBackends];

    if (!sourceChain) return;

    setBackends((prev) => {
      const copyOfChain = JSON.parse(JSON.stringify(sourceChain));
      if (activePhase === 'defaultChain') {
        return { ...prev, defaultChain: copyOfChain };
      } else {
        const phases = { ...prev.phaseBackends };
        phases[activePhase as keyof typeof prev.phaseBackends] = copyOfChain;
        return { ...prev, phaseBackends: phases };
      }
    });
    setCopySourcePhase('');
  }

  function handleCopyFromPreset() {
    if (!copySourcePreset) return;
    const preset = backends.presets.find((p) => p.name === copySourcePreset);
    if (!preset) return;

    setBackends((prev) => {
      const copyOfChain = JSON.parse(JSON.stringify(preset.backends));
      if (activePhase === 'defaultChain') {
        return { ...prev, defaultChain: copyOfChain };
      } else {
        const phases = { ...prev.phaseBackends };
        phases[activePhase as keyof typeof prev.phaseBackends] = copyOfChain;
        return { ...prev, phaseBackends: phases };
      }
    });
    setCopySourcePreset('');
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
      style={{ background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-4xl max-h-[90vh] flex flex-col rounded-2xl animate-scale-in"
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
              <Settings className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                Config: {projectName}
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

        {/* Tabs */}
        <div className="flex gap-1 p-2 mx-6 mt-4 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-200"
              style={{
                background: activeTab === tab.id ? 'var(--bg-elevated)' : 'transparent',
                color: activeTab === tab.id ? 'var(--accent-primary)' : 'var(--text-secondary)',
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Error banner */}
        {errorMsg && (
          <div className="mx-6 mt-4 p-4 rounded-xl border border-red-500/20 bg-red-500/5 text-red-400 text-sm flex gap-2">
            <span className="font-semibold">Error:</span> {errorMsg}
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 min-h-0">
          {isLoading && (
            <div className="flex flex-col items-center justify-center py-24 gap-4">
              <Loader2 className="w-10 h-10 animate-spin text-blue-400" />
              <p className="text-sm font-mono text-gray-400">Loading configuration...</p>
            </div>
          )}

          {!isLoading && activeTab === 'workflow' && (
            <div className="space-y-6">
              <div className="p-6 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
                <div className="flex items-center gap-3 mb-6">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ background: 'rgba(91, 141, 239, 0.12)' }}
                  >
                    <Zap className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                  </div>
                  <div>
                    <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                      Core AI Preferences
                    </p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      AI settings registered in .agent-pump/config.yml
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Main AI Backend
                    </label>
                    <select
                      value={config.backend}
                      onChange={(e) => setConfig((prev) => ({ ...prev, backend: e.target.value }))}
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    >
                      <option value="gemini">Gemini</option>
                      <option value="claude">Claude</option>
                      <option value="opencode">OpenCode (Local)</option>
                      <option value="qwen">Qwen</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Git Branch Override (Legacy)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. main (blank for auto)"
                      value={config.workflow.branch || ''}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          workflow: {
                            ...prev.workflow,
                            branch: e.target.value || null,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Max Autonomous Iterations
                    </label>
                    <input
                      type="number"
                      value={config.workflow.maxIterations}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          workflow: {
                            ...prev.workflow,
                            maxIterations: parseInt(e.target.value) || 0,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Operation Timeout (Seconds)
                    </label>
                    <input
                      type="number"
                      value={config.workflow.timeout}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          workflow: {
                            ...prev.workflow,
                            timeout: parseInt(e.target.value) || 0,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {!isLoading && activeTab === 'verification' && (
            <div className="space-y-6">
              <div className="p-6 rounded-xl" style={{ background: 'var(--bg-tertiary)' }}>
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ background: 'rgba(91, 141, 239, 0.12)' }}
                    >
                      <Shield className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                    </div>
                    <div>
                      <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                        Quality & Verification
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Configure the strict verification rules (build, lint, test)
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      setConfig((prev) => ({
                        ...prev,
                        verification: {
                          ...prev.verification,
                          skipVerification: !prev.verification.skipVerification,
                        },
                      }))
                    }
                    className="flex items-center gap-2 text-sm font-medium transition-all"
                    style={{
                      color: config.verification.skipVerification
                        ? 'var(--accent-red)'
                        : 'var(--text-muted)',
                    }}
                  >
                    {config.verification.skipVerification ? (
                      <CheckSquare className="w-5 h-5 text-red-500 animate-pulse" />
                    ) : (
                      <Square className="w-5 h-5 text-gray-500" />
                    )}
                    Skip Verification Entirely
                  </button>
                </div>

                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Build Command
                    </label>
                    <input
                      type="text"
                      disabled={config.verification.skipVerification}
                      placeholder="e.g. npm run build, cargo build (blank to skip)"
                      value={config.verification.buildCmd || ''}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          verification: {
                            ...prev.verification,
                            buildCmd: e.target.value || null,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono disabled:opacity-50"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Lint Command
                    </label>
                    <input
                      type="text"
                      disabled={config.verification.skipVerification}
                      placeholder="e.g. npm run lint, ruff check . (blank to skip)"
                      value={config.verification.lintCmd || ''}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          verification: {
                            ...prev.verification,
                            lintCmd: e.target.value || null,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono disabled:opacity-50"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Test Command
                    </label>
                    <input
                      type="text"
                      disabled={config.verification.skipVerification}
                      placeholder="e.g. npm test, pytest (blank to skip)"
                      value={config.verification.testCmd || ''}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          verification: {
                            ...prev.verification,
                            testCmd: e.target.value || null,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono disabled:opacity-50"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                        Coverage Command
                      </label>
                      <input
                        type="text"
                        disabled={config.verification.skipVerification}
                        placeholder="e.g. pytest --cov (blank to skip)"
                        value={config.verification.coverageCmd || ''}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            verification: {
                              ...prev.verification,
                              coverageCmd: e.target.value || null,
                            },
                          }))
                        }
                        className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono disabled:opacity-50"
                        style={{
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                        Min Coverage Threshold (%)
                      </label>
                      <input
                        type="number"
                        disabled={config.verification.skipVerification}
                        value={config.verification.coverageThreshold}
                        onChange={(e) =>
                          setConfig((prev) => ({
                            ...prev,
                            verification: {
                              ...prev.verification,
                              coverageThreshold: parseFloat(e.target.value) || 0,
                            },
                          }))
                        }
                        className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono disabled:opacity-50"
                        style={{
                          background: 'var(--bg-primary)',
                          border: '1px solid var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-muted)' }}>
                      Docker Sandbox Image (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. node:18-slim, python:3.11-slim (blank for host execution)"
                      value={config.verification.sandboxImage || ''}
                      onChange={(e) =>
                        setConfig((prev) => ({
                          ...prev,
                          verification: {
                            ...prev.verification,
                            sandboxImage: e.target.value || null,
                          },
                        }))
                      }
                      className="w-full px-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none font-mono"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {!isLoading && activeTab === 'backends' && (
            <div className="flex gap-6 h-full min-h-0 flex-col md:flex-row">
              {/* Left Column: Phase Selector */}
              <div className="w-full md:w-56 flex flex-col gap-1 rounded-xl p-2 h-fit" style={{ background: 'var(--bg-tertiary)' }}>
                <p className="text-[10px] font-semibold uppercase tracking-wider px-3 py-2" style={{ color: 'var(--text-muted)' }}>
                  Chain Categories
                </p>
                {[
                  { id: 'defaultChain', label: 'Default Chain' },
                  { id: 'defaults', label: 'Workspace Defaults' },
                  { id: 'planning', label: 'Planning' },
                  { id: 'implementing', label: 'Implementing' },
                  { id: 'verifying', label: 'Verifying' },
                  { id: 'brainstorming', label: 'Brainstorming' },
                  { id: 'committing', label: 'Committing' },
                ].map((phase) => (
                  <button
                    key={phase.id}
                    onClick={() => setActivePhase(phase.id)}
                    className="px-3 py-2.5 rounded-lg text-left text-sm font-medium transition-all duration-200"
                    style={{
                      background: activePhase === phase.id ? 'var(--bg-elevated)' : 'transparent',
                      color: activePhase === phase.id ? 'var(--accent-primary)' : 'var(--text-secondary)',
                    }}
                  >
                    {phase.label}
                  </button>
                ))}
              </div>

              {/* Right Column: Chain Editor */}
              <div className="flex-1 flex flex-col gap-4 min-h-0 overflow-y-auto">
                <div className="p-5 rounded-xl flex-1 flex flex-col" style={{ background: 'var(--bg-tertiary)' }}>
                  <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
                    <div>
                      <h4 className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>
                        {activePhase === 'defaultChain' ? 'Default Fallback Chain' : `Fallback Chain: ${activePhase}`}
                      </h4>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Define the ordered list of LLMs to attempt for this category
                      </p>
                    </div>

                    {activePhase !== 'defaultChain' && activePhase !== 'defaults' && (
                      <button
                        onClick={() => {
                          const list = backends.phaseBackends[activePhase as keyof typeof backends.phaseBackends]?.backends;
                          const isInherited = !list || list.length === 0;
                          handleInheritToggle(activePhase, !isInherited);
                        }}
                        className="flex items-center gap-2 text-xs font-semibold transition-all"
                        style={{
                          color:
                            backends.phaseBackends[activePhase as keyof typeof backends.phaseBackends]?.backends?.length === 0
                              ? 'var(--accent-primary)'
                              : 'var(--text-muted)',
                        }}
                      >
                        {backends.phaseBackends[activePhase as keyof typeof backends.phaseBackends]?.backends?.length === 0 ? (
                          <CheckSquare className="w-4 h-4 text-blue-500" />
                        ) : (
                          <Square className="w-4 h-4 text-gray-500" />
                        )}
                        Use Project Default Chain
                      </button>
                    )}
                  </div>

                  {/* Active List of Fallbacks */}
                  {(() => {
                    const activeFallback =
                      activePhase === 'defaultChain'
                        ? backends.defaultChain
                        : backends.phaseBackends[activePhase as keyof typeof backends.phaseBackends];

                    const isInherited =
                      activePhase !== 'defaultChain' &&
                      activePhase !== 'defaults' &&
                      (!activeFallback || activeFallback.backends.length === 0);

                    if (isInherited) {
                      return (
                        <div className="flex-1 flex flex-col items-center justify-center py-12 border border-dashed rounded-xl" style={{ borderColor: 'var(--border-subtle)' }}>
                          <Database className="w-10 h-10 text-gray-600 mb-2" />
                          <p className="text-xs italic" style={{ color: 'var(--text-muted)' }}>
                            Inheriting fallbacks from the Project Default Chain.
                          </p>
                        </div>
                      );
                    }

                    const list = activeFallback?.backends || [];

                    return (
                      <div className="flex-1 flex flex-col gap-3 min-h-0 overflow-y-auto mb-4">
                        {list.map((backend, idx) => (
                          <div
                            key={idx}
                            className="p-4 rounded-lg flex flex-col md:flex-row gap-3 items-center border"
                            style={{
                              background: 'var(--bg-primary)',
                              borderColor: 'var(--border-subtle)',
                            }}
                          >
                            {/* Reordering indicators */}
                            <div className="flex flex-row md:flex-col gap-1">
                              <button
                                disabled={idx === 0}
                                onClick={() => moveBackendInstance(activePhase, idx, 'up')}
                                className="p-1 rounded transition hover:bg-slate-800 disabled:opacity-30"
                              >
                                <ArrowUp className="w-4 h-4" />
                              </button>
                              <button
                                disabled={idx === list.length - 1}
                                onClick={() => moveBackendInstance(activePhase, idx, 'down')}
                                className="p-1 rounded transition hover:bg-slate-800 disabled:opacity-30"
                              >
                                <ArrowDown className="w-4 h-4" />
                              </button>
                            </div>

                            {/* Backend Selection */}
                            <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-3 gap-3 w-full">
                              <div>
                                <label className="block text-[10px] uppercase font-semibold text-gray-500 mb-1">
                                  Provider
                                </label>
                                <select
                                  value={backend.name}
                                  onChange={(e) =>
                                    handleUpdateBackendField(activePhase, idx, 'name', e.target.value)
                                  }
                                  className="w-full px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 text-xs text-white"
                                >
                                  {Object.keys(modelCatalog.backends).map((b) => (
                                    <option key={b} value={b}>
                                      {b}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div>
                                <label className="block text-[10px] uppercase font-semibold text-gray-500 mb-1">
                                  Model (Catalog)
                                </label>
                                <select
                                  value={
                                    backend.args.find((a) => a.startsWith('--model'))?.split(' ')[1] ||
                                    backend.args[backend.args.indexOf('--model') + 1] ||
                                    ''
                                  }
                                  onChange={(e) => {
                                    const modelVal = e.target.value;
                                    let newArgs = [...backend.args];
                                    const mIdx = newArgs.indexOf('--model');
                                    if (mIdx !== -1) {
                                      newArgs[mIdx + 1] = modelVal;
                                    } else {
                                      newArgs.push('--model', modelVal);
                                    }
                                    handleUpdateBackendField(activePhase, idx, 'args', newArgs);
                                  }}
                                  className="w-full px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 text-xs text-white"
                                >
                                  <option value="">(Default)</option>
                                  {(modelCatalog.backends[backend.name] || []).map((m) => (
                                    <option key={m} value={m}>
                                      {m}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div>
                                <label className="block text-[10px] uppercase font-semibold text-gray-500 mb-1">
                                  Extra Arguments
                                </label>
                                <input
                                  type="text"
                                  placeholder="e.g. --temperature 0.7"
                                  value={backend.args.filter((a) => a !== '--model' && !backend.args[backend.args.indexOf(a) - 1]?.includes('--model')).join(' ')}
                                  onChange={(e) => {
                                    const input = e.target.value;
                                    const modelIdx = backend.args.indexOf('--model');
                                    const currentModel = modelIdx !== -1 ? backend.args[modelIdx + 1] : null;
                                    let newArgs: string[] = [];
                                    if (currentModel) {
                                      newArgs.push('--model', currentModel);
                                    }
                                    if (input.trim()) {
                                      newArgs = [...newArgs, ...input.split(/\s+/)];
                                    }
                                    handleUpdateBackendField(activePhase, idx, 'args', newArgs);
                                  }}
                                  className="w-full px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 text-xs text-white font-mono"
                                />
                              </div>
                            </div>

                            {/* Remove button */}
                            <button
                              onClick={() => handleRemoveBackendInstance(activePhase, idx)}
                              className="p-2 rounded text-red-400 transition hover:bg-red-500/10 hover:text-red-300"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        ))}

                        <button
                          onClick={() => handleAddBackendInstance(activePhase)}
                          className="flex items-center justify-center gap-2 py-3 rounded-lg border border-dashed text-sm font-semibold transition hover:bg-slate-800/20"
                          style={{
                            borderColor: 'var(--border-subtle)',
                            color: 'var(--accent-primary)',
                          }}
                        >
                          <Plus className="w-4 h-4" />
                          Add Fallback Backend
                        </button>
                      </div>
                    );
                  })()}

                  {/* Preset & Copy Toolbar */}
                  <div
                    className="mt-auto border-t pt-4 grid grid-cols-1 sm:grid-cols-2 gap-4"
                    style={{ borderColor: 'var(--border-subtle)' }}
                  >
                    {/* Copy Config tools */}
                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase text-gray-500">
                        Copy Configuration
                      </p>
                      <div className="flex gap-2">
                        <select
                          value={copySourcePhase}
                          onChange={(e) => setCopySourcePhase(e.target.value)}
                          className="flex-1 px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 text-xs text-white"
                        >
                          <option value="">Copy Phase...</option>
                          <option value="defaultChain">Default Chain</option>
                          <option value="planning">Planning</option>
                          <option value="implementing">Implementing</option>
                          <option value="verifying">Verifying</option>
                          <option value="brainstorming">Brainstorming</option>
                          <option value="committing">Committing</option>
                        </select>
                        <button
                          disabled={!copySourcePhase}
                          onClick={handleCopyFromPhase}
                          className="px-3 py-1.5 rounded text-xs font-semibold bg-neutral-800 text-white hover:bg-neutral-700 transition"
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {backends.presets.length > 0 && (
                        <div className="flex gap-2">
                          <select
                            value={copySourcePreset}
                            onChange={(e) => setCopySourcePreset(e.target.value)}
                            className="flex-1 px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 text-xs text-white"
                          >
                            <option value="">Copy Preset...</option>
                            {backends.presets.map((preset) => (
                              <option key={preset.name} value={preset.name}>
                                {preset.name}
                              </option>
                            ))}
                          </select>
                          <button
                            disabled={!copySourcePreset}
                            onClick={handleCopyFromPreset}
                            className="px-3 py-1.5 rounded text-xs font-semibold bg-neutral-800 text-white hover:bg-neutral-700 transition"
                          >
                            <Copy className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Preset Saving tool */}
                    <div className="space-y-2">
                      <p className="text-[10px] font-semibold uppercase text-gray-500 font-display">
                        Save Current Chain as Preset
                      </p>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder="Preset name (e.g. local-fast)"
                          value={presetName}
                          onChange={(e) => setPresetName(e.target.value)}
                          className="flex-1 px-3 py-1.5 rounded bg-neutral-900 border border-neutral-800 text-xs text-white outline-none"
                        />
                        <button
                          disabled={!presetName.trim()}
                          onClick={handleSavePreset}
                          className="flex items-center gap-1 px-4 py-1.5 rounded text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 disabled:opacity-40 transition"
                        >
                          <Save className="w-3.5 h-3.5" />
                          Save
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-end gap-3 p-6 border-t"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}
        >
          <button
            onClick={onClose}
            className="px-5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = 'var(--bg-elevated)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'var(--bg-tertiary)';
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isLoading || isSaved}
            className="flex items-center gap-2 px-6 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200"
            style={{
              background: isSaved
                ? 'var(--accent-green)'
                : 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              color: 'white',
              opacity: isLoading ? 0.7 : 1,
              boxShadow: isSaved ? 'none' : 'var(--glow-primary)',
            }}
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Saving...
              </>
            ) : isSaved ? (
              <>
                <Check className="w-4 h-4" />
                Saved!
              </>
            ) : (
              'Save Changes'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
