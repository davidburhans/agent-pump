import { WorkflowState } from '../types';
import { GitBranch, Clock, Zap, ChevronRight } from 'lucide-react';

interface WorkflowGraphProps {
  workflow: WorkflowState | null;
}

export function WorkflowGraph({ workflow }: WorkflowGraphProps) {
  if (!workflow) {
    return (
      <div
        className="w-96 flex flex-col items-center justify-center text-center p-8 relative overflow-hidden"
        style={{ background: 'var(--bg-secondary)' }}
      >
        {/* Decorative grid */}
        <div
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `linear-gradient(rgba(91, 141, 239, 0.1) 1px, transparent 1px),
              linear-gradient(90deg, rgba(91, 141, 239, 0.1) 1px, transparent 1px)`,
            backgroundSize: '20px 20px'
          }}
        />

        {/* Animated pulsing rings */}
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
        >
          <div
            className="w-40 h-40 rounded-full border border-[var(--accent-primary)] opacity-5 animate-ping"
            style={{ animationDuration: '4s' }}
          />
          <div
            className="absolute w-32 h-32 rounded-full border border-[var(--accent-secondary)] opacity-5 animate-ping"
            style={{ animationDuration: '3s', animationDelay: '0.5s' }}
          />
        </div>

        {/* Animated border */}
        <div
          className="absolute inset-4 rounded-2xl animate-ambient"
          style={{ border: '1px dashed var(--border-subtle)' }}
        />

        <div
          className="relative w-24 h-24 rounded-2xl flex items-center justify-center mb-6 animate-entrance"
          style={{
            background: 'linear-gradient(135deg, var(--bg-tertiary), var(--bg-elevated))',
            border: '1px solid var(--border-subtle)',
            boxShadow: '0 0 40px rgba(91, 141, 239, 0.1), inset 0 0 20px rgba(91, 141, 239, 0.05)'
          }}
        >
          <GitBranch className="w-12 h-12 animate-pulse" style={{ color: 'var(--text-muted)' }} />
        </div>

        <p className="relative text-base font-display font-medium mb-2 italic" style={{ color: 'var(--text-secondary)' }}>
          Awaiting Selection
        </p>
        <p className="relative text-sm font-mono" style={{ color: 'var(--text-muted)' }}>
          Select a project to monitor
        </p>

        {/* Corner accents with glow */}
        <div className="absolute top-4 left-4 w-8 h-8 border-l-2 border-t-2 rounded-tl-xl" style={{ borderColor: 'var(--accent-primary)', opacity: 0.4 }} />
        <div className="absolute top-4 right-4 w-8 h-8 border-r-2 border-t-2 rounded-tr-xl" style={{ borderColor: 'var(--accent-primary)', opacity: 0.4 }} />
        <div className="absolute bottom-4 left-4 w-8 h-8 border-l-2 border-b-2 rounded-bl-xl" style={{ borderColor: 'var(--accent-secondary)', opacity: 0.3 }} />
        <div className="absolute bottom-4 right-4 w-8 h-8 border-r-2 border-b-2 rounded-br-xl" style={{ borderColor: 'var(--accent-secondary)', opacity: 0.3 }} />
      </div>
    );
  }

  const nodes = workflow.nodes || [];
  const edges = workflow.edges || [];

  // Calculate bounds for SVG
  let maxX = 0;
  let maxY = 0;
  nodes.forEach(n => {
    if (n.position) {
      maxX = Math.max(maxX, n.position[0]);
      maxY = Math.max(maxY, n.position[1]);
    }
  });

  const width = Math.max(maxX + 200, 400);
  const height = Math.max(maxY + 150, 300);

  // Find active node for highlighting
  const completedCount = nodes.filter(n => n.isCompleted).length;

  return (
    <div
      className="w-96 flex flex-col h-full"
      style={{ background: 'var(--bg-secondary)' }}
    >
      {/* Header */}
      <div
        className="p-5 border-b"
        style={{ borderColor: 'var(--border-subtle)' }}
      >
        <div className="flex items-center gap-3 mb-4">
          <div
            className="w-10 h-10 rounded-xl flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))' }}
          >
            <GitBranch className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Workflow State
            </h2>
            <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              {workflow.currentState}
            </p>
          </div>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-3 stagger-children">
          <div
            className="flex flex-col items-center p-3 rounded-xl relative overflow-hidden group transition-all duration-200 hover:bg-[var(--bg-hover)]"
            style={{ background: 'var(--bg-tertiary)' }}
          >
            {/* Subtle gradient overlay */}
            <div
              className="absolute inset-0 opacity-10"
              style={{ background: 'linear-gradient(135deg, var(--accent-primary), transparent)' }}
            />
            {/* Shine effect on hover */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-20 transition-opacity duration-300"
              style={{
                background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.1) 50%, transparent 60%)',
                transform: 'translateX(-100%)'
              }}
            />
            <span data-testid="workflow-iteration" className="text-lg font-bold font-mono gradient-text relative">
              {workflow.iteration}
            </span>
            <span className="text-[10px] uppercase tracking-wider mt-1 relative" style={{ color: 'var(--text-muted)' }}>
              Iteration
            </span>
          </div>

          <div
            className="flex flex-col items-center p-3 rounded-xl relative overflow-hidden group transition-all duration-200 hover:bg-[var(--bg-hover)]"
            style={{ background: 'var(--bg-tertiary)' }}
          >
            {/* Subtle gradient overlay */}
            <div
              className="absolute inset-0 opacity-10"
              style={{ background: 'linear-gradient(135deg, var(--accent-green), transparent)' }}
            />
            {/* Shine effect on hover */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-20 transition-opacity duration-300"
              style={{
                background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.1) 50%, transparent 60%)',
                transform: 'translateX(-100%)'
              }}
            />
            <div className="flex items-center gap-1 relative">
              <Zap className="w-4 h-4 relative" style={{ color: 'var(--accent-green)' }} />
              <span className="text-lg font-bold font-mono relative" style={{ color: 'var(--accent-green)' }}>
                {completedCount}
              </span>
            </div>
            <span className="text-[10px] uppercase tracking-wider mt-1 relative" style={{ color: 'var(--text-muted)' }}>
              Completed
            </span>
          </div>

          <div
            className="flex flex-col items-center p-3 rounded-xl relative overflow-hidden group transition-all duration-200 hover:bg-[var(--bg-hover)]"
            style={{ background: 'var(--bg-tertiary)' }}
          >
            {/* Subtle gradient overlay */}
            <div
              className="absolute inset-0 opacity-10"
              style={{ background: 'linear-gradient(135deg, var(--accent-amber), transparent)' }}
            />
            {/* Shine effect on hover */}
            <div
              className="absolute inset-0 opacity-0 group-hover:opacity-20 transition-opacity duration-300"
              style={{
                background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.1) 50%, transparent 60%)',
                transform: 'translateX(-100%)'
              }}
            />
            <div className="flex items-center gap-1 relative">
              <Clock className="w-4 h-4 relative" style={{ color: 'var(--accent-amber)' }} />
              <span className="text-lg font-bold font-mono relative" style={{ color: 'var(--accent-amber)' }}>
                {Math.floor(workflow.timeInState / 60)}m
              </span>
            </div>
            <span className="text-[10px] uppercase tracking-wider mt-1 relative" style={{ color: 'var(--text-muted)' }}>
              In State
            </span>
          </div>
        </div>
      </div>

      {/* Workflow visualization */}
      <div className="flex-1 overflow-auto p-4">
        {nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
              No workflow data available
            </p>
          </div>
        ) : (
          <svg
            width={width}
            height={height}
            className="w-full h-full min-h-[250px]"
            style={{ minWidth: '350px' }}
          >
            {/* Grid pattern background */}
            <defs>
              <pattern id="wfGrid" width="24" height="24" patternUnits="userSpaceOnUse">
                <path
                  d="M 24 0 L 0 0 0 24"
                  fill="none"
                  stroke="var(--border-subtle)"
                  strokeWidth="0.5"
                  opacity="0.25"
                />
              </pattern>
              <marker
                id="arrow"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
              >
                <path d="M0,0 L0,6 L8,3 z" fill="var(--border-active)" />
              </marker>
              <marker
                id="arrow-active"
                markerWidth="8"
                markerHeight="8"
                refX="6"
                refY="3"
                orient="auto"
              >
                <path d="M0,0 L0,6 L8,3 z" fill="var(--accent-primary)" />
              </marker>
              <filter id="glow-violet">
                <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            <rect width="100%" height="100%" fill="url(#wfGrid)" />

            {/* Edges */}
            {edges.map((edge, i) => {
              const source = nodes.find(n => n.name === edge.source);
              const target = nodes.find(n => n.name === edge.target);
              if (!source?.position || !target?.position) return null;

              const [x1, y1] = source.position;
              const [x2, y2] = target.position;

              const sx = x1 + 60;
              const sy = y1 + 25;
              const tx = x2;
              const ty = y2 + 25;

              return (
                <path
                  key={i}
                  d={`M ${sx} ${sy} C ${sx + 40} ${sy}, ${tx - 40} ${ty}, ${tx} ${ty}`}
                  fill="none"
                  stroke={edge.isActive ? 'var(--accent-primary)' : 'var(--border-active)'}
                  strokeWidth="2"
                  markerEnd={edge.isActive ? 'url(#arrow-active)' : 'url(#arrow)'}
                  className="transition-all duration-300"
                  style={edge.isActive ? { filter: 'url(#glow-violet)' } : {}}
                />
              );
            })}

            {/* Nodes */}
            {nodes.map((node, i) => {
              if (!node.position) return null;
              const [x, y] = node.position;

              const nodeColors = {
                active: {
                  bg: 'rgba(91, 141, 239, 0.15)',
                  border: 'var(--accent-primary)',
                  text: 'var(--accent-primary)',
                },
                completed: {
                  bg: 'rgba(16, 185, 129, 0.1)',
                  border: 'var(--accent-green)',
                  text: 'var(--accent-green)',
                },
                pending: {
                  bg: 'var(--bg-tertiary)',
                  border: 'var(--border-active)',
                  text: 'var(--text-muted)',
                }
              };

              const colors = node.isActive ? nodeColors.active :
                            node.isCompleted ? nodeColors.completed :
                            nodeColors.pending;

              return (
                <g
                  key={i}
                  transform={`translate(${x}, ${y})`}
                  className="transition-all duration-300"
                >
                  {/* Glow effect for active node */}
                  {node.isActive && (
                    <>
                      <rect
                        x="-8"
                        y="-8"
                        width="136"
                        height="66"
                        rx="12"
                        fill="none"
                        stroke="var(--accent-primary)"
                        strokeWidth="1"
                        opacity="0.2"
                        style={{ filter: 'blur(10px)' }}
                        className="animate-pulse"
                      />
                      <rect
                        x="-4"
                        y="-4"
                        width="128"
                        height="58"
                        rx="10"
                        fill="none"
                        stroke="var(--accent-primary)"
                        strokeWidth="2"
                        opacity="0.4"
                        style={{ filter: 'blur(4px)' }}
                        className="animate-pulse"
                      />
                    </>
                  )}

                  {/* Main node */}
                  <rect
                    width="120"
                    height="50"
                    rx="8"
                    fill={colors.bg}
                    stroke={colors.border}
                    strokeWidth={node.isActive ? 2 : 1.5}
                    style={node.isActive ? { filter: 'url(#glow-violet)' } : {}}
                    className="transition-all duration-300 cursor-pointer"
                  >
                    <title>{node.name}</title>
                  </rect>

                  {/* Inner highlight for active node */}
                  {node.isActive && (
                    <rect
                      x="4"
                      y="4"
                      width="112"
                      height="20"
                      rx="4"
                      fill="var(--accent-primary)"
                      opacity="0.08"
                    />
                  )}

                  {/* Inner shadow for completed nodes */}
                  {node.isCompleted && (
                    <rect
                      x="4"
                      y="4"
                      width="112"
                      height="42"
                      rx="4"
                      fill="var(--accent-green)"
                      opacity="0.05"
                    />
                  )}

                  {/* Icon */}
                  <g transform="translate(12, 13)">
                    {node.isActive && (
                      <circle cx="12" cy="12" r="10" fill="var(--accent-primary)" opacity="0.12" className="animate-pulse" />
                    )}
                    <GitBranch
                      className="w-5 h-5"
                      style={{ color: colors.text }}
                    />
                  </g>

                  {/* Label */}
                  <text
                    x="44"
                    y="30"
                    dominantBaseline="middle"
                    className="text-xs font-semibold uppercase tracking-wider"
                    fill={colors.text}
                  >
                    {node.name.length > 10 ? node.name.substring(0, 10) + '...' : node.name}
                  </text>

                  {/* Status indicator */}
                  {node.isActive && (
                    <circle
                      cx="110"
                      cy="10"
                      r="4"
                      fill="var(--accent-primary)"
                      className="animate-pulse"
                    />
                  )}
                  {node.isCompleted && (
                    <circle
                      cx="110"
                      cy="10"
                      r="4"
                      fill="var(--accent-green)"
                    />
                  )}
                </g>
              );
            })}
          </svg>
        )}

        {/* Available transitions */}
        {workflow.availableTransitions.length > 0 && (
          <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--border-subtle)' }}>
            <p className="text-[10px] uppercase tracking-wider font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>
              Available Transitions
            </p>
            <div className="flex flex-wrap gap-2">
              {workflow.availableTransitions.map((transition) => (
                <button
                  key={transition}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 group"
                  style={{
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'var(--accent-primary)';
                    e.currentTarget.style.color = 'var(--accent-primary)';
                    e.currentTarget.style.background = 'var(--bg-hover)';
                    e.currentTarget.style.transform = 'translateY(-1px)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'var(--border-subtle)';
                    e.currentTarget.style.color = 'var(--text-secondary)';
                    e.currentTarget.style.background = 'var(--bg-tertiary)';
                    e.currentTarget.style.transform = 'translateY(0)';
                  }}
                >
                  <ChevronRight className="w-3 h-3 transition-transform duration-200 group-hover:translate-x-0.5" style={{ color: 'var(--accent-primary)' }} />
                  {transition}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
