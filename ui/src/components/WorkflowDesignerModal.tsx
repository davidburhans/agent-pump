import { useState, useEffect } from 'react';
import { X, Save, Plus, Trash2, ArrowUp, ArrowDown, Sliders, Info, Zap, Sparkles } from 'lucide-react';
import { WorkflowDefinition, WorkflowPhase } from '../types';
import { fetchProjectWorkflowDef, updateProjectWorkflowDef, fetchWorkflowTemplate } from '../api';
import { cn } from '../utils/cn';

interface WorkflowDesignerModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectPath: string;
}

export function WorkflowDesignerModal({ isOpen, onClose, projectPath }: WorkflowDesignerModalProps) {
  const [workflow, setWorkflow] = useState<WorkflowDefinition | null>(null);
  const [selectedPhaseName, setSelectedPhaseName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Load project local workflow definition
  useEffect(() => {
    if (isOpen && projectPath) {
      setIsLoading(true);
      setErrorMessage(null);
      fetchProjectWorkflowDef(projectPath)
        .then((def) => {
          setWorkflow(def);
          if (def.phases.length > 0) {
            setSelectedPhaseName(def.phases[0].name);
          }
        })
        .catch((e) => {
          setErrorMessage('Failed to load project workflow: ' + e.message);
        })
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, projectPath]);

  if (!isOpen) return null;

  const handleApplyTemplate = async (templateName: string) => {
    try {
      setIsLoading(true);
      setErrorMessage(null);
      const template = await fetchWorkflowTemplate(templateName);
      setWorkflow(template);
      if (template.phases.length > 0) {
        setSelectedPhaseName(template.phases[0].name);
      }
      setSuccessMessage(`Loaded preset blueprint: ${templateName}`);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (e: any) {
      setErrorMessage('Failed to load preset blueprint: ' + e.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    if (!workflow) return;
    try {
      setIsSaving(true);
      setErrorMessage(null);
      setSuccessMessage(null);

      // Validate phase names are unique
      const phaseNames = workflow.phases.map(p => p.name.trim());
      const duplicates = phaseNames.filter((item, index) => phaseNames.indexOf(item) !== index);
      if (duplicates.length > 0) {
        throw new Error(`Duplicate phase names detected: ${duplicates.join(', ')}`);
      }

      // Validate transitions
      const allStates = new Set([
        workflow.initial_state,
        ...workflow.terminal_states,
        ...phaseNames
      ]);

      workflow.phases.forEach((p) => {
        if (p.routing && p.routing.choices.length > 0) {
          p.routing.choices.forEach((c) => {
            if (!allStates.has(c.target)) {
              throw new Error(`Phase '${p.name}' choice has invalid target state: '${c.target}'`);
            }
          });
        } else {
          if (!allStates.has(p.on_success)) {
            throw new Error(`Phase '${p.name}' success target '${p.on_success}' is not a valid state.`);
          }
          if (p.on_failure && !allStates.has(p.on_failure)) {
            throw new Error(`Phase '${p.name}' failure target '${p.on_failure}' is not a valid state.`);
          }
        }
      });

      await updateProjectWorkflowDef(projectPath, workflow);
      setSuccessMessage('Workflow deployed to active memory and saved successfully!');
      setTimeout(() => setSuccessMessage(null), 4000);
    } catch (e: any) {
      setErrorMessage(e.message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleUpdatePhase = (updatedPhase: WorkflowPhase) => {
    if (!workflow) return;
    setWorkflow((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        phases: prev.phases.map((p) => (p.name === selectedPhaseName ? updatedPhase : p)),
      };
    });
    // Update selected phase name in case it changed
    if (selectedPhaseName !== updatedPhase.name) {
      setSelectedPhaseName(updatedPhase.name);
    }
  };

  const handleAddPhase = () => {
    if (!workflow) return;
    const newName = `phase_${workflow.phases.length + 1}`;
    const newPhase: WorkflowPhase = {
      name: newName,
      description: 'New phase step description',
      icon: '⚙️',
      on_success: 'completed',
      on_failure: 'troubleshooting',
      allow_failure_recovery: true,
      timeout: null,
      max_retries: 0,
      retry_delay: 0,
      routing: null,
    };

    setWorkflow((prev) => {
      if (!prev) return null;
      return {
        ...prev,
        phases: [...prev.phases, newPhase],
      };
    });
    setSelectedPhaseName(newName);
  };

  const handleRemovePhase = (nameToRemove: string) => {
    if (!workflow) return;
    setWorkflow((prev) => {
      if (!prev) return null;
      const filtered = prev.phases.filter((p) => p.name !== nameToRemove);
      return {
        ...prev,
        phases: filtered,
      };
    });
    if (selectedPhaseName === nameToRemove) {
      const remaining = workflow.phases.filter((p) => p.name !== nameToRemove);
      setSelectedPhaseName(remaining.length > 0 ? remaining[0].name : null);
    }
  };

  const movePhaseUp = (index: number) => {
    if (!workflow || index === 0) return;
    setWorkflow((prev) => {
      if (!prev) return null;
      const updated = [...prev.phases];
      const temp = updated[index];
      updated[index] = updated[index - 1];
      updated[index - 1] = temp;
      return { ...prev, phases: updated };
    });
  };

  const movePhaseDown = (index: number) => {
    if (!workflow || index === workflow.phases.length - 1) return;
    setWorkflow((prev) => {
      if (!prev) return null;
      const updated = [...prev.phases];
      const temp = updated[index];
      updated[index] = updated[index + 1];
      updated[index + 1] = temp;
      return { ...prev, phases: updated };
    });
  };

  const selectedPhase = workflow?.phases.find((p) => p.name === selectedPhaseName) || null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 backdrop-blur-md overflow-hidden bg-black/60">
      {/* Dynamic ambient backdrop */}
      <div className="absolute w-[600px] h-[600px] rounded-full bg-[var(--accent-primary)]/10 blur-[120px] pointer-events-none -top-40 -left-40" />
      <div className="absolute w-[400px] h-[400px] rounded-full bg-[var(--accent-secondary)]/5 blur-[100px] pointer-events-none -bottom-20 -right-20" />

      {/* Main Designer Modal Container */}
      <div
        className="relative w-full h-[90vh] max-w-7xl rounded-2xl flex flex-col border shadow-2xl overflow-hidden animate-entrance"
        style={{
          background: 'rgba(10, 12, 16, 0.9)',
          borderColor: 'var(--border-subtle)',
          boxShadow: '0 0 50px rgba(0, 0, 0, 0.8)',
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border-subtle)' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-gradient-to-br from-[var(--accent-primary)] to-[var(--accent-secondary)]">
              <Sliders className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-base font-bold font-display tracking-wide" style={{ color: 'var(--text-primary)' }}>
                Visual Workflow Designer
              </h2>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Configure phase parameters, semantic agent-routing choices, and deployment structures.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors hover:bg-[var(--bg-hover)]"
            style={{ color: 'var(--text-secondary)' }}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content area */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Left panel - Phases List & Blueprints */}
          <div className="w-80 border-r flex flex-col p-5 overflow-y-auto" style={{ borderColor: 'var(--border-subtle)' }}>
            {/* Blueprint Shelf */}
            <div className="mb-6">
              <h3 className="text-xs uppercase tracking-wider font-semibold mb-3 flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
                <Sparkles className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                Select Preset Blueprint
              </h3>
              <div className="grid grid-cols-3 gap-2">
                {['minimal', 'default', 'extended'].map((tmpl) => (
                  <button
                    key={tmpl}
                    onClick={() => handleApplyTemplate(tmpl)}
                    className="py-2 px-1 text-center rounded-lg border text-xs font-semibold uppercase tracking-wider capitalize transition-all hover:border-[var(--accent-primary)] hover:bg-[var(--bg-hover)]"
                    style={{
                      background: 'var(--bg-tertiary)',
                      borderColor: 'var(--border-subtle)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {tmpl}
                  </button>
                ))}
              </div>
            </div>

            {/* Phases List */}
            <div className="flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-xs uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
                  Phases List
                </h3>
                <button
                  onClick={handleAddPhase}
                  className="flex items-center gap-1 text-[10px] uppercase font-bold py-1 px-2.5 rounded-md hover:bg-[var(--bg-hover)] border transition-all text-white border-[var(--accent-primary)] bg-[var(--accent-primary)]/10"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Phase
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2 pr-1 stagger-children">
                {workflow?.phases.map((phase, idx) => (
                  <div
                    key={phase.name}
                    onClick={() => setSelectedPhaseName(phase.name)}
                    className={cn(
                      'p-3.5 rounded-xl border cursor-pointer flex items-center justify-between group transition-all duration-200',
                      selectedPhaseName === phase.name
                        ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/5 shadow-md shadow-[var(--accent-primary)]/5'
                        : 'border-[var(--border-subtle)] bg-[var(--bg-tertiary)] hover:bg-[var(--bg-hover)]'
                    )}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="text-lg">{phase.icon || '⚙️'}</span>
                      <div className="min-w-0">
                        <p
                          className="text-xs font-bold font-mono truncate"
                          style={{
                            color: selectedPhaseName === phase.name ? 'var(--accent-primary)' : 'var(--text-primary)',
                          }}
                        >
                          {phase.name}
                        </p>
                        <p className="text-[10px] truncate" style={{ color: 'var(--text-muted)' }}>
                          {phase.routing && phase.routing.choices.length > 0
                            ? `Semantic (${phase.routing.choices.length} choices)`
                            : `Linear ➜ ${phase.on_success}`}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          movePhaseUp(idx);
                        }}
                        disabled={idx === 0}
                        className="p-1 rounded hover:bg-white/5 disabled:opacity-30"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        <ArrowUp className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          movePhaseDown(idx);
                        }}
                        disabled={idx === (workflow?.phases.length || 0) - 1}
                        className="p-1 rounded hover:bg-white/5 disabled:opacity-30"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        <ArrowDown className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemovePhase(phase.name);
                        }}
                        className="p-1 rounded hover:bg-red-500/10 hover:text-red-400"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Middle panel - Live Dynamic SVG Graph */}
          <div className="flex-1 flex flex-col relative overflow-hidden bg-black/20 p-6 min-w-[400px]">
            <h3 className="absolute top-4 left-4 text-[10px] uppercase tracking-wider font-semibold pointer-events-none" style={{ color: 'var(--text-muted)' }}>
              Dynamic SVG Blueprint Preview
            </h3>

            <div className="flex-1 flex items-center justify-center overflow-auto w-full h-full min-h-[300px]">
              {workflow && workflow.phases.length > 0 ? (
                <svg
                  width={workflow.phases.length * 190 + 260}
                  height={320}
                  className="max-w-full max-h-full"
                >
                  <defs>
                    <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                      <circle cx="1.5" cy="1.5" r="1" fill="var(--border-active)" opacity="0.15" />
                    </pattern>
                    <marker id="glowArrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                      <path d="M0,0 L0,6 L6,3 z" fill="var(--accent-primary)" />
                    </marker>
                    <marker id="failureArrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                      <path d="M0,0 L0,6 L6,3 z" fill="#ef4444" />
                    </marker>
                  </defs>

                  <rect width="100%" height="100%" fill="url(#grid)" />

                  {/* SVG Nodes & Edges Render */}
                  {(() => {
                    const phasePositions: Record<string, { x: number; y: number }> = {};
                    phasePositions['idle'] = { x: 30, y: 120 };

                    workflow.phases.forEach((p, idx) => {
                      phasePositions[p.name] = { x: 130 + idx * 190, y: 120 };
                    });

                    phasePositions['completed'] = { x: 130 + workflow.phases.length * 190, y: 50 };
                    phasePositions['error'] = { x: 130 + workflow.phases.length * 190, y: 190 };
                    phasePositions['troubleshooting'] = { x: 130 + workflow.phases.length * 190, y: 260 };

                    const lines: any[] = [];
                    const renderedNodes: any[] = [];

                    // 1. Idle link to first phase
                    lines.push(
                      <path
                        key="idle-to-first"
                        d={`M 100 145 H 130`}
                        stroke="var(--accent-primary)"
                        strokeWidth="2"
                        markerEnd="url(#glowArrow)"
                      />
                    );

                    // 2. Render dynamic edges
                    workflow.phases.forEach((p) => {
                      const pos = phasePositions[p.name];
                      if (!pos) return;

                      // If phase has semantic routing, draw dynamic choices
                      if (p.routing && p.routing.choices.length > 0) {
                        // Draw decision gate diamond
                        const gateX = pos.x + 85;
                        const gateY = pos.y + 40;

                        renderedNodes.push(
                          <g key={`${p.name}-gate`} transform={`translate(${gateX}, ${gateY})`}>
                            <polygon
                              points="0,-12 12,0 0,12 -12,0"
                              fill="rgba(91, 141, 239, 0.15)"
                              stroke="var(--accent-primary)"
                              strokeWidth="1.5"
                            />
                            <title>Semantic Decision Router</title>
                          </g>
                        );

                        // Path to decision gate
                        lines.push(
                          <line
                            key={`${p.name}-to-gate`}
                            x1={pos.x + 70}
                            y1={pos.y + 25}
                            x2={gateX - 12}
                            y2={gateY}
                            stroke="var(--accent-primary)"
                            strokeWidth="1.5"
                          />
                        );

                        // Draw path from decision gate to choice targets
                        p.routing.choices.forEach((choice, cIdx) => {
                          const targetPos = phasePositions[choice.target];
                          if (!targetPos) return;

                          const isLoop = targetPos.x <= pos.x;
                          const d = isLoop
                            ? `M ${gateX} ${gateY + 12} C ${gateX} ${gateY + 60}, ${targetPos.x + 35} ${targetPos.y + 70}, ${targetPos.x + 35} ${targetPos.y + 50}`
                            : `M ${gateX + 12} ${gateY} C ${gateX + 40} ${gateY}, ${targetPos.x - 30} ${targetPos.y + 25}, ${targetPos.x} ${targetPos.y + 25}`;

                          lines.push(
                            <path
                              key={`${p.name}-choice-${cIdx}`}
                              d={d}
                              fill="none"
                              stroke="var(--accent-primary)"
                              strokeWidth="1.5"
                              strokeDasharray="3 3"
                              markerEnd="url(#glowArrow)"
                            />
                          );
                        });
                      } else {
                        // Default linear routing arrows
                        const targetSuccess = phasePositions[p.on_success];
                        if (targetSuccess) {
                          const isLoop = targetSuccess.x <= pos.x;
                          const d = isLoop
                            ? `M ${pos.x + 35} ${pos.y + 50} C ${pos.x + 35} ${pos.y + 90}, ${targetSuccess.x + 35} ${targetSuccess.y + 90}, ${targetSuccess.x + 35} ${targetSuccess.y + 50}`
                            : `M ${pos.x + 70} ${pos.y + 25} C ${pos.x + 110} ${pos.y + 25}, ${targetSuccess.x - 30} ${targetSuccess.y + 25}, ${targetSuccess.x} ${targetSuccess.y + 25}`;

                          lines.push(
                            <path
                              key={`${p.name}-success`}
                              d={d}
                              fill="none"
                              stroke="var(--accent-primary)"
                              strokeWidth="1.5"
                              markerEnd="url(#glowArrow)"
                            />
                          );
                        }

                        // Failure arrow
                        const targetFailure = phasePositions[p.on_failure];
                        if (targetFailure) {
                          lines.push(
                            <path
                              key={`${p.name}-failure`}
                              d={`M ${pos.x + 35} ${pos.y} C ${pos.x + 35} ${pos.y - 40}, ${targetFailure.x - 40} ${targetFailure.y + 25}, ${targetFailure.x} ${targetFailure.y + 25}`}
                              fill="none"
                              stroke="#ef4444"
                              strokeWidth="1"
                              strokeDasharray="4 2"
                              markerEnd="url(#failureArrow)"
                            />
                          );
                        }
                      }

                      // Render Node
                      const isActive = selectedPhaseName === p.name;
                      renderedNodes.push(
                        <g
                          key={p.name}
                          transform={`translate(${pos.x}, ${pos.y})`}
                          className="cursor-pointer"
                          onClick={() => setSelectedPhaseName(p.name)}
                        >
                          <rect
                            width="70"
                            height="50"
                            rx="8"
                            fill={isActive ? 'rgba(91, 141, 239, 0.15)' : 'var(--bg-tertiary)'}
                            stroke={isActive ? 'var(--accent-primary)' : 'var(--border-subtle)'}
                            strokeWidth={isActive ? '2' : '1'}
                          />
                          <text x="35" y="22" dominantBaseline="middle" textAnchor="middle" className="text-[15px]">
                            {p.icon || '⚙️'}
                          </text>
                          <text x="35" y="38" textAnchor="middle" className="text-[9px] font-bold font-mono" fill="var(--text-secondary)">
                            {p.name.length > 9 ? p.name.substring(0, 7) + '..' : p.name}
                          </text>
                        </g>
                      );
                    });

                    // 3. Render Terminal nodes
                    const renderTerminal = (name: string, label: string, color: string, icon: string) => {
                      const pos = phasePositions[name];
                      if (!pos) return;
                      renderedNodes.push(
                        <g key={name} transform={`translate(${pos.x}, ${pos.y})`}>
                          <rect
                            width="90"
                            height="40"
                            rx="10"
                            fill="rgba(10, 12, 16, 0.6)"
                            stroke={color}
                            strokeWidth="1.5"
                          />
                          <text x="12" y="22" dominantBaseline="middle" className="text-sm">
                            {icon}
                          </text>
                          <text x="30" y="22" dominantBaseline="middle" className="text-[9px] uppercase tracking-wider font-bold" fill={color}>
                            {label}
                          </text>
                        </g>
                      );
                    };

                    renderTerminal('idle', 'idle start', 'var(--text-muted)', '🏁');
                    renderTerminal('completed', 'completed', 'var(--accent-green)', '🎉');
                    renderTerminal('error', 'terminal err', '#ef4444', '💥');
                    renderTerminal('troubleshooting', 'troubleshoot', 'var(--accent-amber)', '🛠');

                    return (
                      <>
                        {lines}
                        {renderedNodes}
                      </>
                    );
                  })()}
                </svg>
              ) : (
                <p className="text-sm text-slate-500 italic">No phases defined. Add a phase to get started.</p>
              )}
            </div>
          </div>

          {/* Right Panel - Active Phase Details Inspector Panel */}
          <div className="w-[450px] border-l flex flex-col p-5 overflow-y-auto" style={{ borderColor: 'var(--border-subtle)', background: 'rgba(12, 14, 18, 0.95)' }}>
            {selectedPhase ? (
              <div className="space-y-5 animate-entrance">
                <div className="border-b pb-4" style={{ borderColor: 'var(--border-subtle)' }}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-2xl">{selectedPhase.icon || '⚙️'}</span>
                    <h3 className="text-sm font-bold font-mono tracking-wide" style={{ color: 'var(--accent-primary)' }}>
                      {selectedPhase.name}
                    </h3>
                  </div>
                  <p className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
                    Phase parameters configuration inspector.
                  </p>
                </div>

                {/* Form fields */}
                <div className="space-y-4">
                  <div className="grid grid-cols-4 gap-3">
                    <div className="col-span-3">
                      <label className="text-[10px] uppercase tracking-wider font-semibold mb-1.5 block" style={{ color: 'var(--text-muted)' }}>
                        Phase Name
                      </label>
                      <input
                        type="text"
                        value={selectedPhase.name}
                        onChange={(e) => handleUpdatePhase({ ...selectedPhase, name: e.target.value })}
                        className="w-full py-1.5 px-3 rounded-lg border text-xs font-mono"
                        style={{
                          background: 'var(--bg-tertiary)',
                          borderColor: 'var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>
                    <div>
                      <label className="text-[10px] uppercase tracking-wider font-semibold mb-1.5 block text-center" style={{ color: 'var(--text-muted)' }}>
                        Emoji Icon
                      </label>
                      <input
                        type="text"
                        value={selectedPhase.icon}
                        onChange={(e) => handleUpdatePhase({ ...selectedPhase, icon: e.target.value })}
                        className="w-full py-1.5 text-center rounded-lg border text-sm"
                        style={{
                          background: 'var(--bg-tertiary)',
                          borderColor: 'var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-[10px] uppercase tracking-wider font-semibold mb-1.5 block" style={{ color: 'var(--text-muted)' }}>
                      Description
                    </label>
                    <textarea
                      rows={2}
                      value={selectedPhase.description}
                      onChange={(e) => handleUpdatePhase({ ...selectedPhase, description: e.target.value })}
                      className="w-full py-1.5 px-3 rounded-lg border text-xs leading-relaxed"
                      style={{
                        background: 'var(--bg-tertiary)',
                        borderColor: 'var(--border-subtle)',
                        color: 'var(--text-primary)',
                      }}
                    />
                  </div>

                  {/* Timeout / Retries group */}
                  <div className="grid grid-cols-3 gap-3 p-3.5 rounded-xl border bg-black/10" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div>
                      <label className="text-[9px] uppercase tracking-wider font-semibold mb-1 block" style={{ color: 'var(--text-muted)' }}>
                        Timeout (s)
                      </label>
                      <input
                        type="number"
                        placeholder="Global"
                        value={selectedPhase.timeout || ''}
                        onChange={(e) => handleUpdatePhase({ ...selectedPhase, timeout: e.target.value ? parseInt(e.target.value) : null })}
                        className="w-full py-1 px-2.5 rounded-md border text-[11px] font-mono"
                        style={{
                          background: 'var(--bg-tertiary)',
                          borderColor: 'var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>
                    <div>
                      <label className="text-[9px] uppercase tracking-wider font-semibold mb-1 block" style={{ color: 'var(--text-muted)' }}>
                        Max Retries
                      </label>
                      <input
                        type="number"
                        value={selectedPhase.max_retries}
                        onChange={(e) => handleUpdatePhase({ ...selectedPhase, max_retries: parseInt(e.target.value) || 0 })}
                        className="w-full py-1 px-2.5 rounded-md border text-[11px] font-mono"
                        style={{
                          background: 'var(--bg-tertiary)',
                          borderColor: 'var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>
                    <div>
                      <label className="text-[9px] uppercase tracking-wider font-semibold mb-1 block" style={{ color: 'var(--text-muted)' }}>
                        Delay (s)
                      </label>
                      <input
                        type="number"
                        value={selectedPhase.retry_delay}
                        onChange={(e) => handleUpdatePhase({ ...selectedPhase, retry_delay: parseFloat(e.target.value) || 0 })}
                        className="w-full py-1 px-2.5 rounded-md border text-[11px] font-mono"
                        style={{
                          background: 'var(--bg-tertiary)',
                          borderColor: 'var(--border-subtle)',
                          color: 'var(--text-primary)',
                        }}
                      />
                    </div>
                  </div>

                  {/* Routing Decision gate controller */}
                  <div className="border-t pt-4 mt-2" style={{ borderColor: 'var(--border-subtle)' }}>
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <label className="text-[10px] uppercase tracking-wider font-bold block" style={{ color: 'var(--text-primary)' }}>
                          Transition Routing Mode
                        </label>
                        <p className="text-[9px]" style={{ color: 'var(--text-muted)' }}>
                          Determine whether state transition is static or evaluated by the backend agent harness.
                        </p>
                      </div>
                    </div>

                    {/* Segmented control tabs */}
                    <div className="flex rounded-lg p-0.5 mb-4 bg-black/40 border border-white/5">
                      <button
                        onClick={() => handleUpdatePhase({ ...selectedPhase, routing: null })}
                        className={cn(
                          'flex-1 py-1.5 text-center text-xs font-semibold uppercase tracking-wider rounded-md transition-all',
                          !selectedPhase.routing
                            ? 'bg-gradient-to-r from-[var(--accent-primary)]/15 to-[var(--accent-secondary)]/15 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20'
                            : 'text-[var(--text-muted)] hover:text-white'
                        )}
                      >
                        Linear default
                      </button>
                      <button
                        onClick={() =>
                          handleUpdatePhase({
                            ...selectedPhase,
                            routing: {
                              type: 'agent',
                              prompt_template: null,
                              choices: [
                                { target: selectedPhase.on_success, description: 'Default transition' },
                              ],
                            },
                          })
                        }
                        className={cn(
                          'flex-1 py-1.5 text-center text-xs font-semibold uppercase tracking-wider rounded-md transition-all',
                          selectedPhase.routing
                            ? 'bg-gradient-to-r from-[var(--accent-primary)]/15 to-[var(--accent-secondary)]/15 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20'
                            : 'text-[var(--text-muted)] hover:text-white'
                        )}
                      >
                        Semantic agent
                      </button>
                    </div>

                    {!selectedPhase.routing ? (
                      /* Linear transition options */
                      <div className="grid grid-cols-2 gap-3 p-3.5 rounded-xl border bg-black/5" style={{ borderColor: 'var(--border-subtle)' }}>
                        <div>
                          <label className="text-[9px] uppercase tracking-wider font-semibold mb-1 block" style={{ color: 'var(--text-muted)' }}>
                            Success Route ➜
                          </label>
                          <input
                            type="text"
                            value={selectedPhase.on_success}
                            onChange={(e) => handleUpdatePhase({ ...selectedPhase, on_success: e.target.value })}
                            className="w-full py-1.5 px-3 rounded-lg border text-xs font-mono"
                            style={{
                              background: 'var(--bg-tertiary)',
                              borderColor: 'var(--border-subtle)',
                              color: 'var(--text-primary)',
                            }}
                          />
                        </div>
                        <div>
                          <label className="text-[9px] uppercase tracking-wider font-semibold mb-1 block text-red-400">
                            Failure Route ➜
                          </label>
                          <input
                            type="text"
                            value={selectedPhase.on_failure}
                            onChange={(e) => handleUpdatePhase({ ...selectedPhase, on_failure: e.target.value })}
                            className="w-full py-1.5 px-3 rounded-lg border text-xs font-mono"
                            style={{
                              background: 'var(--bg-tertiary)',
                              borderColor: 'var(--border-subtle)',
                              color: 'var(--text-primary)',
                            }}
                          />
                        </div>
                      </div>
                    ) : (
                      /* Semantic Agent routing options */
                      <div className="space-y-4">
                        <div className="p-3.5 rounded-xl border bg-slate-500/5 space-y-2.5" style={{ borderColor: 'var(--border-subtle)' }}>
                          <label className="text-[9px] uppercase tracking-wider font-semibold flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
                            <Info className="w-3.5 h-3.5 text-[var(--accent-primary)]" />
                            Agent Guidelines prompt (Optional)
                          </label>
                          <textarea
                            rows={3}
                            placeholder="Add semantic guidance (e.g. 'Ensure to check error severity before routing.')"
                            value={selectedPhase.routing.prompt_template || ''}
                            onChange={(e) =>
                              handleUpdatePhase({
                                ...selectedPhase,
                                routing: {
                                  ...selectedPhase.routing!,
                                  prompt_template: e.target.value || null,
                                },
                              })
                            }
                            className="w-full py-1.5 px-3 rounded-lg border text-[11px]"
                            style={{
                              background: 'var(--bg-tertiary)',
                              borderColor: 'var(--border-subtle)',
                              color: 'var(--text-primary)',
                            }}
                          />
                        </div>

                        {/* Choices list builder */}
                        <div className="space-y-3">
                          <div className="flex items-center justify-between">
                            <label className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: 'var(--text-muted)' }}>
                              Routing Choices List
                            </label>
                            <button
                              onClick={() => {
                                const newChoices = [...selectedPhase.routing!.choices, { target: 'completed', description: 'Triggered when...' }];
                                handleUpdatePhase({
                                  ...selectedPhase,
                                  routing: {
                                    ...selectedPhase.routing!,
                                    choices: newChoices,
                                  },
                                });
                              }}
                              className="text-[10px] uppercase font-bold py-1 px-2.5 rounded-md hover:bg-white/5 border border-white/10 text-white"
                            >
                              Add Choice
                            </button>
                          </div>

                          <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                            {selectedPhase.routing.choices.map((choice, cIdx) => (
                              <div
                                key={cIdx}
                                className="p-3 rounded-lg border flex flex-col gap-2 relative bg-black/20"
                                style={{ borderColor: 'var(--border-subtle)' }}
                              >
                                <button
                                  onClick={() => {
                                    const filtered = selectedPhase.routing!.choices.filter((_, idx) => idx !== cIdx);
                                    handleUpdatePhase({
                                      ...selectedPhase,
                                      routing: {
                                        ...selectedPhase.routing!,
                                        choices: filtered,
                                      },
                                    });
                                  }}
                                  className="absolute top-2 right-2 text-slate-500 hover:text-red-400"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>

                                <div className="w-2/3">
                                  <label className="text-[8px] uppercase tracking-wider font-semibold mb-0.5 block" style={{ color: 'var(--text-muted)' }}>
                                    Target State
                                  </label>
                                  <input
                                    type="text"
                                    value={choice.target}
                                    onChange={(e) => {
                                      const updatedChoices = [...selectedPhase.routing!.choices];
                                      updatedChoices[cIdx] = { ...choice, target: e.target.value };
                                      handleUpdatePhase({
                                        ...selectedPhase,
                                        routing: {
                                          ...selectedPhase.routing!,
                                          choices: updatedChoices,
                                        },
                                      });
                                    }}
                                    className="w-full py-0.5 px-2 rounded border text-[10px] font-mono"
                                    style={{
                                      background: 'var(--bg-tertiary)',
                                      borderColor: 'var(--border-subtle)',
                                      color: 'var(--text-primary)',
                                    }}
                                  />
                                </div>

                                <div>
                                  <label className="text-[8px] uppercase tracking-wider font-semibold mb-0.5 block" style={{ color: 'var(--text-muted)' }}>
                                    Semantic description / when to trigger
                                  </label>
                                  <input
                                    type="text"
                                    value={choice.description}
                                    onChange={(e) => {
                                      const updatedChoices = [...selectedPhase.routing!.choices];
                                      updatedChoices[cIdx] = { ...choice, description: e.target.value };
                                      handleUpdatePhase({
                                        ...selectedPhase,
                                        routing: {
                                          ...selectedPhase.routing!,
                                          choices: updatedChoices,
                                        },
                                      });
                                    }}
                                    className="w-full py-0.5 px-2 rounded border text-[10px]"
                                    style={{
                                      background: 'var(--bg-tertiary)',
                                      borderColor: 'var(--border-subtle)',
                                      color: 'var(--text-primary)',
                                    }}
                                  />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500 italic">
                <Sliders className="w-8 h-8 mb-2 opacity-30" />
                Select a phase from list to customize parameters.
              </div>
            )}
          </div>
        </div>

        {/* Footer controls & Feedbacks */}
        <div
          className="px-6 py-4 flex items-center justify-between border-t"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-secondary)' }}
        >
          <div className="flex-1 max-w-lg mr-4">
            {errorMessage && (
              <div className="py-2 px-3.5 rounded-lg border text-xs font-semibold bg-red-500/10 border-red-500/20 text-red-400">
                ⚠️ Error: {errorMessage}
              </div>
            )}
            {successMessage && (
              <div className="py-2 px-3.5 rounded-lg border text-xs font-semibold bg-emerald-500/10 border-emerald-500/20 text-emerald-400 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5" />
                {successMessage}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider hover:bg-[var(--bg-hover)] border transition-all"
              style={{
                borderColor: 'var(--border-subtle)',
                color: 'var(--text-secondary)',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving || isLoading || !workflow}
              className="flex items-center gap-1.5 px-5 py-2 rounded-lg text-xs font-bold uppercase tracking-wider border shadow-md transition-all text-white border-[var(--accent-primary)] hover:shadow-[var(--accent-primary)]/10 hover:shadow-lg disabled:opacity-50"
              style={{
                background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))',
              }}
            >
              <Save className="w-4 h-4" />
              {isSaving ? 'Deploying...' : 'Deploy & Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
