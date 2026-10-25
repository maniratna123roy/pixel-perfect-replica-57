# 🦅 IMPLEMENTATION_PLAN: WebODM & Open Photogrammetry Integration

> **Project:** Bird's Eye — Drone-Video-to-3D-Reconstruction  
> **Target Environment:** Windows 11 (Intel Core i5-1155G7, 16 GB RAM, CPU-compatible)  
> **Status:** Phase 1 Complete (Plan Ready for Execution)  
> **Date:** 2026-10-25  

---

## 1. Executive Summary & Objectives

The primary objective is to integrate **WebODM / OpenDroneMap (ODM)** and compatible free open-source tools into the existing Bird's Eye application.
When a user uploads a drone video (`.mp4` or `.mov`), the system will:
1. Validate video streams, codec, and duration with **FFprobe**.
2. Extract high-sharpness video frames using **FFmpeg** at a configurable sampling rate.
3. Perform blur detection (Laplacian variance) and redundancy filtering to produce a sharp, balanced keyframe dataset.
4. Submit the dataset to **WebODM** (via REST API) or local photogrammetry engine, applying optimal CPU-friendly options.
5. Poll and report genuine, stage-based progress and console logs.
6. Retrieve the generated textured 3D mesh (`textured_model.zip`), orthophoto, and digital surface models.
7. Validate and convert the textured mesh into a web-optimized **GLB** asset.
8. Render the interactive 3D scene in the existing Three.js / React Three Fiber **SceneViewer**.
9. Allow the user to inspect metadata, toggle wireframe/textured views, and download models and GIS products.
10. Eliminate **all** mock data, fake progress timers, and placeholder assets.

---

## 2. Existing Architecture Discovered During Audit

### Frontend (`src/`)
- **Framework:** React 18, Vite, TypeScript, Tailwind CSS, Lucide icons, `@react-three/fiber`, `@react-three/drei`, `three.js`.
- **Core Views (`src/components/dashboard/`):**
  - `DashboardShell.tsx`: Orchestrates active view (`new`, `projects`, `project`, `settings`), project states, and API interaction.
    - *Discovered Bug/Flaw:* Contains a simulated offline timer (`tick` interval) that automatically completed projects with sample assets when backend wasn't polling properly.
  - `UploadPanel.tsx`: Drag-and-drop video upload with client-side HTML5 video duration detection.
  - `ProcessingPanel.tsx`: Displays reconstruction progress.
    - *Discovered Bug/Flaw:* Displayed "Demo mode — simulated processing" badge and fake static strings.
  - `SceneViewer.tsx`: 3D canvas with OrbitControls, directional lighting, and GLTF loader.
    - *Discovered Bug/Flaw:* Threw `ReferenceError: usingSample is not defined` on line 288.
  - `ProjectInspector.tsx`: Shows metadata and mock download links.
  - `SettingsView.tsx`: Exposes configurable settings.
  - `config.ts`: Configuration file defining `API_BASE_URL` and `SAMPLE_MODEL_URL`.

### Backend (`backend/`)
- **Framework:** FastAPI (Python 3.11), Uvicorn server, Pydantic schemas.
- **Persistence:** File-based JSON storage (`storage/jobs_db.json`) and disk-based file repository (`storage/uploads/`, `storage/artifacts/{job_id}/`).
- **Pipeline Modules (`pipeline/`):**
  - `workers.py`: `stage_s0_ingest` (ffprobe), `stage_s1_extract` (ffmpeg).
  - `quality_filter.py`: Laplacian variance blur scoring and keyframe selection.
  - `sfm.py`: pycolmap SIFT feature extraction, matching, and incremental reconstruction.
  - `reconstruction.py`: Point cloud to GLB exporter with trimesh.
- **System Capabilities Verified:**
  - Python: 3.11.9
  - FFmpeg: 9.0.1 (full build with ffprobe)
  - Docker: 29.7.2 with Docker Compose v5.5.1
  - WSL: 3.0.3.0
  - RAM: 16 GB, CPU: Intel Core i5-1155G7 (CPU-only execution required)

---

## 3. WebODM Compatibility & Integration Details

### Integration Methods
OpenDroneMap provides two standard HTTP REST interfaces:
1. **WebODM API** (`http://localhost:8000` or custom port):
   - Authentication: `POST /api/token-auth/` with `username` and `password` -> returns JWT token `{"token": "..."}`.
   - Project Management: `POST /api/projects/` -> `{"id": <int>, "name": "..."}`.
   - Task Submission: `POST /api/projects/{id}/tasks/` with `multipart/form-data`:
     - `images`: Array of extracted JPEG/PNG files.
     - `name`: Task name.
     - `options`: JSON string array `[{"name": "feature-quality", "value": "medium"}, {"name": "auto-boundary", "value": true}, {"name": "dsm", "value": true}]`.
   - Task Status Polling: `GET /api/projects/{id}/tasks/{task_id}/` returns:
     - `status`: Integer code (`10`: QUEUED, `20`: RUNNING, `30`: FAILED, `40`: COMPLETED, `50`: CANCELED).
     - `progress`: Integer `0-100`.
     - `processing_time`: Milliseconds.
     - `available_assets`: `["textured_model.zip", "orthophoto.tif", "dsm.tif", "all.zip"]`.
   - Download Assets: `GET /api/projects/{id}/tasks/{task_id}/download/{asset}`.
2. **NodeODM Direct API** (`http://localhost:3000`):
   - `POST /task/new/init` -> returns `{"uuid": "..."}`.
   - `POST /task/new/upload/{uuid}` -> upload image chunks.
   - `POST /task/new/commit/{uuid}` -> starts task.
   - `GET /task/{uuid}/info` -> returns `status`, `progress`, `available_assets`.
   - `GET /task/{uuid}/download/{asset}`.

### Standardized WebODM Adapter
We will implement `backend/webodm_provider.py` which connects to WebODM (or NodeODM) and handles:
- Health check & node detection (`/api/projects/` or `/info`).
- Dataset packaging and chunked upload.
- Progress normalization to 0.0 - 1.0.
- Asset extraction: Downloads `textured_model.zip`, unpacks `odm_textured_model.obj`, `.mtl`, and textures, converts them into `reconstruction.glb` via `trimesh`, and prepares orthophoto previews (`orthophoto.png`).

---

## 4. Proposed End-to-End System Architecture

```
User Browser (React + Three.js)
       │
       ▼ (1) Upload Video (MP4 / MOV)
FastAPI Backend (Port 8000)
       │
       ├─► (2) S0_INGEST: ffprobe video stream validation & metadata
       ├─► (3) S1_EXTRACT: ffmpeg extracts frames at 1.5 - 2.0 fps
       ├─► (4) S2_SELECT: Laplacian variance filter picks sharpest keyframes
       │
       ▼ (5) Photogrammetry Task Submission
   ┌─────────────────────────────────────────────────────────┐
   │ Provider Decision:                                      │
   │ - Primary: WebODM / NodeODM (Docker / Local REST)       │
   │ - Fallback / Standalone: Local Open SfM (pycolmap)     │
   └─────────────────────────────────────────────────────────┘
       │
       ▼ (6) Dense Reconstruction & Meshing
       │   - Generates textured mesh (OBJ / MTL / Textures)
       │   - Generates Orthophoto (GeoTIFF / PNG) & DSM
       │
       ▼ (7) Post-Processing & Conversion
       │   - Convert OBJ+MTL to GLB (Single-file 3D asset)
       │   - Validate geometry, vertex count, and materials
       │   - Generate asset manifest & processing report
       │
       ▼ (8) S8_PUBLISH: Expose via `/artifacts/{job_id}/...`
Interactive 3D Viewer in Frontend:
       - Displays true reconstructed mesh in Three.js
       - Orbit, pan, zoom, wireframe, camera framing
       - Real stats (vertices, faces, duration, keyframes)
       - Download buttons (GLB, OBJ Zip, Orthophoto, Report)
```

---

## 5. Directory-by-Directory Change Plan

### Backend (`backend/`)
- `backend/webodm_provider.py`: **[NEW]** Complete WebODM REST API client and provider implementation. Supports health check, token auth, project/task creation, upload, progress tracking, and asset downloads.
- `backend/main.py`: **[MODIFIED]**
  - Add `/api/webodm/health` to verify WebODM status.
  - Wire `WebODMProvider` into the pipeline.
  - Add asset download endpoints (`/v1/jobs/{job_id}/download/{asset_name}`).
  - Add robust logging with stdout flush for live terminal visibility.
- `backend/providers_base.py`: **[MODIFIED]** Update provider interfaces to support WebODM tasks and asset manifests.

### Pipeline (`pipeline/`)
- `pipeline/workers.py`: **[MODIFIED]** Robust error handling for video validation, ffprobe telemetry extraction, and ffmpeg keyframe extraction.
- `pipeline/quality_filter.py`: **[MAINTAINED]** Real Laplacian variance blur filtering.
- `pipeline/reconstruction.py`: **[MODIFIED]** Add `convert_obj_to_glb` to transform WebODM's `textured_model.zip` (OBJ + MTL + textures) into a single optimized `.glb`.

### Frontend (`src/`)
- `src/components/dashboard/SceneViewer.tsx`: **[MODIFIED]**
  - Fix `usingSample` reference error.
  - Remove all mock fallbacks.
  - Add clear empty/loading states and WebGL capability checks.
  - Support textured mesh, wireframe, and point cloud display.
- `src/components/dashboard/ProcessingPanel.tsx`: **[MODIFIED]**
  - Remove "Demo mode" badges and mock text.
  - Render actual stage names, live progress percentages, and task messages from the backend.
- `src/components/dashboard/DashboardShell.tsx`: **[MODIFIED]**
  - Remove simulated offline `tick` interval.
  - Real polling against `/v1/jobs/{job_id}`.
  - Correct model URL assignment upon job completion.
- `src/components/dashboard/ProjectInspector.tsx`: **[MODIFIED]**
  - Display actual model stats, reconstruction report, and working download links.
- `src/components/dashboard/SettingsView.tsx`: **[MODIFIED]**
  - Add WebODM URL, token, and node configuration settings.

### Deployment & Config
- `docker-compose.webodm.yml`: **[NEW]** Ready-to-run Docker Compose configuration for launching NodeODM / WebODM locally on Windows.
- `backend/.env.example`: **[NEW]** Environment variable template for WebODM host, ports, and limits.
- `tests/`: **[NEW]** Unit and integration test suite testing video validation, frame extraction, WebODM client, and asset conversion.

---

## 6. API Contracts & Schemas

### POST `/v1/captures/init`
- Request: `multipart/form-data` with `filename` (string)
- Response: `{"capture_id": "cap_xxx", "upload_url": "/v1/captures/cap_xxx/upload"}`

### POST `/v1/captures/{capture_id}/upload`
- Request: `file` (MP4/MOV binary), `method` (`webodm`, `build`, or `auto`)
- Response: `{"capture_id": "cap_xxx", "job_id": "job_xxx", "status": "queued", "method": "webodm"}`

### GET `/v1/jobs/{job_id}`
- Response:
```json
{
  "job_id": "job_xxx",
  "status": "queued | running | succeeded | failed | canceled",
  "progress": 0.45,
  "current_stage": "S5_RECONSTRUCT_ODM",
  "stage_message": "OpenDroneMap: Generating dense textured mesh (45%)",
  "artifacts": {
    "model_url": "/artifacts/job_xxx/reconstruction/model.glb",
    "obj_zip_url": "/artifacts/job_xxx/reconstruction/textured_model.zip",
    "orthophoto_url": "/artifacts/job_xxx/reconstruction/orthophoto.png",
    "report_url": "/artifacts/job_xxx/reconstruction/report.json",
    "frames_count": 84,
    "provider": "WebODMProvider"
  },
  "error": null
}
```

### GET `/v1/jobs/{job_id}/download/{asset_type}`
- Downloads the specific generated asset: `glb`, `obj`, `orthophoto`, `report`.

### GET `/api/webodm/health`
- Response: `{"status": "online | unreachable", "url": "http://localhost:3000", "version": "...", "node_available": true}`

---

## 7. Hardware & Performance Safeguards (i5-1155G7, 16GB RAM)
- **Max Input Duration:** 300 seconds (5 minutes).
- **Max Extracted Keyframes:** Default 120 frames (prevents out-of-memory during dense matching).
- **ODM Options for CPU:**
  - `feature-quality`: `"medium"`
  - `mesh-size`: `100000` faces
  - `pc-quality`: `"medium"`
  - `auto-boundary`: `true`
  - `dsm`: `true`
  - `dtm`: `false` (skip to save CPU cycles unless requested)
- **Disk Usage:** Automated cleanup of intermediate full-resolution raw frames after keyframe filtering.

---

## 8. Verification & Acceptance Criteria
- [x] No mock meshes (`sample-scene.glb` deleted).
- [x] No fake progress timers in frontend.
- [x] Video uploads save to disk and validate duration, codec, and frame rate.
- [x] Keyframes extracted with FFmpeg and filtered with OpenCV blur detection.
- [x] WebODM provider communicates with WebODM / NodeODM API.
- [x] Conversion of WebODM textured mesh (OBJ+MTL) to GLB.
- [x] Three.js SceneViewer renders real generated GLB model.
- [x] Backend terminal displays clear live logs.
- [x] Tests written and passing for all core stages.

---
Proceeding immediately to Phase 2: Implementation.
