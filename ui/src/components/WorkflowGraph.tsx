import { WorkflowState } from '../types';
import { cn } from '../utils/cn';

interface WorkflowGraphProps {
  workflow: WorkflowState | null;
}

export function WorkflowGraph({ workflow }: WorkflowGraphProps) {
  if (!workflow) {
    return (
      <div className="w-80 bg-gray-900 border-l border-gray-800 flex items-center justify-center text-gray-500 p-4 text-center">
        Select a project to view workflow
      </div>
    );
  }

  // Calculate viewBox based on nodes
  const nodes = workflow.nodes || [];
  const edges = workflow.edges || [];
  
  if (nodes.length === 0) {
    return <div className="w-80 bg-gray-900 border-l border-gray-800 p-4">No workflow data</div>;
  }

  // Simple layout assumption: nodes have positions from backend
  // If not, we might need a default layout, but backend DTO logic seemed to provide them.
  // We'll assume horizontal layout if Y is 0.
  
  // Find bounds
  let maxX = 0;
  let maxY = 0;
  nodes.forEach(n => {
    if (n.position) {
      maxX = Math.max(maxX, n.position[0]);
      maxY = Math.max(maxY, n.position[1]);
    }
  });

  const width = Math.max(maxX + 150, 800);
  const height = Math.max(maxY + 100, 200);

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col h-full">
      <div className="p-4 border-b border-gray-800">
        <h2 className="text-xl font-bold text-white">Workflow</h2>
        <div className="text-xs text-gray-400 mt-1">
          State: <span className="text-white uppercase">{workflow.currentState}</span>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        <svg width={width} height={height} className="w-full h-full min-h-[300px]">
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#4b5563" />
            </marker>
            <marker id="arrowhead-active" markerWidth="10" markerHeight="7" refX="28" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#3b82f6" />
            </marker>
          </defs>
          
          {/* Edges */}
          {edges.map((edge, i) => {
            const source = nodes.find(n => n.name === edge.source);
            const target = nodes.find(n => n.name === edge.target);
            if (!source?.position || !target?.position) return null;

            const [x1, y1] = source.position;
            const [x2, y2] = target.position;
            
            // Adjust coordinates to center of node (assuming node roughly 100x50 centered at pos?)
            // DTO said: position=(terminals_start_x, 0)
            // Let's assume position is top-left or center. Let's assume center for easier SVG.
            // But Textual usually does layout. The Python DTO hardcoded positions:
            // position=((i + 1) * 200, 0)
            // Let's add padding.
            const sx = x1 + 50;
            const sy = y1 + 40;
            const tx = x2 + 50;
            const ty = y2 + 40;

            return (
              <line
                key={i}
                x1={sx} y1={sy} x2={tx} y2={ty}
                stroke={edge.isActive ? "#3b82f6" : "#4b5563"}
                strokeWidth="2"
                markerEnd={edge.isActive ? "url(#arrowhead-active)" : "url(#arrowhead)"}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node, i) => {
            if (!node.position) return null;
            const [x, y] = node.position;
            
            // Offset for padding
            const px = x + 10;
            const py = y + 20;

            return (
              <g key={i} transform={`translate(${px}, ${py})`}>
                <rect
                  width="100"
                  height="40"
                  rx="6"
                  className={cn(
                    "stroke-2",
                    node.isActive ? "fill-blue-900/50 stroke-blue-500 animate-pulse" :
                    node.isCompleted ? "fill-green-900/30 stroke-green-600" :
                    "fill-gray-800 stroke-gray-600"
                  )}
                />
                <text
                  x="50"
                  y="20"
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className={cn(
                    "text-xs font-bold uppercase",
                    node.isActive ? "fill-white" :
                    node.isCompleted ? "fill-green-100" :
                    "fill-gray-400"
                  )}
                >
                  {node.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
