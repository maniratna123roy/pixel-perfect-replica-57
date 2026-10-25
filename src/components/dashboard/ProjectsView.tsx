import { Clapperboard, Plus } from "lucide-react";
import { formatDate, type Project, type ProjectStatus } from "@/lib/demo-projects";
import { STATUS_LABEL, statusDotClass } from "./Sidebar";

interface ProjectsViewProps {
  projects: Project[];
  onOpenProject: (id: string) => void;
  onNew: () => void;
}

export function ProjectsView({ projects, onOpenProject, onNew }: ProjectsViewProps) {
  const sorted = [...projects].sort((a, b) => b.updatedAt - a.updatedAt);

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-background p-6 md:p-8">
      <div className="mx-auto w-full max-w-5xl">
        <div className="flex items-center justify-between border-b border-border pb-5">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-foreground">My Projects</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Manage and view your 3D drone reconstruction captures.
            </p>
          </div>
          <button
            onClick={onNew}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3.5 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <Plus className="h-4 w-4" />
            New Capture
          </button>
        </div>

        {sorted.length === 0 ? (
          <div className="mt-16 flex flex-col items-center justify-center rounded-xl border border-dashed border-border p-12 text-center">
            <Clapperboard className="h-10 w-10 text-muted-foreground/60" />
            <h3 className="mt-4 text-base font-medium text-foreground">No projects yet</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Upload a drone video to generate your first interactive 3D scene.
            </p>
            <button
              onClick={onNew}
              className="mt-5 inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Plus className="h-4 w-4" />
              Start New Project
            </button>
          </div>
        ) : (
          <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sorted.map((project) => (
              <div
                key={project.id}
                onClick={() => onOpenProject(project.id)}
                className="group relative flex cursor-pointer flex-col justify-between rounded-xl border border-border bg-card p-5 transition-all hover:border-border/80 hover:bg-card/80 hover:shadow-md"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                        project.status === "ready"
                          ? "bg-primary/10 text-primary"
                          : project.status === "processing"
                            ? "bg-amber-500/10 text-amber-500"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${statusDotClass(project.status)}`} />
                      {STATUS_LABEL[project.status as ProjectStatus] || project.status}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(project.updatedAt)}
                    </span>
                  </div>

                  <h3 className="mt-3 font-medium text-foreground group-hover:text-primary">
                    {project.name}
                  </h3>
                  {project.fileName && (
                    <p className="mt-1 truncate text-xs text-muted-foreground">
                      {project.fileName}
                    </p>
                  )}
                </div>

                <div className="mt-6 flex items-center justify-between border-t border-border/50 pt-3 text-xs text-muted-foreground">
                  <span>
                    {project.fileSize
                      ? `${(project.fileSize / (1024 * 1024)).toFixed(1)} MB`
                      : "Source ready"}
                  </span>
                  <span className="font-medium text-primary group-hover:underline">Open Scene &rarr;</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
