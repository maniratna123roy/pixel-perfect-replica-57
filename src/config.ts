/**
 * Central configuration for external assets and integration points.
 * Replace these values to point Bird's Eye at real footage or a real
 * reconstruction backend without touching component code.
 */

/** Full-bleed hero footage on the landing page (aerial city at night). */
export const HERO_VIDEO_SRC =
  "https://videos.pexels.com/video-files/8953983/8953983-hd_1920_1080_24fps.mp4";

/**
 * Reconstruction asset loaded by the 3D viewer.
 * When a real reconstruction backend exists, point this at the generated
 * GLB/GLTF for the selected project. An empty string disables asset loading
 * and the viewer falls back to the clearly labeled procedural sample scene.
 */
export const SAMPLE_MODEL_URL = "";
export const API_BASE_URL =
  typeof window !== "undefined"
    ? (window as unknown as { __VITE_API_BASE_URL?: string }).__VITE_API_BASE_URL || "http://localhost:8001"
    : "http://localhost:8001";

/** Accepted source video formats. */
export const ACCEPTED_VIDEO_EXTENSIONS = ["mp4", "mov", "webm"] as const;

export const ACCEPTED_VIDEO_MIME = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
] as const;

export function isAcceptedVideoFile(file: File): boolean {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return (
    (ACCEPTED_VIDEO_MIME as readonly string[]).includes(file.type) ||
    (ACCEPTED_VIDEO_EXTENSIONS as readonly string[]).includes(
      ext as (typeof ACCEPTED_VIDEO_EXTENSIONS)[number],
    )
  );
}
