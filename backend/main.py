"""
Bird's Eye — Drone Video 3D Reconstruction API

FastAPI backend orchestrating the complete drone-to-3D photogrammetry pipeline:
  1. Video upload & stream validation (ffprobe)
  2. Frame extraction (ffmpeg)
  3. Quality filtering (Laplacian variance blur detection)
  4. 3D Photogrammetry & Dense Reconstruction via WebODM / NodeODM
  5. Fallback/Standalone local SfM (pycolmap + trimesh)
  6. Asset packaging & GLB streaming
"""

import json
import logging
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ──────────────────────────────────────────────────────────────────
# Unbuffered Logging Configuration — Flushes immediately to terminal
# ──────────────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class FlushingStreamHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

handler = FlushingStreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.handlers = [handler]

logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)

logger = logging.getLogger("backend.main")

# ──────────────────────────────────────────────────────────────────
# Path Setup
# ──────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
ARTIFACTS_DIR = STORAGE_DIR / "artifacts"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────────
# Pipeline & Providers
# ──────────────────────────────────────────────────────────────────

from pipeline.workers import stage_s0_ingest, stage_s1_extract
from pipeline.quality_filter import stage_s2_quality_filter
from pipeline.sfm import run_sfm
from pipeline.reconstruction import sparse_pointcloud_to_glb, write_reconstruction_metadata
from backend.webodm_provider import WebODMProvider
from backend.build_provider import BuildProvider
from backend.polycam_provider import PolycamProvider

webodm_provider = WebODMProvider()
build_provider = BuildProvider()
POLYCAM_API_KEY = os.getenv("POLYCAM_API_KEY", "")
polycam_provider = PolycamProvider(api_key=POLYCAM_API_KEY) if POLYCAM_API_KEY else None

def select_provider(method: str = "auto"):
    """
    Selects photogrammetry provider based on method and service availability.
    Options: 'webodm', 'build', 'polycam', 'auto'
    """
    if method == "webodm":
        health = webodm_provider.check_health()
        if health["status"] != "online":
            raise ValueError(
                f"WebODM is requested but unreachable at {webodm_provider.base_url}. "
                f"Run: docker compose -f docker-compose.webodm.yml up -d"
            )
        return webodm_provider
    elif method == "polycam":
        if not polycam_provider:
            raise ValueError("Polycam API key not configured. Set POLYCAM_API_KEY env var.")
        return polycam_provider
    elif method == "build":
        return build_provider
    else:  # auto
        health = webodm_provider.check_health()
        if health["status"] == "online":
            logger.info("Auto-selection: WebODM / NodeODM is ONLINE at %s — using WebODM", webodm_provider.base_url)
            return webodm_provider
        else:
            logger.info("Auto-selection: WebODM is not active (%s). Using local CPU SfM (BuildProvider).", health.get("error"))
            return build_provider

# ──────────────────────────────────────────────────────────────────
# Jobs Database Persistence
# ──────────────────────────────────────────────────────────────────

JOBS_FILE = STORAGE_DIR / "jobs_db.json"
jobs_db: Dict[str, Dict[str, Any]] = {}

def save_jobs():
    try:
        with open(JOBS_FILE, "w") as f:
            json.dump(jobs_db, f, indent=2)
    except Exception as e:
        logger.error("Error saving jobs DB: %s", e)

def load_jobs():
    global jobs_db
    if JOBS_FILE.exists():
        try:
            with open(JOBS_FILE, "r") as f:
                jobs_db = json.load(f)
            logger.info("Loaded %d jobs from %s", len(jobs_db), JOBS_FILE)
        except Exception:
            jobs_db = {}

load_jobs()

# ──────────────────────────────────────────────────────────────────
# FastAPI Application
# ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Bird's Eye — Drone 3D Reconstruction API",
    version="2.1.0",
    description="Real Open Photogrammetry & WebODM Pipeline for Drone Video Footage.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/artifacts", StaticFiles(directory=str(ARTIFACTS_DIR)), name="artifacts")

# ──────────────────────────────────────────────────────────────────
# Background Reconstruction Worker
# ──────────────────────────────────────────────────────────────────

def run_reconstruction_pipeline(job_id: str, video_path: str, method: str = "auto"):
    """
    Orchestrates the real end-to-end photogrammetry pipeline.
    """
    job = jobs_db.get(job_id)
    if not job:
        logger.error("[PIPELINE] Job %s not found!", job_id)
        return

    work_dir = ARTIFACTS_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("[PIPELINE START] Job: %s", job_id)
    logger.info("  Video input: %s", video_path)
    logger.info("  Requested method: %s", method)
    logger.info("=" * 60)

    try:
        # S0: Ingest & Probe
        job["status"] = "running"
        job["current_stage"] = "S0_INGEST"
        job["stage_message"] = "Probing video metadata and stream integrity..."
        job["progress"] = 0.05
        save_jobs()
        logger.info("[%s] S0_INGEST: Analyzing video streams with ffprobe...", job_id)
        ingest_result = stage_s0_ingest(video_path, work_dir / "ingest")
        logger.info("[%s] S0_INGEST complete. Duration: %s", job_id, ingest_result.get("duration"))

        # S1: Frame Extraction
        job["current_stage"] = "S1_EXTRACT"
        job["stage_message"] = "Extracting video frames at 2.0 fps..."
        job["progress"] = 0.15
        save_jobs()
        logger.info("[%s] S1_EXTRACT: Extracting frames with ffmpeg...", job_id)
        frames = stage_s1_extract(video_path, work_dir / "frames", fps=2.0)
        logger.info("[%s] S1_EXTRACT: Extracted %d frames.", job_id, len(frames))

        if len(frames) < 3:
            raise RuntimeError(f"Video produced only {len(frames)} frames. Need at least 3 for 3D reconstruction.")

        # S2: Quality Filter (Laplacian variance)
        job["current_stage"] = "S2_SELECT"
        job["stage_message"] = "Selecting sharpest non-redundant keyframes (Laplacian variance)..."
        job["progress"] = 0.30
        save_jobs()
        logger.info("[%s] S2_SELECT: Performing blur detection on %d frames...", job_id, len(frames))
        selected = stage_s2_quality_filter(
            frame_paths=frames,
            selected_dir=work_dir / "selected",
            target_count=120,
            blur_percentile=25.0,
            min_frames=15,
        )
        logger.info("[%s] S2_SELECT: Selected %d high-quality keyframes.", job_id, len(selected))

        # Select Provider
        provider = select_provider(method)
        provider_name = provider.name()
        logger.info("[%s] Selected reconstruction provider: %s", job_id, provider_name)

        if isinstance(provider, WebODMProvider):
            # WebODM / NodeODM Pipeline
            job["current_stage"] = "S5_RECONSTRUCT_ODM"
            job["stage_message"] = "Submitting image dataset to OpenDroneMap..."
            job["progress"] = 0.40
            save_jobs()

            def odm_progress_callback(prog: float, msg: str):
                job["progress"] = prog
                job["stage_message"] = msg
                save_jobs()

            odm_result = provider.run_reconstruction(
                job_id=job_id,
                image_paths=selected,
                work_dir=work_dir,
                progress_cb=odm_progress_callback,
            )

            model_url = odm_result["model_url"]
            obj_zip_url = odm_result.get("obj_zip_url")
            orthophoto_url = odm_result.get("orthophoto_url")
            report_url = odm_result.get("report_url")
            metrics = odm_result.get("metrics", {})

        else:
            # Local Open-Source SfM Pipeline (pycolmap + trimesh)
            job["current_stage"] = "S3_POSES"
            job["stage_message"] = "Computing camera poses with SIFT Structure-from-Motion..."
            job["progress"] = 0.50
            save_jobs()

            logger.info("[%s] S3_POSES: Running pycolmap SfM on %d keyframes...", job_id, len(selected))
            sfm_result = run_sfm(
                images_dir=work_dir / "selected",
                output_dir=work_dir / "sfm",
                camera_model="SIMPLE_RADIAL",
                single_camera=True,
            )

            if sfm_result["status"] != "ok":
                raise RuntimeError(f"SfM failed: {sfm_result.get('error', 'unknown error')}")

            job["current_stage"] = "S5_RECONSTRUCT"
            job["stage_message"] = "Building 3D scene geometry and materials..."
            job["progress"] = 0.75
            save_jobs()

            recon_result = sparse_pointcloud_to_glb(
                points_path=sfm_result["points_path"],
                colors_path=sfm_result["colors_path"],
                output_dir=work_dir / "reconstruction",
                output_name="reconstruction.glb",
            )

            if recon_result["status"] != "ok":
                raise RuntimeError(f"Reconstruction failed: {recon_result.get('error', 'unknown error')}")

            write_reconstruction_metadata(work_dir, sfm_result, recon_result, method="build")
            model_url = f"/artifacts/{job_id}/reconstruction/reconstruction.glb"
            obj_zip_url = None
            orthophoto_url = None
            report_url = f"/artifacts/{job_id}/reconstruction_meta.json"
            metrics = {
                "num_points": recon_result.get("num_points", 0),
                "file_size_mb": recon_result.get("file_size_mb", 0.0),
                "registration_rate": sfm_result.get("registration_rate", ""),
            }

        # Verify output exists
        expected_glb = work_dir / "reconstruction" / "reconstruction.glb"
        if not expected_glb.exists() or expected_glb.stat().st_size == 0:
            raise RuntimeError(f"Generated 3D asset missing or empty at {expected_glb}")

        # S8: Publish
        job["status"] = "succeeded"
        job["current_stage"] = "S8_PUBLISH"
        job["stage_message"] = "Reconstruction complete. 3D model ready for viewing."
        job["progress"] = 1.0
        job["artifacts"] = {
            "model_url": model_url,
            "obj_zip_url": obj_zip_url,
            "orthophoto_url": orthophoto_url,
            "report_url": report_url,
            "frames_count": len(selected),
            "provider": provider_name,
            **metrics,
        }
        save_jobs()

        logger.info("=" * 60)
        logger.info("[PIPELINE COMPLETE] Job %s succeeded!", job_id)
        logger.info("  Model: %s", model_url)
        logger.info("  Provider: %s", provider_name)
        logger.info("=" * 60)

    except Exception as e:
        logger.error("=" * 60)
        logger.error("[PIPELINE FAILED] Job %s: %s", job_id, e, exc_info=True)
        logger.error("=" * 60)
        job["status"] = "failed"
        job["error"] = str(e)
        job["current_stage"] = "FAILED"
        job["stage_message"] = f"Pipeline error: {str(e)}"
        save_jobs()

# ──────────────────────────────────────────────────────────────────
# API Endpoints
# ──────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    webodm_health = webodm_provider.check_health()
    logger.info("=" * 60)
    logger.info("Bird's Eye Backend v2.1.0 started.")
    logger.info("  Storage dir: %s", STORAGE_DIR)
    logger.info("  WebODM/NodeODM status: %s (url: %s)", webodm_health["status"], webodm_health.get("url"))
    logger.info("=" * 60)

@app.get("/healthz")
def healthz():
    return {
        "status": "ok",
        "service": "birdseye-backend",
        "version": "2.1.0",
        "webodm": webodm_provider.check_health(),
    }

@app.get("/api/webodm/health")
def webodm_health():
    """Returns connectivity and diagnostic status for WebODM / NodeODM."""
    return webodm_provider.check_health()

@app.post("/v1/captures/init")
async def init_capture(filename: str = Form(...)):
    capture_id = f"cap_{uuid.uuid4().hex[:8]}"
    logger.info("[API] Init capture: %s -> capture_id=%s", filename, capture_id)
    return {
        "capture_id": capture_id,
        "upload_url": f"/v1/captures/{capture_id}/upload",
    }

@app.post("/v1/captures/{capture_id}/upload")
async def upload_capture(
    capture_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    method: str = Form("auto"),
):
    logger.info("[API] Upload received for capture %s: %s (method=%s)", capture_id, file.filename, method)

    dest_path = UPLOADS_DIR / f"{capture_id}_{file.filename}"
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size_mb = dest_path.stat().st_size / (1024 * 1024)
    logger.info("[API] File saved: %.2f MB", file_size_mb)

    job_id = f"job_{uuid.uuid4().hex[:8]}"
    jobs_db[job_id] = {
        "job_id": job_id,
        "capture_id": capture_id,
        "filename": file.filename,
        "video_path": str(dest_path),
        "method": method,
        "status": "queued",
        "progress": 0.0,
        "current_stage": "QUEUED",
        "stage_message": "Queued for processing...",
        "stages": [],
        "artifacts": {},
        "error": None,
    }
    save_jobs()

    background_tasks.add_task(run_reconstruction_pipeline, job_id, str(dest_path), method)

    return {
        "capture_id": capture_id,
        "job_id": job_id,
        "status": "queued",
        "method": method,
    }

@app.get("/v1/jobs/{job_id}")
async def get_job_status(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/v1/jobs")
async def list_jobs():
    return list(jobs_db.values())

@app.delete("/v1/jobs/{job_id}")
async def delete_job(job_id: str):
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    artifact_dir = ARTIFACTS_DIR / job_id
    if artifact_dir.exists():
        shutil.rmtree(artifact_dir)

    del jobs_db[job_id]
    save_jobs()
    return {"status": "deleted", "job_id": job_id}

@app.get("/v1/jobs/{job_id}/download/{asset_name}")
async def download_job_asset(job_id: str, asset_name: str):
    """
    Download a specific reconstruction asset (glb, obj, orthophoto, report).
    """
    job = jobs_db.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    work_dir = ARTIFACTS_DIR / job_id
    asset_map = {
        "glb": work_dir / "reconstruction" / "reconstruction.glb",
        "model": work_dir / "reconstruction" / "reconstruction.glb",
        "obj": work_dir / "reconstruction" / "textured_model.zip",
        "orthophoto": work_dir / "reconstruction" / "orthophoto.png",
        "report": work_dir / "reconstruction" / "report.json",
    }

    target_file = asset_map.get(asset_name.lower())
    if not target_file or not target_file.exists():
        raise HTTPException(status_code=404, detail=f"Asset '{asset_name}' not available for this job")

    media_types = {
        "glb": "model/gltf-binary",
        "model": "model/gltf-binary",
        "obj": "application/zip",
        "orthophoto": "image/png",
        "report": "application/json",
    }

    return FileResponse(
        path=str(target_file),
        filename=target_file.name,
        media_type=media_types.get(asset_name.lower(), "application/octet-stream"),
    )
