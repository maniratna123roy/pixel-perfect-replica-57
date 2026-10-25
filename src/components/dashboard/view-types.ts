export type DashboardView = "new" | "projects" | "project" | "settings";
export type WorkspaceState = "upload" | "processing" | "viewer";

export type ViewerMode = "orbit" | "pan" | "zoom" | "select";
export type ViewPreset = "perspective" | "top" | "front" | "side";

export interface ViewerSettings {
  defaultView: ViewPreset;
  showGrid: boolean;
  showAxes: boolean;
}

export interface ModelStats {
  format: string;
  meshes: number;
  triangles: number;
  vertices: number;
}

export interface SceneBounds {
  center: [number, number, number];
  size: [number, number, number];
}

export interface ViewRequest {
  kind: ViewPreset | "reset" | "fit";
  nonce: number;
}

export const DEFAULT_VIEWER_SETTINGS: ViewerSettings = {
  defaultView: "perspective",
  showGrid: true,
  showAxes: false,
};

const SETTINGS_KEY = "birdseye.settings.v1";

export function loadViewerSettings(): ViewerSettings {
  if (typeof window === "undefined") return DEFAULT_VIEWER_SETTINGS;
  try {
    const raw = window.localStorage.getItem(SETTINGS_KEY);
    if (!raw) return DEFAULT_VIEWER_SETTINGS;
    return { ...DEFAULT_VIEWER_SETTINGS, ...(JSON.parse(raw) as Partial<ViewerSettings>) };
  } catch {
    return DEFAULT_VIEWER_SETTINGS;
  }
}

export function saveViewerSettings(settings: ViewerSettings): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Ignore — preferences simply won't persist.
  }
}
