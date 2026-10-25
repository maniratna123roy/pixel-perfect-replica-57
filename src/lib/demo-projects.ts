/**
 * Demonstration-mode project store.
 *
 * There is no reconstruction backend connected, so projects persist as
 * lightweight metadata in localStorage. Large video blobs are never stored.
 * Processing is simulated and always labeled as demo mode in the UI.
 */

export type ProjectStatus = "draft" | "processing" | "ready" | "failed";

export interface Project {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
  status: ProjectStatus;
  fileName: string | null;
  fileSize: number | null;
  fileDuration: number | null;
  /** Index into STAGES (0-6). */
  stageIndex: number;
  /** Progress within the current stage, 0..1. */
  stageProgress: number;
  error: string | null;
}

export interface PipelineStage {
  key: string;
  label: string;
  duration: number;
  messages: string[];
}

export const STAGES: PipelineStage[] = [
  {
    key: "uploaded",
    label: "Footage uploaded",
    duration: 0.4,
    messages: ["Source video registered for this session."],
  },
  {
    key: "extraction",
    label: "Frame extraction",
    duration: 4,
    messages: ["Decoding source video.", "Extracting keyframes for matching."],
  },
  {
    key: "matching",
    label: "Feature matching",
    duration: 5,
    messages: ["Detecting features across frames.", "Matching keypoints between views."],
  },
  {
    key: "poses",
    label: "Camera pose estimation",
    duration: 4,
    messages: ["Estimating camera positions.", "Solving camera trajectories."],
  },
  {
    key: "reconstruction",
    label: "3D reconstruction",
    duration: 6,
    messages: ["Building scene geometry.", "Densifying the reconstruction."],
  },
  {
    key: "optimization",
    label: "Scene optimization",
    duration: 3,
    messages: ["Optimizing scene geometry.", "Preparing the scene for viewing."],
  },
  {
    key: "ready",
    label: "Ready to explore",
    duration: 0.4,
    messages: ["Reconstruction pipeline finished."],
  },
];

const STORAGE_KEY = "birdseye.projects.v1";

export function loadProjects(): Project[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Project[];
    // Simulated processing never survives a page reload — mark it honestly.
    return parsed.map((p) =>
      p.status === "processing"
        ? {
            ...p,
            status: "failed",
            error:
              "Processing was interrupted when the previous session ended (demo mode).",
          }
        : p,
    );
  } catch {
    return [];
  }
}

export function saveProjects(projects: Project[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  } catch {
    // Storage full or unavailable — demo state simply won't persist.
  }
}

export function createProject(meta: {
  name: string;
  fileName: string;
  fileSize: number;
  fileDuration: number | null;
}): Project {
  const now = Date.now();
  return {
    id: `proj-${now}-${Math.random().toString(36).slice(2, 8)}`,
    name: meta.name,
    createdAt: now,
    updatedAt: now,
    status: "processing",
    fileName: meta.fileName,
    fileSize: meta.fileSize,
    fileDuration: meta.fileDuration,
    stageIndex: 0,
    stageProgress: 0,
    error: null,
  };
}

export function formatBytes(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDuration(seconds: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) return "—";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDate(ts: number): string {
  return new Date(ts).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
