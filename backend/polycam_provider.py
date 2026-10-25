"""
Buy Track Provider — Polycam Reconstruction API.

Implements the Polycam Enterprise Reconstruction API workflow:
  1. Package keyframes + poses into session.zip
  2. POST /v1/captures to create a capture
  3. Upload session.zip to pre-signed URL
  4. Confirm upload to trigger cloud reconstruction
  5. Poll for completion
  6. Download artifacts (GLB/PLY/splat)

REQUIRES: POLYCAM_API_KEY environment variable with Enterprise `reconstruct` scope.

NO MOCK FALLBACKS. If the API key is missing, this provider MUST NOT be used.
Use BuildProvider instead.
"""

import json
import logging
import os
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

from .providers_base import (
    BaseReconstructionProvider,
    ReconstructionJobRequest,
    ReconstructionJobResult,
)

logger = logging.getLogger("backend.polycam_provider")

POLYCAM_API_BASE = os.getenv("POLYCAM_API_BASE", "https://poly.cam/api/v1")


class PolycamProvider(BaseReconstructionProvider):
    """
    Polycam Reconstruction API provider (Buy Track).

    Workflow per Section 2.2 and 4.1 of the architecture plan:
      1. Bundle selected keyframes into keyframes/images/*
      2. Embed Polycam-formatted frames.json at root of session.zip (for splat mode)
      3. POST /v1/captures with numKeyframes and mode
      4. Upload session.zip to the returned pre-signed URL
      5. Confirm upload to trigger cloud reconstruction
      6. Poll capture status or await webhook

    NO MOCK MODE. If API key is empty, this class should not be instantiated.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError(
                "PolycamProvider requires a valid API key. "
                "Set POLYCAM_API_KEY environment variable with Enterprise `reconstruct` scope."
            )
        self.api_key = api_key
        self.base_url = POLYCAM_API_BASE.rstrip("/")
        logger.info("PolycamProvider initialized with API base: %s", self.base_url)

    def name(self) -> str:
        return "PolycamProvider (Buy Track)"

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def prepare_session_zip(
        self,
        frames_dir: Path,
        poses_path: Optional[Path],
        output_zip: Path,
        mode: str = "splat",
    ) -> int:
        """
        Creates session.zip with the layout required by Polycam API:
          session.zip
          ├── keyframes/images/*.jpg
          └── frames.json (root level, for splat mode only)

        Returns the number of keyframes packaged.
        """
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        frame_files = sorted(list(frames_dir.glob("*.jpg")) + list(frames_dir.glob("*.png")))
        num_keyframes = len(frame_files)

        if num_keyframes < 20:
            logger.warning(
                "Polycam requires at least 20 keyframes. Found %d. "
                "Reconstruction may fail.", num_keyframes
            )

        logger.info("Packaging session.zip with %d keyframes (mode=%s)...", num_keyframes, mode)

        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as z:
            for frame_path in frame_files:
                archive_name = f"keyframes/images/{frame_path.name}"
                z.write(frame_path, arcname=archive_name)

            if mode == "splat" and poses_path and poses_path.exists():
                z.write(poses_path, arcname="frames.json")
                logger.info("  Included frames.json for splat mode")

        zip_size_mb = output_zip.stat().st_size / (1024 * 1024)
        logger.info(
            "session.zip ready: %s (%.2f MB, %d keyframes)",
            output_zip, zip_size_mb, num_keyframes
        )
        return num_keyframes

    def submit_job(self, request: ReconstructionJobRequest) -> ReconstructionJobResult:
        """
        Submit a reconstruction job to Polycam's cloud.

        Steps:
          1. Create session.zip from keyframes + poses
          2. POST /v1/captures → get capture ID + upload URL
          3. PUT session.zip to upload URL
          4. POST /v1/captures/{id}/upload/confirm
        """
        frames_dir = Path(request.frames_dir)
        poses_path = Path(request.poses_path) if request.poses_path else None
        zip_path = frames_dir.parent / f"session_{request.job_id}.zip"

        num_keyframes = self.prepare_session_zip(
            frames_dir=frames_dir,
            poses_path=poses_path,
            output_zip=zip_path,
            mode=request.mode,
        )

        try:
            # Step 1: Create Capture
            logger.info("[Polycam] Creating capture (mode=%s, keyframes=%d)...", request.mode, num_keyframes)
            create_payload = {
                "mode": request.mode,
                "numKeyframes": num_keyframes,
                "totalSize": zip_path.stat().st_size,
            }
            res = requests.post(
                f"{self.base_url}/captures",
                json=create_payload,
                headers=self._headers(),
                timeout=30,
            )
            res.raise_for_status()
            capture_data = res.json()
            capture_id = capture_data.get("captureId") or capture_data.get("id")
            upload_url = capture_data.get("uploadUrl") or capture_data.get("upload", {}).get("url")

            if not upload_url:
                raise ValueError(f"No upload URL returned by Polycam: {capture_data}")

            logger.info("[Polycam] Capture created: %s", capture_id)

            # Step 2: Upload session.zip
            logger.info("[Polycam] Uploading session.zip (%.2f MB)...", zip_path.stat().st_size / (1024*1024))
            with open(zip_path, "rb") as f:
                put_res = requests.put(
                    upload_url,
                    data=f,
                    headers={"Content-Type": "application/zip"},
                    timeout=300,
                )
                put_res.raise_for_status()
            logger.info("[Polycam] Upload complete.")

            # Step 3: Confirm Upload
            logger.info("[Polycam] Confirming upload...")
            confirm_res = requests.post(
                f"{self.base_url}/captures/{capture_id}/upload/confirm",
                headers=self._headers(),
                timeout=30,
            )
            confirm_res.raise_for_status()

            logger.info("[Polycam] Capture %s confirmed and queued for reconstruction.", capture_id)
            return ReconstructionJobResult(
                status="pending",
                artifacts={"capture_id": capture_id},
                metrics={"num_keyframes": num_keyframes, "provider": "polycam"},
            )

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else "unknown"
            body = e.response.text[:500] if e.response else ""
            logger.error("[Polycam] HTTP %s: %s", status_code, body)

            if status_code == 429:
                retry_after = e.response.headers.get("Retry-After", "60")
                logger.warning("[Polycam] Rate limited! Retry after %s seconds.", retry_after)
                return ReconstructionJobResult(
                    status="rate_limited",
                    error=f"Polycam rate limit hit. Retry after {retry_after}s.",
                    metrics={"retry_after": retry_after},
                )

            return ReconstructionJobResult(status="failed", error=f"Polycam HTTP {status_code}: {body}")

        except Exception as e:
            logger.error("[Polycam] Submission failed: %s", e, exc_info=True)
            return ReconstructionJobResult(status="failed", error=str(e))

    def check_status(self, provider_job_id: str) -> ReconstructionJobResult:
        """
        Poll Polycam for the status of a reconstruction job.
        """
        try:
            logger.info("[Polycam] Checking status for capture %s...", provider_job_id)
            res = requests.get(
                f"{self.base_url}/captures/{provider_job_id}",
                headers=self._headers(),
                timeout=30,
            )
            res.raise_for_status()
            data = res.json()
            status = data.get("status", "pending")
            artifacts = {}

            if status in ("complete", "succeeded", "ok"):
                raw_artifacts = data.get("artifacts", {})
                artifacts["model_glb"] = raw_artifacts.get("glb") or raw_artifacts.get("gltf") or ""
                artifacts["splat_ply"] = raw_artifacts.get("splat_ply") or raw_artifacts.get("splat") or ""
                logger.info("[Polycam] Capture %s complete! Artifacts: %s", provider_job_id, artifacts)

            mapped_status = "ok" if status in ("complete", "succeeded", "ok") else status
            return ReconstructionJobResult(
                status=mapped_status,
                artifacts=artifacts,
                metrics=data.get("metrics", {}),
            )

        except Exception as e:
            logger.error("[Polycam] Status check failed: %s", e)
            return ReconstructionJobResult(status="failed", error=str(e))
