import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Menu } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { UploadPanel } from "./UploadPanel";
import { ProcessingPanel } from "./ProcessingPanel";
import { ProjectsView } from "./ProjectsView";
import { SettingsView } from "./SettingsView";
import { ProjectInspector } from "./ProjectInspector";
import {
  createProject,
  loadProjects,
  saveProjects,
  STAGES,
  type Project,
} from "@/lib/demo-projects";
import {
  loadViewerSettings,
  saveViewerSettings,
  type DashboardView,
  type ModelStats,
  type SourceMeta,
  type ViewerMode,
  type ViewerSettings,
  type WorkspaceState,
} from "./view-types";

const SceneViewer = lazy(() =>
  import("./SceneViewer").then((m) => ({ default: m.SceneViewer })),
);

import { lazy, Suspense } from "react";

export function DashboardShell() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [view, setView] = useState<DashboardView>("new");
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [source, setSource] = useState<{ file: File; meta: SourceMeta } | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceState>("upload");
  const [exploreGate, setExploreGate] = useState(false);
  const [runKey, setRunKey] = useState(0);
  const [settings, setSettings] = useState<ViewerSettings>(loadViewerSettings());
  const [modelStats, setModelStats] = useState<ModelStats | null>(null);
  const [viewerMode, setViewerMode] = useState<ViewerMode>("orbit");
  const [selection, setSelection] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showInspector, setShowInspector] = useState(true);

  // Load persisted demo state once on the client.
  useEffect(() => {
    setProjects(loadProjects());
    setLoaded(true);
  }, []);

  const activeProject = useMemo(
    () => projects.find((p) => p.id === activeProjectId) ?? null,
    [projects, activeProjectId],
  );

  const projectsRef = useRef(projects);
  projectsRef.current = projects;
  const activeIdRef = useRef(activeProjectId);
  activeIdRef.current = activeProjectId;
  const lastSavedStageRef = useRef(-1);

  const handleFileSelected = useCallback((file: File) => {
    setSource({
      file,
      meta: { name: file.name, size: file.size, duration: null },
    });
  }, []);

  const handleDuration = useCallback((seconds: number) => {
    setSource((prev) =>
      prev && prev.meta.duration == null
        ? { ...prev, meta: { ...prev.meta, duration: seconds } }
        : prev,
    );
  }, []);

  const handleRemoveFile = useCallback(() => setSource(null), []);

  const persist = useCallback((next: Project[]) => {
    setProjects(next);
    saveProjects(next);
  }, []);

  const generateScene = useCallback(() => {
    const src = source;
    if (!src) return;
    const existingId = activeIdRef.current;
    const existing = projectsRef.current.find((p) => p.id === existingId);

    if (existing && existing.status === "draft") {
      persist(
        projectsRef.current.map((p) =>
          p.id === existing.id
            ? {
                ...p,
                status: "processing",
                fileName: src.meta.name,
                fileSize: src.meta.size,
                fileDuration: src.meta.duration,
                stageIndex: 0,
                stageProgress: 0,
                error: null,
                updatedAt: Date.now(),
              }
            : p,
        ),
      );
    } else {
      const name = src.meta.name.replace(/\.[^.]+$/, "") || "Untitled scene";
      const project = createProject({
        name,
        fileName: src.meta.name,
        fileSize: src.meta.size,
        fileDuration: src.meta.duration,
      });
      persist([...projectsRef.current, project]);
      setActiveProjectId(project.id);
    }
    lastSavedStageRef.current = -1;
    setExploreGate(false);
    setSelection(null);
    setModelStats(null);
    setRunKey((k) => k + 1);
    setView("project");
    setWorkspace("processing");
  }, [source, persist]);

  const handleProcessingUpdate = useCallback(
    (stage: number, progress: number) => {
      const id = activeIdRef.current;
      if (!id) return;
      const next = projectsRef.current.map((p) =>
        p.id === id
          ? { ...p, stageIndex: stage, stageProgress: progress, updatedAt: Date.now() }
          : p,
      );
      setProjects(next);
      if (stage !== lastSavedStageRef.current) {
        lastSavedStageRef.current = stage;
        saveProjects(next);
      }
    },
    [],
  );

  const handleProcessingComplete = useCallback(() => {
    const id = activeIdRef.current;
    if (!id) return;
    const next = projectsRef.current.map((p) =>
      p.id === id
        ? {
            ...p,
            status: "ready",
            stageIndex: STAGES.length - 1,
            stageProgress: 1,
            error: null,
            updatedAt: Date.now(),
          }
        : p,
    );
    persist(next);
    setExploreGate(true);
  }, [persist]);

  const handleProcessingCancel = useCallback(() => {
    const id = activeIdRef.current;
    if (!id) return;
    const next = projectsRef.current.map((p) =>
      p.id === id
        ? { ...p, status: "draft", stageIndex: 0, stageProgress: 0, updatedAt: Date.now() }
        : p,
    );
    persist(next);
    setExploreGate(false);
    setWorkspace("upload");
  }, [persist]);

  const handleRetry = useCallback(() => {
    const id = activeIdRef.current;
    if (!id) return;
    const next = projectsRef.current.map((p) =>
      p.id === id
        ? {
            ...p,
            status: "processing",
            stageIndex: 0,
            stageProgress: 0,
            error: null,
            updatedAt: Date.now(),
          }
        : p,
    );
    persist(next);
    lastSavedStageRef.current = -1;
    setExploreGate(false);
    setRunKey((k) => k + 1);
    setWorkspace("processing");
  }, [persist]);

  const handleExplore = useCallback(() => setWorkspace("viewer"), []);

  const openProject = useCallback((id: string) => {
    setActiveProjectId(id);
    setSidebarOpen(false);
    setExploreGate(false);
    setSelection(null);
    setModelStats(null);
    setSource(null);
    const project = projectsRef.current.find((p) => p.id === id);
    setView("project");
    if (!project) return;
    setWorkspace(
      project.status === "ready"
        ? "viewer"
        : project.status === "draft"
          ? "upload"
          : "processing",
    );
  }, []);

  const newReconstruction = useCallback(() => {
    setView("new");
    setActiveProjectId(null);
    setSource(null);
    setExploreGate(false);
    setWorkspace("upload");
    setSidebarOpen(false);
  }, []);

  const updateSettings = useCallback((partial: Partial<ViewerSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...partial };
      saveViewerSettings(next);
      return next;
    });
  }, []);

  // Simulated reconstruction pipeline (demo mode). Runs in the shell so the
  // pipeline keeps moving even if the user navigates between views.
  const activeStatus = activeProject?.status ?? null;
  useEffect(() => {
    if (activeStatus !== "processing") return;
    let cancelled = false;
    let stage = 0;
    let progress = 0;
    const tick = () => {
      if (cancelled) return;
      progress += 0.2 / STAGES[stage].duration;
      if (progress >= 1) {
        stage += 1;
        progress = 0;
        if (stage >= STAGES.length) {
          window.clearInterval(id);
          handleProcessingComplete();
          return;
        }
      }
      handleProcessingUpdate(stage, progress);
    };
    const id = window.setInterval(tick, 200);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [activeProjectId, activeStatus, runKey, handleProcessingUpdate, handleProcessingComplete]);

  const viewerProjectName = activeProject?.name ?? "Untitled scene";

  const workspaceContent = (() => {
    if (view === "projects") {
      return (
        <ProjectsView
          projects={projects}
          onOpenProject={openProject}
          onNew={newReconstruction}
        />
      );
    }
    if (view === "settings") {
      return <SettingsView settings={settings} onChange={updateSettings} />;
    }
    if (view === "new" || workspace === "upload") {
      return (
        <UploadPanel
          meta={source?.meta ?? null}
          hasFile={!!source}
          reselectNote={
            view === "project" && activeProject?.status === "draft" && !source
              ? "Demo projects keep only metadata — select the video again to continue."
              : undefined
          }
          onFileSelected={handleFileSelected}
          onDuration={handleDuration}
          onRemove={handleRemoveFile}
          onGenerate={generateScene}
        />
      );
    }
    if (workspace === "processing" && activeProject) {
      return (
        <ProcessingPanel
          project={activeProject}
          exploreGate={exploreGate}
          onExplore={handleExplore}
          onCancel={handleProcessingCancel}
          onRetry={handleRetry}
          onBackToProjects={() => setView("projects")}
        />
      );
    }
    if (workspace === "viewer") {
      return (
        <Suspense fallback={<div className="min-h-full bg-viewport" />}>
          <SceneViewer
            projectName={viewerProjectName}
            settings={settings}
            onSettingsChange={updateSettings}
            onStats={setModelStats}
            onModeChange={setViewerMode}
            onSelect={setSelection}
          />
        </Suspense>
      );
    }
    return null;
  })();

  const inspectorState = (() => {
    if (view === "new" || workspace === "upload") {
      return {
        kind: "upload" as const,
        meta: source?.meta ?? null,
        ready: !!source,
        note:
          view === "project" && activeProject?.status === "draft" && !source
            ? "Demo projects keep only metadata — select the video again to continue."
            : undefined,
      };
    }
    if (workspace === "processing" && activeProject) {
      return { kind: "processing" as const, project: activeProject };
    }
    if (workspace === "viewer" && activeProject) {
      return {
        kind: "viewer" as const,
        project: activeProject,
        stats: modelStats,
        settings,
        mode: viewerMode,
        selection,
      };
    }
    return null;
  })();

  if (!loaded) {
    return <div className="h-dvh bg-background" />;
  }

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <div className="hidden lg:flex">
        <Sidebar
          view={view}
          projects={projects}
          activeProjectId={activeProjectId}
          onNavigate={(v) => (v === "new" ? newReconstruction() : setView(v))}
          onOpenProject={openProject}
        />
      </div>

      {/* Mobile sidebar */}
      {sidebarOpen && (
        <div className="lg:hidden">
          <button
            className="fixed inset-0 z-30 bg-black/60"
            aria-label="Close navigation overlay"
            onClick={() => setSidebarOpen(false)}
          />
          <Sidebar
            mobile
            view={view}
            projects={projects}
            activeProjectId={activeProjectId}
            onNavigate={(v) => {
              v === "new" ? newReconstruction() : setView(v);
              setSidebarOpen(false);
            }}
            onOpenProject={openProject}
            onClose={() => setSidebarOpen(false)}
          />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-3 lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open navigation"
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="text-[15px] font-medium text-foreground">bird&rsquo;s eye</span>
        </header>

        <div className="flex min-h-0 flex-1">
          <main className="relative min-w-0 flex-1">{workspaceContent}</main>

          {!showInspector && (
            <button
              onClick={() => setShowInspector(true)}
              aria-label="Show inspector panel"
              className="absolute right-0 top-1/2 z-10 hidden -translate-y-1/2 rounded-l-md border border-border border-r-0 bg-panel px-1 py-3 text-muted-foreground hover:text-foreground xl:block"
            >
              &lsaquo;
            </button>
          )}

          {showInspector && inspectorState && (
            <aside className="hidden w-[280px] shrink-0 flex-col overflow-y-auto border-l border-border bg-sidebar/60 xl:flex">
              <ProjectInspector
                state={inspectorState}
                onHide={() => setShowInspector(false)}
              />
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
