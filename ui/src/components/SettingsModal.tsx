import { useState, useEffect } from 'react';
import { ModelCatalog } from '../types';
import { fetchModelCatalog, updateModelCatalog } from '../api';
import { X, Settings, Database, Plus, Trash2, Loader2, Check } from 'lucide-react';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'general' | 'model-catalog';

const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: 'general', label: 'General', icon: <Settings className="w-4 h-4" /> },
  { id: 'model-catalog', label: 'Model Catalog', icon: <Database className="w-4 h-4" /> },
];

interface ToggleProps {
  enabled: boolean;
  onToggle: () => void;
}

function Toggle({ enabled, onToggle }: ToggleProps) {
  return (
    <button
      onClick={onToggle}
      className="w-12 h-6 rounded-full transition-all duration-200 relative"
      style={{
        background: enabled ? 'var(--accent-primary)' : 'var(--bg-elevated)',
        boxShadow: enabled ? '0 0 15px rgba(91, 141, 239, 0.4)' : 'inset 0 2px 4px rgba(0,0,0,0.3)'
      }}
    >
      <span
        className="absolute top-1 w-4 h-4 rounded-full transition-all duration-200"
        style={{
          background: enabled ? 'white' : 'var(--text-muted)',
          left: enabled ? '20px' : '4px',
          boxShadow: enabled ? '0 2px 6px rgba(0,0,0,0.3)' : '0 1px 2px rgba(0,0,0,0.2)'
        }}
      />
    </button>
  );
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const [modelCatalog, setModelCatalog] = useState<ModelCatalog>({ backends: {} });
  const [newModels, setNewModels] = useState<Record<string, string>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadModelCatalog();
    }
  }, [isOpen]);

  async function loadModelCatalog() {
    try {
      const catalog = await fetchModelCatalog();
      setModelCatalog(catalog);
    } catch (e) {
      console.error('Failed to load model catalog:', e);
    }
  }

  async function handleSave() {
    setIsLoading(true);
    try {
      await updateModelCatalog(modelCatalog);
      setIsSaved(true);
      setTimeout(() => {
        setIsSaved(false);
        onClose();
      }, 800);
    } catch (e) {
      console.error('Failed to save settings:', e);
    } finally {
      setIsLoading(false);
    }
  }

  function handleRemoveModel(backend: string, model: string) {
    setModelCatalog(prev => ({
      ...prev,
      backends: {
        ...prev.backends,
        [backend]: prev.backends[backend].filter(m => m !== model),
      },
    }));
  }

  function handleAddModel(backend: string) {
    const model = newModels[backend]?.trim();
    if (!model) return;

    setModelCatalog(prev => ({
      ...prev,
      backends: {
        ...prev.backends,
        [backend]: [...(prev.backends[backend] || []), model],
      },
    }));
    setNewModels(prev => ({ ...prev, [backend]: '' }));
  }

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in"
      style={{ background: 'rgba(0, 0, 0, 0.75)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] flex flex-col rounded-2xl animate-scale-in"
        style={{
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-subtle)',
          boxShadow: '0 30px 60px -15px rgba(0, 0, 0, 0.6)'
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
              style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))' }}
            >
              <Settings className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                Settings
              </h2>
              <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
                Configure your agent preferences
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl flex items-center justify-center transition-all duration-200"
            style={{
              background: 'var(--bg-tertiary)',
              color: 'var(--text-secondary)'
            }}
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
        <div
          className="flex gap-1 p-2 mx-6 mt-4 rounded-xl"
          style={{ background: 'var(--bg-tertiary)' }}
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium text-sm transition-all duration-200"
              style={{
                background: activeTab === tab.id ? 'var(--bg-elevated)' : 'transparent',
                color: activeTab === tab.id ? 'var(--accent-primary)' : 'var(--text-secondary)'
              }}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === 'general' && (
            <div className="space-y-6 stagger-children">
              <div
                className="p-6 rounded-xl"
                style={{ background: 'var(--bg-tertiary)' }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ background: 'rgba(139, 92, 246, 0.12)' }}
                  >
                    <Settings className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                  </div>
                  <div>
                    <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                      General Settings
                    </p>
                    <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                      Core application preferences
                    </p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="flex items-center justify-between py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                        Auto-scroll logs
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Automatically scroll to latest log entry
                      </p>
                    </div>
                    <Toggle enabled={autoScrollEnabled} onToggle={() => setAutoScrollEnabled(!autoScrollEnabled)} />
                  </div>

                  <div className="flex items-center justify-between py-3 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                        Notifications
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Desktop notifications for state changes
                      </p>
                    </div>
                    <Toggle enabled={notificationsEnabled} onToggle={() => setNotificationsEnabled(!notificationsEnabled)} />
                  </div>

                  <div className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                        Theme
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        Application color scheme
                      </p>
                    </div>
                    <span
                      className="px-3 py-1.5 rounded-lg text-xs font-medium"
                      style={{
                        background: 'rgba(91, 141, 239, 0.1)',
                        color: 'var(--accent-primary)'
                      }}
                    >
                      Dark
                    </span>
                  </div>
                </div>
              </div>

              <div
                className="p-6 rounded-xl border"
                style={{
                  background: 'var(--bg-tertiary)',
                  borderColor: 'var(--border-subtle)'
                }}
              >
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
                  Additional general settings coming soon.
                </p>
              </div>
            </div>
          )}

          {activeTab === 'model-catalog' && (
            <div className="space-y-4">
              {Object.entries(modelCatalog.backends).map(([backend, models]) => (
                <div
                  key={backend}
                  className="p-5 rounded-xl"
                  style={{ background: 'var(--bg-tertiary)' }}
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center"
                      style={{ background: 'rgba(139, 92, 246, 0.12)' }}
                    >
                      <Database className="w-5 h-5" style={{ color: 'var(--accent-primary)' }} />
                    </div>
                    <div className="flex-1">
                      <p className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                        {backend}
                      </p>
                      <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                        {models.length} {models.length === 1 ? 'model' : 'models'} configured
                      </p>
                    </div>
                  </div>

                  {/* Existing models */}
                  <div className="flex flex-wrap gap-2 mb-4">
                    {models.map(model => (
                      <span
                        key={model}
                        className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm group transition-all duration-200"
                        style={{
                          background: 'var(--bg-elevated)',
                          color: 'var(--text-secondary)'
                        }}
                      >
                        <span className="font-mono">{model}</span>
                        <button
                          onClick={() => handleRemoveModel(backend, model)}
                          className="w-5 h-5 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                          style={{ background: 'rgba(244, 63, 94, 0.15)', color: 'var(--accent-red)' }}
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>

                  {/* Add new model */}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newModels[backend] || ''}
                      onChange={e => setNewModels(prev => ({ ...prev, [backend]: e.target.value }))}
                      onKeyDown={e => e.key === 'Enter' && handleAddModel(backend)}
                      placeholder={`Add ${backend} model...`}
                      className="flex-1 px-4 py-2.5 rounded-lg text-sm font-mono transition-all duration-200"
                      style={{
                        background: 'var(--bg-primary)',
                        border: '1px solid var(--border-subtle)',
                        color: 'var(--text-primary)',
                        outline: 'none'
                      }}
                      onFocus={(e) => {
                        e.currentTarget.style.borderColor = 'var(--accent-primary)';
                        e.currentTarget.style.boxShadow = '0 0 0 3px var(--accent-primary-glow)';
                      }}
                      onBlur={(e) => {
                        e.currentTarget.style.borderColor = 'var(--border-subtle)';
                        e.currentTarget.style.boxShadow = 'none';
                      }}
                    />
                    <button
                      onClick={() => handleAddModel(backend)}
                      className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200"
                      style={{
                        background: 'rgba(91, 141, 239, 0.1)',
                        color: 'var(--accent-primary)'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(91, 141, 239, 0.18)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(91, 141, 239, 0.1)';
                      }}
                    >
                      <Plus className="w-4 h-4" />
                      Add
                    </button>
                  </div>
                </div>
              ))}

              {Object.keys(modelCatalog.backends).length === 0 && (
                <div
                  className="flex flex-col items-center justify-center py-16 rounded-xl relative overflow-hidden"
                  style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-subtle)' }}
                >
                  {/* Decorative grid */}
                  <div
                    className="absolute inset-0 opacity-10 pointer-events-none"
                    style={{
                      backgroundImage: `linear-gradient(rgba(91, 141, 239, 0.1) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(91, 141, 239, 0.1) 1px, transparent 1px)`,
                      backgroundSize: '16px 16px'
                    }}
                  />

                  <div
                    className="relative w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
                    style={{ background: 'var(--bg-elevated)' }}
                  >
                    <Database className="w-8 h-8 animate-pulse" style={{ color: 'var(--text-muted)' }} />
                  </div>
                  <p className="relative text-sm font-display italic mb-1" style={{ color: 'var(--text-secondary)' }}>
                    No backends configured
                  </p>
                  <p className="relative text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    Add a backend to start
                  </p>
                </div>
              )}
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
            style={{
              background: 'var(--bg-tertiary)',
              color: 'var(--text-secondary)'
            }}
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
              boxShadow: isSaved ? 'none' : 'var(--glow-primary)'
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
