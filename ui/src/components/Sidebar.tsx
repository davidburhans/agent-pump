import { ProjectStatus } from '../types';
import { cn } from '../utils/cn'; // I need to create this utility

interface SidebarProps {
  projects: ProjectStatus[];
  selectedPath: string | null;
  onSelectProject: (path: string) => void;
}

export function Sidebar({ projects, selectedPath, onSelectProject }: SidebarProps) {
  return (
    <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
      <div className="p-4 border-b border-gray-800">
        <h2 className="text-xl font-bold text-white">Projects</h2>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {projects.map((project) => (
          <button
            key={project.path}
            onClick={() => onSelectProject(project.path)}
            className={cn(
              "w-full text-left p-3 rounded-md transition-colors border",
              selectedPath === project.path
                ? "bg-blue-900/30 border-blue-500 text-blue-100"
                : "bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700"
            )}
          >
            <div className="font-medium truncate">{project.name}</div>
            <div className="text-xs mt-1 flex justify-between items-center opacity-70">
              <span className="uppercase">{project.state}</span>
              <span>#{project.iteration}</span>
            </div>
          </button>
        ))}
        {projects.length === 0 && (
          <div className="text-center text-gray-500 mt-10">
            No projects found.
          </div>
        )}
      </div>
      <div className="p-4 border-t border-gray-800 text-xs text-gray-500 text-center">
        Agent Pump v0.1.0
      </div>
    </div>
  );
}
