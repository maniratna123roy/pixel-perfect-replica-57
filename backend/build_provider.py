"""
Build Track Provider — Self-Hosted Reconstruction.

Runs the full reconstruction pipeline locally:
  1. Quality filter keyframes (blur detection)
  2. SfM with pycolmap (real camera poses + sparse point cloud)
  3. Convert sparse point cloud to GLB for web viewing

No external API required. Works on CPU-only machines.
"""

import logging
from pathlib import Path
from typing import Any, Dict

from .providers_base import (
    BaseReconstructionProvider,
    ReconstructionJobRequest,
    ReconstructionJobResult,
)

logger = logging.getLogger("backend.build_provider")


class BuildProvider(BaseReconstructionProvider):
    """
    Self-hosted reconstruction provider implementing the Build track.

    Uses pycolmap for SfM and trimesh for GLB export.
    No external API keys or GPU required for basic reconstruction.
    """

    def name(self) -> str:
        return "BuildProvider (Self-Hosted)"

    def submit_job(self, request: ReconstructionJobRequest) -> ReconstructionJobResult:
        """
        Run reconstruction synchronously (called from a background task).

        This performs the full pipeline:
        1. pycolmap SfM → camera poses + sparse point cloud
        2. Point cloud → GLB export

        Args:
            request: Job request with frames_dir and output info

        Returns:
            ReconstructionJobResult with status and artifact paths
        """
        from pipeline.sfm import run_sfm
        from pipeline.reconstruction import sparse_pointcloud_to_glb, write_reconstruction_metadata

        frames_dir = Path(request.frames_dir)
        work_dir = frames_dir.parent  # e.g., storage/artifacts/{job_id}
        sfm_dir = work_dir / "sfm"
        recon_dir = work_dir / "reconstruction"

        logger.info("=== BuildProvider: Starting reconstruction for job %s ===", request.job_id)
        logger.info("Frames directory: %s (%d files)", frames_dir, len(list(frames_dir.glob("*.jpg"))))

        # Step 1: Run SfM
        logger.info("[Build 1/2] Running Structure-from-Motion...")
        sfm_result = run_sfm(
            images_dir=frames_dir,
            output_dir=sfm_dir,
            camera_model="SIMPLE_RADIAL",
            single_camera=True,
        )

        if sfm_result["status"] != "ok":
            error_msg = sfm_result.get("error", "Unknown SfM failure")
            logger.error("[Build] SfM failed: %s", error_msg)
            return ReconstructionJobResult(
                status="failed",
                error=f"SfM failed: {error_msg}",
            )

        logger.info(
            "[Build] SfM succeeded: %s registered, %d 3D points",
            sfm_result["registration_rate"],
            sfm_result["num_points"],
        )

        # Step 2: Convert point cloud to GLB
        logger.info("[Build 2/2] Converting point cloud to GLB...")
        recon_result = sparse_pointcloud_to_glb(
            points_path=sfm_result["points_path"],
            colors_path=sfm_result["colors_path"],
            output_dir=recon_dir,
            output_name="reconstruction.glb",
        )

        if recon_result["status"] != "ok":
            error_msg = recon_result.get("error", "Unknown reconstruction failure")
            logger.error("[Build] GLB export failed: %s", error_msg)
            return ReconstructionJobResult(
                status="failed",
                error=f"Reconstruction export failed: {error_msg}",
            )

        # Write metadata
        write_reconstruction_metadata(work_dir, sfm_result, recon_result, method="build")

        logger.info("=== BuildProvider: Reconstruction complete for job %s ===", request.job_id)
        logger.info("  GLB: %s (%.2f MB)", recon_result["glb_path"], recon_result["file_size_mb"])
        logger.info("  Points: %d", recon_result["num_points"])

        return ReconstructionJobResult(
            status="ok",
            artifacts={
                "model_glb": recon_result["glb_path"],
                "model_ply": recon_result.get("ply_path", ""),
            },
            metrics={
                "provider": "build",
                "num_registered": sfm_result["num_registered"],
                "num_points": recon_result["num_points"],
                "registration_rate": sfm_result["registration_rate"],
                "file_size_mb": recon_result["file_size_mb"],
            },
        )

    def check_status(self, provider_job_id: str) -> ReconstructionJobResult:
        """Build provider runs synchronously, so status is always done."""
        return ReconstructionJobResult(
            status="ok",
            metrics={"provider": "build", "note": "Build provider runs synchronously"},
        )
