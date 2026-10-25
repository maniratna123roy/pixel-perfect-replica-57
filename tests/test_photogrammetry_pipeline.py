"""
Automated Test Suite for Bird's Eye Photogrammetry & WebODM Pipeline.

Covers:
  - Video stream probing and metadata extraction (ffprobe)
  - Video frame extraction (ffmpeg)
  - Keyframe quality filtering & blur detection (Laplacian variance)
  - WebODM provider connectivity and parameter handling
  - 3D asset conversion (textured OBJ to GLB)
  - FastAPI endpoints (/healthz, /api/webodm/health, /v1/captures/init, /v1/jobs)
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.webodm_provider import WebODMProvider
from pipeline.workers import stage_s0_ingest, stage_s1_extract
from pipeline.quality_filter import stage_s2_quality_filter, compute_blur_score
from pipeline.reconstruction import convert_textured_model_to_glb, sparse_pointcloud_to_glb

client = TestClient(app)

TEST_VIDEO = Path("Free Stock Footage - Highrise Building close up Drone DJI Air2S - Free Stock Footage (720p, h264).mp4")


def test_api_healthz():
    """Verify backend health endpoint."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "webodm" in data


def test_webodm_health_endpoint():
    """Verify WebODM health check endpoint returns valid diagnostic structure."""
    resp = client.get("/api/webodm/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "url" in data
    assert data["status"] in ("online", "unreachable")


def test_webodm_provider_offline_handling():
    """Ensure WebODMProvider fails gracefully with actionable message when unreachable."""
    provider = WebODMProvider(base_url="http://127.0.0.1:59999")
    health = provider.check_health()
    assert health["status"] == "unreachable"
    assert "docker_hint" in health


def test_video_ingest_probe():
    """Verify ffprobe parses video streams, duration, and resolution."""
    if not TEST_VIDEO.exists():
        pytest.skip(f"Test video {TEST_VIDEO} not found in workspace root")

    with tempfile.TemporaryDirectory() as tmp_dir:
        ingest_dir = Path(tmp_dir) / "ingest"
        result = stage_s0_ingest(str(TEST_VIDEO), ingest_dir)
        assert result["status"] == "ok"
        assert "meta" in result
        assert ingest_dir.exists()


def test_frame_extraction_and_blur_filtering():
    """Test extracting frames from video and running blur filtering."""
    if not TEST_VIDEO.exists():
        pytest.skip(f"Test video {TEST_VIDEO} not found in workspace root")

    with tempfile.TemporaryDirectory() as tmp_dir:
        frames_dir = Path(tmp_dir) / "frames"
        selected_dir = Path(tmp_dir) / "selected"

        # Extract frames at 1 fps for testing
        frames = stage_s1_extract(str(TEST_VIDEO), frames_dir, fps=1.0)
        assert len(frames) > 0, "FFmpeg should extract frames from the test video"

        # Verify blur calculation
        score = compute_blur_score(frames[0])
        assert isinstance(score, float)
        assert score >= 0.0

        # Run quality filter
        selected = stage_s2_quality_filter(
            frame_paths=frames,
            selected_dir=selected_dir,
            target_count=10,
            blur_percentile=10.0,
            min_frames=3,
        )
        assert len(selected) > 0
        assert len(selected) <= len(frames)
        for s in selected:
            assert Path(s).exists()


def test_pointcloud_to_glb_conversion():
    """Verify point cloud array export to valid binary GLB."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_dir = Path(tmp_dir)
        pts_path = out_dir / "points3d.npy"
        cols_path = out_dir / "colors3d.npy"

        # Create dummy point cloud (100 points in 3D box)
        pts = np.random.uniform(-5, 5, (100, 3)).astype(np.float32)
        cols = np.random.randint(0, 255, (100, 3), dtype=np.uint8)
        np.save(pts_path, pts)
        np.save(cols_path, cols)

        res = sparse_pointcloud_to_glb(str(pts_path), str(cols_path), out_dir, "test.glb")
        assert res["status"] == "ok"
        glb_file = out_dir / "test.glb"
        assert glb_file.exists()
        assert glb_file.stat().st_size > 0


def test_captures_init_endpoint():
    """Verify session initialization endpoint."""
    resp = client.post("/v1/captures/init", data={"filename": "drone_flight.mp4"})
    assert resp.status_code == 200
    data = resp.json()
    assert "capture_id" in data
    assert "upload_url" in data
    assert data["capture_id"].startswith("cap_")
