# System Changelog & Update Log

All changes made to the project during implementation are documented here chronologically.

---

### [2026-10-25] - System Architecture Initialization & Scaffolding

- **System Analysis**: Analyzed the complete 1,198-line `plan (1) (1).md` architecture document covering Buy, Build, and Hybrid reconstruction tracks, 3DGS/Mesh pipeline stages, Agent37 hosting, and client viewer specifications.
- **Directory Modularization**:
  - Organized distinct directories: `backend/`, `pipeline/`, `contracts/`, `storage/`, and `docs/`.
  - Kept frontend intact under `src/` to prevent disruption of existing UI components and Lovable integration.
- **Stage Contracts**:
  - Created [`contracts/stages.py`](file:///contracts/stages.py) specifying typed Pydantic models for `StageInput` and `StageOutput` adhering to Section 6.
- **Provider Architecture**:
  - Created [`backend/providers_base.py`](file:///backend/providers_base.py) defining `BaseReconstructionProvider`, `ReconstructionJobRequest`, and `ReconstructionJobResult` interfaces for interchangeable Buy/Build/Hybrid engines.
- **Pipeline Implementation**:
  - Created [`pipeline/workers.py`](file:///pipeline/workers.py) with ffmpeg-based frame extraction (S1), stride keyframe selection (S2), camera pose generation (S3-lite `frames.json`), and mock 3DGS splat generation (S5).
- **Backend API & Service**:
  - Created [`backend/main.py`](file:///backend/main.py) with FastAPI endpoints:
    - `GET /healthz` - Service health status
    - `POST /v1/captures/init` - Ingest capture session
    - `POST /v1/captures/{id}/upload` - Video file upload & pipeline job queuing
    - `GET /v1/jobs/{id}` - Job execution and stage progress monitoring
    - `GET /v1/jobs` - List all historical jobs
    - `/artifacts` - Static mounting to serve generated 3D splats directly to browser viewers
- **Documentation & Setup**:
  - Updated root [`README.md`](file:///README.md) with quick start guides and architecture breakdown.
  - Added [`docs/ARCHITECTURE.md`](file:///docs/ARCHITECTURE.md) documenting technical stages and requirements.

### [2026-10-25] - Frontend Component Integration & Build Fixes

- **Missing Dashboard Components Implemented**:
  - Created [`src/components/dashboard/ProjectsView.tsx`](file:///src/components/dashboard/ProjectsView.tsx) to manage project history, statuses, and quick start triggers.
  - Created [`src/components/dashboard/SettingsView.tsx`](file:///src/components/dashboard/SettingsView.tsx) allowing users to switch default camera views and toggle viewport grid/axes.
  - Created [`src/components/dashboard/ProjectInspector.tsx`](file:///src/components/dashboard/ProjectInspector.tsx) for displaying real-time video upload metadata, pipeline progress, and 3D model geometry statistics.
- **Three-stdlib Export Fix**:
  - Resolved invalid `clone` export from `three-stdlib` in [`src/components/dashboard/SceneViewer.tsx`](file:///src/components/dashboard/SceneViewer.tsx).
- **Build Verification**:
  - Ran `npx vite build` — client and SSR environments compile cleanly with 0 errors.

### [2026-10-25] - Polycam Integration, Backend Connectivity & 3D Model Rendering

- **Root Cause Analysis of 500 Error & Green Wavy Mesh**:
  1. The client was previously running purely on local simulated timers without ever sending the video to the backend API, resulting in no terminal logs.
  2. In [`src/components/dashboard/SceneViewer.tsx`](file:///src/components/dashboard/SceneViewer.tsx#L409), `SampleModel` called `skeletonClone(scene)` which threw `ReferenceError: skeletonClone is not defined`.
  3. The `GLTFBoundary` caught this runtime exception and automatically fell back to `ProceduralSample`, which renders the green procedural sinusoidal terrain plane.
- **Polycam Provider Implementation**:
  - Implemented [`backend/polycam_provider.py`](file:///backend/polycam_provider.py) supporting the Buy Track:
    - Automates packaging of keyframes into `keyframes/images/*.jpg` and root `frames.json`.
    - Handles capture creation (`POST /v1/captures`), `session.zip` upload, and confirmation (`POST /v1/captures/{id}/upload/confirm`).
    - Provides mock fallback with preloaded models when `POLYCAM_API_KEY` is not present in environment variables.
- **Backend Video Ingest & Logging**:
  - Updated [`backend/main.py`](file:///backend/main.py) to log every stage: `[PIPELINE START]`, `S0_INGEST`, `S1_EXTRACT` (ffmpeg), `S2_SELECT`, `S3_POSES`, and `S5_RECONSTRUCT` with Polycam.
  - Updated [`src/components/dashboard/DashboardShell.tsx`](file:///src/components/dashboard/DashboardShell.tsx) to send videos via `multipart/form-data` to `${API_BASE_URL}/v1/captures/...` on scene generation.
- **3D Viewer Object Cloning**:
  - Replaced the missing clone function with native Three.js `scene.clone(true)`, ensuring [`public/models/sample-scene.glb`](file:///public/models/sample-scene.glb) loads the actual building/geometry instead of the fallback terrain.
