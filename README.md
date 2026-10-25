# Drone Video → Interactive 3D Architecture & Execution Plan

This repository contains the full system for converting raw drone video captures into interactive, photorealistic 3D Gaussian Splats and textured meshes, powered by an agentic orchestration layer.

---

## 1. Directory Structure

The project has been organized into modular workspaces:

```
├── frontend/ (Current React + TanStack Start UI in src/)
│   ├── src/components/dashboard/  -> Dashboard, upload flow, 3D viewer
│   ├── src/components/landing/    -> Landing page
│   └── src/routes/                -> Router definitions
├── backend/                       -> FastAPI backend & orchestration API
│   ├── main.py                    -> API endpoints (/v1/captures, /v1/jobs)
│   ├── providers_base.py          -> Swappable ReconstructionProvider interface
│   └── requirements.txt           -> Backend Python dependencies
├── pipeline/                      -> Processing stages workers
│   └── workers.py                 -> S0 Ingest, S1 Extract, S2 Select, S3 Poses, S5 Reconstruct
├── contracts/                     -> Shared data contracts & Pydantic models
│   └── stages.py                  -> StageInput and StageOutput definitions
├── storage/                       -> Local artifact & media storage (S3/R2 mock)
│   ├── uploads/                   -> Uploaded video files
│   └── artifacts/                 -> Generated frames, poses, and 3D splat PLY files
└── docs/                          -> System architecture & changelog
    ├── ARCHITECTURE.md            -> Full system technical breakdown
    └── CHANGELOG.md               -> Detailed step-by-step update log
```

---

## 2. Quick Startup Guide

Follow these steps to run both the frontend and backend locally:

### Prerequisites
- **Node.js**: v18+ & npm / bun
- **Python**: 3.10+
- **ffmpeg & ffprobe**: Installed and available in your system `PATH`

### Step 1: Start the Backend Server
```bash
# Navigate to project root
cd pixel-perfect-replica-57

# Install Python dependencies
pip install -r backend/requirements.txt

# Start FastAPI server on port 8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
The backend API is accessible at `http://localhost:8000` (Docs: `http://localhost:8000/docs`).

### Step 2: Start the Frontend Application
In a separate terminal:
```bash
# Install frontend dependencies
npm install

# Start Vite / TanStack development server
npm run dev
```
The frontend is available at `http://localhost:5173` (or the port Vite outputs).

---

## 3. Reconstruction Tracks Overview

Per the system design specifications:
- **Buy Track (`PolycamProvider`)**: Hosted cloud API reconstruction for fastest turnaround.
- **Build Track (`SelfHostedProvider`)**: In-house worker pool (ffmpeg -> COLMAP/GLOMAP -> gsplat/Splatfacto) scaling to zero.
- **Hybrid Track (`RouterProvider`)**: Cost, SLA, and capacity-based dynamic routing across both engines.

---

## 4. Change Tracker & Updates

All architectural progress and milestone implementations are logged continuously in [`docs/CHANGELOG.md`](file:///docs/CHANGELOG.md).
