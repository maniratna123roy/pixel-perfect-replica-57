import { Link } from "@tanstack/react-router";
import { Clapperboard, FolderOpen, Plus, Settings2, X } from "lucide-react";
import { formatDate, type Project, type ProjectStatus } from "@/lib/demo-projects";
import type { DashboardView } from "./view-types";

const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: "Draft",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
};

interface SidebarProps {
  view: DashboardView;
  projects: Project[];
  activeProjectId: string | null;
  onNavigate: (view: DashboardView) => void;
  onOpenProject: (id: string) => void;
  onClose?: () => void;
  mobile?: boolean;
}

function statusDotClass(status: ProjectStatus): string {
  switch (status) {
    case "ready":
      return "bg-primary";
    case "processing":
      return "bg-primary animate-pulse";
    case "failed":
      return "bg-destructive";
    default:
      return "bg-muted-foreground/50";
  }
}

export function Sidebar({
  view,
  projects,
  activeProjectId,
  onNavigate,
  onOpenProject,
  onClose,
  mobile = false,
}: SidebarProps) {
  const recent = [...projects].sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 4);

  return (
    <aside
      className={`flex h-full w-60 shrink-0 flex-col border-r border-border bg-sidebar ${
        mobile ? "fixed inset-y-0 left-0 z-40" : ""
      }`}
      aria-label="Dashboard navigation"
    >
      <div className="flex items-center justify-between px-5 py-5">
        <Link to="/" className="text-[15px] font-medium tracking-tight text-foreground">
          bird&rsquo;s eye
        </Link>
        {mobile && (
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <nav className="flex flex-col gap-1 px-3">
        <SidebarItem
          icon={Plus}
          label="New Reconstruction"
          active={view === "new"}
          onClick={() => onNavigate("new")}
        />
        <SidebarItem
          icon={FolderOpen}
          label="My Projects"
          active={view === "projects"}
          onClick={() => onNavigate("projects")}
        />
        <SidebarItem
          icon={Settings2}
          label="Settings"
          active={view === "settings"}
          onClick={() => onNavigate("settings")}
        />
      </nav>

      {recent.length > 0 && (
        <div className="mt-8 min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          <p className="px-2 pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Recent Projects
          </p>
          <ul className="flex flex-col gap-0.5">
            {recent.map((project) => (
              <li key={project.id}>
                <button
                  onClick={() => onOpenProject(project.id)}
                  aria-current={activeProjectId === project.id}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left text-sm transition-colors ${
                    activeProjectId === project.id
                      ? "bg-sidebar-accent text-foreground"
                      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                  }`}
                >
                  <Clapperboard className="h-3.5 w-3.5 shrink-0 opacity-70" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate">{project.name}</span>
                  <span
                    className={`h-1.5 w-1.5 shrink-0 rounded-full ${statusDotClass(project.status)}`}
                    title={STATUS_LABEL[project.status]}
                    aria-label={STATUS_LABEL[project.status]}
                  />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="border-t border-border px-5 py-4">
        <p className="text-[11px] text-muted-foreground">
          Demo workspace — projects are stored locally in this browser.
        </p>
      </div>
    </aside>
  );
}

function SidebarItem({
  icon: Icon,
  label,
  active,
  onClick,
}: {
  icon: typeof Plus;
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-current={active}
      className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
        active
          ? "bg-primary font-medium text-primary-foreground"
          : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" aria-hidden="true" />
      {label}
    </button>
  );
}

export { STATUS_LABEL, statusDotClass, formatDate };
