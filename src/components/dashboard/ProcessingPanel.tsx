import { AlertTriangle, ArrowLeft, CheckCircle2, Circle, Loader2, Play } from "lucide-react";
import { STAGES, type Project } from "@/lib/demo-projects";

interface ProcessingPanelProps {
  project: Project;
  exploreGate: boolean;
  onExplore: () => void;
  onCancel: () => void;
  onRetry: () => void;
  onBackToProjects: () => void;
}

export function ProcessingPanel({
  project,
  exploreGate,
  onExplore,
  onCancel,
  onRetry,
  onBackToProjects,
}: ProcessingPanelProps) {
  const stageIndex = project.stageIndex;
  const overall = ((stageIndex + project.stageProgress) / STAGES.length) * 100;
  const stage = STAGES[Math.min(stageIndex, STAGES.length - 1)];
  const fallbackMessage =
    stage.messages[
      Math.min(
        Math.floor(project.stageProgress * stage.messages.length),
        stage.messages.length - 1,
      )
    ];
  const message = project.stageMessage || fallbackMessage;

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto px-5 py-10 sm:py-16">
      <div className="w-full max-w-xl">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-medium tracking-tight text-foreground sm:text-4xl">
            Reconstructing your scene
          </h1>
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-400">
            Photogrammetry Pipeline
          </span>
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          Your footage is moving through the reconstruction pipeline.
        </p>

        {project.status === "failed" ? (
          <div className="mt-8 rounded-xl border border-destructive/40 bg-destructive/10 p-4">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium text-foreground">Processing stopped</p>
                <p className="mt-1 text-xs text-muted-foreground">{project.error}</p>
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2.5">
              <button onClick={onRetry} className="btn-primary-solid px-4 py-2 text-sm">
                <Play className="h-3.5 w-3.5" aria-hidden="true" /> Retry
              </button>
              <button onClick={onBackToProjects} className="btn-glass px-4 py-2 text-sm">
                <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" /> Return to Projects
              </button>
            </div>
          </div>
        ) : exploreGate || project.status === "ready" ? (
          <div className="mt-8 rounded-xl border border-border bg-panel p-5">
            <div className="flex items-center gap-2.5">
              <CheckCircle2 className="h-5 w-5 text-primary" aria-hidden="true" />
              <p className="text-sm font-medium text-foreground">Pipeline finished</p>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Photogrammetric reconstruction complete. Your textured 3D scene has been generated and is ready to inspect.
            </p>
            <button onClick={onExplore} className="btn-primary-solid mt-4">
              <Play className="h-4 w-4" aria-hidden="true" /> Explore 3D Scene
            </button>
          </div>
        ) : (
          <>
            <div className="mt-8">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>
                  {stage.label}
                  <span className="ml-2 text-foreground">{Math.round(overall)}%</span>
                </span>
                <span>In progress</span>
              </div>
              <div
                className="mt-2 h-1.5 overflow-hidden rounded-full bg-accent"
                role="progressbar"
                aria-valuenow={Math.round(overall)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Overall reconstruction progress"
              >
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-200 ease-linear"
                  style={{ width: `${overall}%` }}
                />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">{message}</p>
            </div>

            <ol className="mt-8 divide-y divide-border rounded-xl border border-border bg-panel">
              {STAGES.map((s, i) => {
                const done = i < stageIndex;
                const active = i === stageIndex;
                return (
                  <li
                    key={s.key}
                    className={`flex items-center gap-3 px-4 py-3 text-sm ${
                      active ? "bg-primary/5" : ""
                    }`}
                    aria-current={active ? "step" : undefined}
                  >
                    {done ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    ) : active ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" aria-hidden="true" />
                    ) : (
                      <Circle className="h-4 w-4 shrink-0 text-muted-foreground/40" aria-hidden="true" />
                    )}
                    <span
                      className={
                        done
                          ? "text-foreground"
                          : active
                            ? "font-medium text-foreground"
                            : "text-muted-foreground"
                      }
                    >
                      {s.label}
                    </span>
                    {active && (
                      <span className="ml-auto text-xs text-muted-foreground">
                        {Math.round(project.stageProgress * 100)}%
                      </span>
                    )}
                  </li>
                );
              })}
            </ol>

            <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
              <button
                onClick={onCancel}
                className="rounded-full border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-destructive/50 hover:text-destructive-foreground"
              >
                Cancel reconstruction
              </button>
              <p className="text-xs text-muted-foreground">
                Footage is analyzed via FFmpeg frame extraction, blur filtering, and 3D photogrammetry.
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
