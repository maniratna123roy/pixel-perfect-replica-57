"""
Phase 2: Real Structure-from-Motion using pycolmap.

Performs actual feature extraction, sequential matching, and incremental
mapping to compute real camera poses and a sparse 3D point cloud from
the user's uploaded video frames.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import pycolmap
    HAS_PYCOLMAP = True
except ImportError:
    HAS_PYCOLMAP = False

logger = logging.getLogger("pipeline.sfm")


def check_pycolmap_available() -> bool:
    """Check if pycolmap is installed and usable."""
    if not HAS_PYCOLMAP:
        logger.error("pycolmap is not installed. Run: pip install pycolmap")
        return False
    logger.info("pycolmap version: %s", getattr(pycolmap, '__version__', 'unknown'))
    return True


def run_sfm(
    images_dir: Path,
    output_dir: Path,
    camera_model: str = "SIMPLE_RADIAL",
    single_camera: bool = True,
) -> Dict[str, Any]:
    """
    Run full Structure-from-Motion pipeline using pycolmap.

    Args:
        images_dir: Directory containing the selected keyframes (*.jpg)
        output_dir: Directory to write SfM results (database, sparse model, transforms.json)
        camera_model: COLMAP camera model name
        single_camera: Whether all images come from the same camera (True for drone video)

    Returns:
        Dict with keys: status, num_registered, num_points, transforms_path, etc.
    """
    if not check_pycolmap_available():
        return {"status": "failed", "error": "pycolmap not available"}

    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "database.db"
    sparse_dir = output_dir / "sparse"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    image_files = sorted(list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png")))
    if len(image_files) < 3:
        return {"status": "failed", "error": f"Need at least 3 images, got {len(image_files)}"}

    logger.info("Starting SfM with %d images from %s", len(image_files), images_dir)

    try:
        # Step 1: Feature Extraction
        logger.info("[SfM 1/3] Feature extraction (SIFT)...")
        pycolmap.extract_features(
            database_path=str(db_path),
            image_path=str(images_dir),
            camera_mode=pycolmap.CameraMode.SINGLE if single_camera else pycolmap.CameraMode.AUTO,
            camera_model=camera_model,
        )
        logger.info("[SfM 1/3] Feature extraction complete.")

        # Step 2: Sequential Matching (optimized for video — frames are in order)
        logger.info("[SfM 2/3] Sequential matching (video-optimized)...")
        pycolmap.match_sequential(
            database_path=str(db_path),
            overlap=15,  # match each frame with 15 neighbors
        )
        logger.info("[SfM 2/3] Sequential matching complete.")

        # Step 3: Incremental Mapping
        logger.info("[SfM 3/3] Incremental mapping (building 3D model)...")
        reconstructions = pycolmap.incremental_mapping(
            database_path=str(db_path),
            image_path=str(images_dir),
            output_path=str(sparse_dir),
        )
        logger.info("[SfM 3/3] Incremental mapping complete.")

        if not reconstructions:
            logger.error("SfM produced no reconstructions!")
            return {"status": "failed", "error": "SfM failed — no reconstruction produced. Ensure frames have sufficient overlap."}

        # Use the largest reconstruction
        best_key = max(reconstructions.keys(), key=lambda k: len(reconstructions[k].images))
        reconstruction = reconstructions[best_key]

        num_registered = len(reconstruction.images)
        num_points = len(reconstruction.points3D)
        logger.info(
            "SfM complete: %d/%d images registered, %d 3D points",
            num_registered, len(image_files), num_points
        )

        # Extract camera intrinsics and extrinsics
        transforms = extract_transforms(reconstruction, images_dir)

        # Write transforms.json (Nerfstudio-compatible)
        transforms_path = output_dir / "transforms.json"
        with open(transforms_path, "w") as f:
            json.dump(transforms, f, indent=2)
        logger.info("Wrote transforms.json with %d frames to %s", len(transforms["frames"]), transforms_path)

        # Write Polycam-format frames.json
        polycam_frames = convert_to_polycam_format(transforms)
        polycam_path = output_dir / "frames.json"
        with open(polycam_path, "w") as f:
            json.dump(polycam_frames, f, indent=2)
        logger.info("Wrote Polycam frames.json to %s", polycam_path)

        # Extract sparse point cloud as numpy arrays for reconstruction
        points_3d, point_colors = extract_point_cloud(reconstruction)
        points_path = output_dir / "points3d.npy"
        colors_path = output_dir / "colors3d.npy"
        np.save(str(points_path), points_3d)
        np.save(str(colors_path), point_colors)
        logger.info("Saved sparse point cloud: %d points", len(points_3d))

        return {
            "status": "ok",
            "num_images": len(image_files),
            "num_registered": num_registered,
            "num_points": num_points,
            "registration_rate": f"{num_registered}/{len(image_files)} ({100*num_registered/len(image_files):.0f}%)",
            "transforms_path": str(transforms_path),
            "polycam_frames_path": str(polycam_path),
            "points_path": str(points_path),
            "colors_path": str(colors_path),
            "sparse_dir": str(sparse_dir),
        }

    except Exception as e:
        logger.error("SfM failed with error: %s", e, exc_info=True)
        return {"status": "failed", "error": str(e)}


def extract_transforms(reconstruction, images_dir: Path) -> Dict[str, Any]:
    """
    Extract camera poses from COLMAP reconstruction into Nerfstudio
    transforms.json format.
    """
    frames = []

    for image_id, image in reconstruction.images.items():
        camera = reconstruction.cameras[image.camera_id]

        # Get camera intrinsics
        params = camera.params
        width = camera.width
        height = camera.height

        # Parse intrinsics based on camera model
        if camera.model_name == "SIMPLE_RADIAL":
            fl_x = fl_y = float(params[0])
            cx = float(params[1])
            cy = float(params[2])
        elif camera.model_name == "SIMPLE_PINHOLE":
            fl_x = fl_y = float(params[0])
            cx = float(params[1])
            cy = float(params[2])
        elif camera.model_name == "PINHOLE":
            fl_x = float(params[0])
            fl_y = float(params[1])
            cx = float(params[2])
            cy = float(params[3])
        elif camera.model_name == "OPENCV":
            fl_x = float(params[0])
            fl_y = float(params[1])
            cx = float(params[2])
            cy = float(params[3])
        else:
            fl_x = fl_y = float(params[0])
            cx = width / 2.0
            cy = height / 2.0

        # Get the world-to-camera transform (COLMAP stores cam_from_world)
        # We need camera-to-world for Nerfstudio
        rot_matrix = image.cam_from_world.rotation.matrix()
        translation = image.cam_from_world.translation

        # Build 4x4 world-to-camera matrix
        w2c = np.eye(4)
        w2c[:3, :3] = rot_matrix
        w2c[:3, 3] = translation

        # Invert to get camera-to-world
        c2w = np.linalg.inv(w2c)

        # Convert from COLMAP (x-right, y-down, z-forward) to
        # OpenGL/Nerfstudio convention (x-right, y-up, z-backward)
        c2w[0:3, 1:3] *= -1

        frame_data = {
            "file_path": image.name,
            "transform_matrix": c2w.tolist(),
            "fl_x": fl_x,
            "fl_y": fl_y,
            "cx": cx,
            "cy": cy,
            "w": width,
            "h": height,
        }
        frames.append(frame_data)

    # Sort by filename for consistency
    frames.sort(key=lambda f: f["file_path"])

    return {
        "camera_model": "PINHOLE",
        "fl_x": frames[0]["fl_x"] if frames else 0,
        "fl_y": frames[0]["fl_y"] if frames else 0,
        "cx": frames[0]["cx"] if frames else 0,
        "cy": frames[0]["cy"] if frames else 0,
        "w": frames[0]["w"] if frames else 0,
        "h": frames[0]["h"] if frames else 0,
        "frames": frames,
    }


def convert_to_polycam_format(transforms: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert Nerfstudio transforms.json to Polycam frames.json format.
    Polycam expects camera poses in their own format with the poses
    as cam-from-world (not world-from-cam).
    """
    polycam_frames = []
    for frame in transforms["frames"]:
        c2w = np.array(frame["transform_matrix"])
        # Convert back: undo the OpenGL convention flip
        c2w_colmap = c2w.copy()
        c2w_colmap[0:3, 1:3] *= -1
        # Invert to get world-to-camera (what Polycam expects)
        w2c = np.linalg.inv(c2w_colmap)

        polycam_frames.append({
            "file_path": frame["file_path"],
            "transform_matrix": w2c.tolist(),
            "fl_x": frame["fl_x"],
            "fl_y": frame["fl_y"],
            "cx": frame["cx"],
            "cy": frame["cy"],
        })

    return {
        "camera_model": "PINHOLE",
        "frames": polycam_frames,
    }


def extract_point_cloud(reconstruction) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract the sparse 3D point cloud from the COLMAP reconstruction.
    Returns (positions [N,3], colors [N,3] as uint8).
    """
    points = []
    colors = []
    for point_id, point3d in reconstruction.points3D.items():
        points.append(point3d.xyz)
        colors.append(point3d.color)

    if not points:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.uint8)

    return np.array(points), np.array(colors, dtype=np.uint8)
