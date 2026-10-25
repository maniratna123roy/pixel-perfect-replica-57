import { X, Layers, Box, Info, Sliders } from "lucide-react";
import type { ModelStats, SourceMeta, ViewerMode, ViewerSettings } from "./view-types";
import { type Project } from "@/lib/demo-projects";
import { STAGES } from "@/lib/demo-projects";

export type InspectorState =
  | {
      kind: "upload";
      meta: SourceMeta | null;
      ready: boolean;
      note?: string;
    }
  | {
      kind: "processing";
      project: Project;
    }
  | {
      kind: "viewer";
      project: Project;
      stats: ModelStats | null;
      settings: ViewerSettings;
      mode: ViewerMode;
      selection: string | null;
    };

interface ProjectInspectorProps {
  state: InspectorState;
  onHide: () => void;
}

export function ProjectInspector({ state, onHide }: ProjectInspectorProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Inspector
        </span>
        <button
          onClick={onHide}
          aria-label="Close inspector"
          className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-4 text-xs">
        {state.kind === "upload" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-foreground">
              <Info className="h-4 w-4 text-primary" />
              <span className="font-medium">Capture Ingest</span>
            </div>

            {state.meta ? (
              <div className="rounded-lg border border-border bg-card p-3 space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">File</span>
                  <span className="truncate max-w-[140px] text-foreground font-mono">
                    {state.meta.name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Size</span>
                  <span className="text-foreground">
                    {(state.meta.size / (1024 * 1024)).toFixed(1)} MB
                  </span>
                </div>
                {state.meta.duration != null && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Duration</span>
                    <span className="text-foreground">{state.meta.duration.toFixed(1)}s</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-muted-foreground">
                Select a drone video file to inspect properties and start reconstruction.
              </p>
            )}

            {state.note && (
              <div className="rounded-lg border border-border/80 bg-muted/40 p-2.5 text-[11px] text-muted-foreground">
                {state.note}
              </div>
            )}
          </div>
        )}

        {state.kind === "processing" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-foreground">
              <Layers className="h-4 w-4 text-primary" />
              <span className="font-medium">Pipeline Progress</span>
            </div>

            <div className="rounded-lg border border-border bg-card p-3 space-y-2.5">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Project</span>
                <span className="font-medium text-foreground">{state.project.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Current Stage</span>
                <span className="text-primary font-medium">
                  {STAGES[state.project.stageIndex]?.label || "Processing"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Stage Index</span>
                <span className="text-foreground">
                  {state.project.stageIndex + 1} / {STAGES.length}
                </span>
              </div>
            </div>
          </div>
        )}

        {state.kind === "viewer" && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-foreground">
              <Box className="h-4 w-4 text-primary" />
              <span className="font-medium">Scene Properties</span>
            </div>

            <div className="rounded-lg border border-border bg-card p-3 space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Name</span>
                <span className="font-medium text-foreground">{state.project.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Mode</span>
                <span className="text-foreground capitalize">{state.mode}</span>
              </div>
            </div>

            {state.stats && (
              <div className="space-y-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Model Statistics
                </span>
                <div className="rounded-lg border border-border bg-card p-3 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Format</span>
                    <span className="text-foreground uppercase">{state.stats.format}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Meshes</span>
                    <span className="text-foreground">{state.stats.meshes}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Triangles</span>
                    <span className="text-foreground">{state.stats.triangles.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Vertices</span>
                    <span className="text-foreground">{state.stats.vertices.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            )}

            {state.selection && (
              <div className="rounded-lg border border-border bg-card p-3 space-y-1">
                <span className="text-[11px] text-muted-foreground">Selected Object</span>
                <p className="font-mono text-xs text-primary">{state.selection}</p>
              </div>
            )}

            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Sliders className="h-3.5 w-3.5" />
                <span className="text-[11px] font-semibold uppercase tracking-wider">
                  Viewport Active
                </span>
              </div>
              <div className="rounded-lg border border-border bg-card p-3 space-y-1.5 text-muted-foreground">
                <div className="flex justify-between">
                  <span>Grid</span>
                  <span className={state.settings.showGrid ? "text-primary" : ""}>
                    {state.settings.showGrid ? "Visible" : "Hidden"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Axes</span>
                  <span className={state.settings.showAxes ? "text-primary" : ""}>
                    {state.settings.showAxes ? "Visible" : "Hidden"}
                  </span>
                </div>
              </div>
            </div>

            {state.project.jobId && (
              <div className="space-y-2 pt-2 border-t border-border">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Export & Downloads
                </span>
                <div className="flex flex-col gap-1.5">
                  <a
                    href={`http://localhost:8000/v1/jobs/${state.project.jobId}/download/glb`}
                    download
                    className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
                  >
                    <span>Download 3D Scene (.GLB)</span>
                    <Box className="h-3.5 w-3.5" />
                  </a>
                  <a
                    href={`http://localhost:8000/v1/jobs/${state.project.jobId}/download/obj`}
                    download
                    className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <span>Textured Mesh (.OBJ Zip)</span>
                    <Layers className="h-3.5 w-3.5" />
                  </a>
                  <a
                    href={`http://localhost:8000/v1/jobs/${state.project.jobId}/download/report`}
                    download
                    className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <span>Processing Report (.JSON)</span>
                    <Info className="h-3.5 w-3.5" />
                  </a>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
