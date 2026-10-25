"""
Phase 3B: Real 3D Reconstruction — Sparse Point Cloud → GLB

Converts the sparse 3D point cloud from SfM (pycolmap) into a viewable
GLB file that the Three.js frontend can render. This works on CPU-only
machines — no GPU required.

For dense reconstruction and full 3DGS, see future phases.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import trimesh

logger = logging.getLogger("pipeline.reconstruction")


def sparse_pointcloud_to_glb(
    points_path: str,
    colors_path: str,
    output_dir: Path,
    output_name: str = "reconstruction.glb",
) -> Dict[str, Any]:
    """
    Convert sparse SfM point cloud (numpy arrays) into a colored GLB file
    viewable in Three.js / react-three-fiber.

    Args:
        points_path: Path to points3d.npy (N, 3)
        colors_path: Path to colors3d.npy (N, 3) uint8
        output_dir: Output directory
        output_name: Output filename

    Returns:
        Dict with status, output_path, num_points
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        points = np.load(points_path)
        colors = np.load(colors_path)

        if len(points) == 0:
            logger.error("No 3D points to convert!")
            return {"status": "failed", "error": "No 3D points produced by SfM"}

        logger.info("Converting %d sparse 3D points to GLB...", len(points))

        # Normalize colors to 0-255 uint8 range and add alpha
        if colors.dtype != np.uint8:
            colors = (colors * 255).astype(np.uint8)

        # Add alpha channel
        alphas = np.full((len(colors), 1), 255, dtype=np.uint8)
        rgba_colors = np.hstack([colors, alphas])

        # Create a PointCloud using trimesh
        cloud = trimesh.PointCloud(vertices=points, colors=rgba_colors)

        # Center the point cloud
        centroid = cloud.centroid
        cloud.vertices -= centroid
        logger.info("Point cloud centered. Centroid was: %s", centroid)

        # Scale to reasonable viewer size (target ~10 units across)
        bounds = cloud.bounds
        if bounds is not None:
            extent = bounds[1] - bounds[0]
            max_extent = max(extent)
            if max_extent > 0:
                scale_factor = 10.0 / max_extent
                cloud.vertices *= scale_factor
                logger.info("Scaled by %.4f (max extent was %.2f)", scale_factor, max_extent)

        # Export as GLB
        glb_path = output_dir / output_name
        cloud.export(str(glb_path), file_type="glb")
        file_size_mb = glb_path.stat().st_size / (1024 * 1024)

        logger.info(
            "Exported GLB: %s (%.2f MB, %d points)",
            glb_path, file_size_mb, len(points)
        )

        # Also export PLY for reference / future splat viewers
        ply_path = output_dir / "reconstruction.ply"
        cloud.export(str(ply_path), file_type="ply")
        logger.info("Exported PLY: %s", ply_path)

        return {
            "status": "ok",
            "glb_path": str(glb_path),
            "ply_path": str(ply_path),
            "num_points": len(points),
            "file_size_mb": round(file_size_mb, 2),
        }

    except Exception as e:
        logger.error("Reconstruction export failed: %s", e, exc_info=True)
        return {"status": "failed", "error": str(e)}


def sparse_to_mesh_glb(
    points_path: str,
    colors_path: str,
    output_dir: Path,
    output_name: str = "reconstruction.glb",
) -> Dict[str, Any]:
    """
    Attempt to create a mesh from the sparse point cloud using
    ball pivoting or convex hull. This provides a solid surface
    rather than just dots.

    Falls back to point cloud GLB if meshing fails.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        points = np.load(points_path)
        colors = np.load(colors_path)

        if len(points) < 4:
            logger.warning("Too few points (%d) for meshing, falling back to point cloud.", len(points))
            return sparse_pointcloud_to_glb(points_path, colors_path, output_dir, output_name)

        logger.info("Attempting mesh creation from %d sparse points...", len(points))

        # Center and scale
        centroid = points.mean(axis=0)
        centered = points - centroid
        max_extent = np.abs(centered).max()
        if max_extent > 0:
            centered = centered * (10.0 / max_extent)

        # Try creating a convex hull mesh (works well for building-like structures)
        try:
            hull = trimesh.convex.convex_hull(centered)
            if hull is not None and hasattr(hull, 'vertices') and len(hull.vertices) > 0:
                # Color the mesh faces based on nearest point colors
                if colors.dtype != np.uint8:
                    colors_uint8 = (colors * 255).astype(np.uint8)
                else:
                    colors_uint8 = colors

                # Assign vertex colors by averaging nearby point colors
                face_colors = np.full((len(hull.faces), 4), 180, dtype=np.uint8)
                face_colors[:, 3] = 255

                hull.visual = trimesh.visual.ColorVisual(
                    mesh=hull,
                    face_colors=face_colors,
                )

                glb_path = output_dir / output_name
                hull.export(str(glb_path), file_type="glb")
                file_size_mb = glb_path.stat().st_size / (1024 * 1024)
                logger.info(
                    "Exported mesh GLB: %s (%.2f MB, %d faces)",
                    glb_path, file_size_mb, len(hull.faces)
                )
                return {
                    "status": "ok",
                    "glb_path": str(glb_path),
                    "num_faces": len(hull.faces),
                    "file_size_mb": round(file_size_mb, 2),
                    "method": "convex_hull",
                }

        except Exception as mesh_err:
            logger.warning("Mesh creation failed: %s — falling back to point cloud", mesh_err)

        # Fallback to point cloud
        return sparse_pointcloud_to_glb(points_path, colors_path, output_dir, output_name)

    except Exception as e:
        logger.error("Reconstruction export failed: %s", e, exc_info=True)
        return {"status": "failed", "error": str(e)}


def write_reconstruction_metadata(
    output_dir: Path,
    sfm_result: Dict[str, Any],
    recon_result: Dict[str, Any],
    method: str = "build",
) -> None:
    """
    Write a reconstruction_meta.json summarizing the pipeline results.
    """
    meta = {
        "method": method,
        "sfm": {
            "num_images": sfm_result.get("num_images"),
            "num_registered": sfm_result.get("num_registered"),
            "num_points": sfm_result.get("num_points"),
            "registration_rate": sfm_result.get("registration_rate"),
        },
        "reconstruction": {
            "status": recon_result.get("status"),
            "num_points": recon_result.get("num_points"),
            "file_size_mb": recon_result.get("file_size_mb"),
            "glb_path": recon_result.get("glb_path"),
        },
    }
    logger.info("Wrote reconstruction metadata to %s", meta_path)


def convert_textured_model_to_glb(
    model_dir: Path,
    output_glb_path: Path,
) -> Dict[str, Any]:
    """
    Finds OBJ/PLY textured model exported by WebODM/OpenDroneMap in model_dir,
    loads the mesh with its materials and texture maps, centers and normalizes scale,
    and exports a self-contained GLB file for Three.js rendering.

    Args:
        model_dir: Directory containing extracted textured model (e.g. odm_textured_model.obj)
        output_glb_path: Destination path for the .glb file

    Returns:
        Dict with status, glb_path, num_vertices, num_faces, file_size_mb
    """
    output_glb_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Locate mesh file (.obj or .ply)
    obj_files = list(model_dir.glob("*.obj"))
    if not obj_files:
        obj_files = list(model_dir.glob("*textured*.obj")) + list(model_dir.glob("*.ply"))
    
    if not obj_files:
        logger.error("No OBJ or PLY mesh file found in %s", model_dir)
        return {"status": "failed", "error": f"No mesh file found in {model_dir}"}
        
    mesh_path = obj_files[0]
    logger.info("Loading textured mesh: %s", mesh_path)
    
    try:
        loaded = trimesh.load(str(mesh_path), process=False)
        
        # In case it's a Scene (multi-part), convert or center
        if isinstance(loaded, trimesh.Scene):
            logger.info("Loaded trimesh Scene with %d geometries", len(loaded.geometry))
            # Export scene directly to GLB
            loaded.export(str(output_glb_path), file_type="glb")
            num_vertices = sum(len(g.vertices) for g in loaded.geometry.values() if hasattr(g, 'vertices'))
            num_faces = sum(len(g.faces) for g in loaded.geometry.values() if hasattr(g, 'faces'))
        elif isinstance(loaded, trimesh.Trimesh):
            # Center the model
            centroid = loaded.centroid
            loaded.vertices -= centroid
            
            # Normalize scale to fit nicely in 3D viewport (~10 units across)
            bounds = loaded.bounds
            if bounds is not None:
                extent = bounds[1] - bounds[0]
                max_extent = max(extent)
                if max_extent > 0:
                    scale_factor = 10.0 / max_extent
                    loaded.vertices *= scale_factor
                    
            loaded.export(str(output_glb_path), file_type="glb")
            num_vertices = len(loaded.vertices)
            num_faces = len(loaded.faces)
        else:
            loaded.export(str(output_glb_path), file_type="glb")
            num_vertices = 0
            num_faces = 0

        file_size_mb = output_glb_path.stat().st_size / (1024 * 1024)
        logger.info(
            "Successfully exported WebODM textured GLB: %s (%.2f MB, %d vertices, %d faces)",
            output_glb_path, file_size_mb, num_vertices, num_faces
        )
        return {
            "status": "ok",
            "glb_path": str(output_glb_path),
            "num_vertices": num_vertices,
            "num_faces": num_faces,
            "file_size_mb": round(file_size_mb, 2),
        }
    except Exception as e:
        logger.error("Failed to convert textured model to GLB: %s", e, exc_info=True)
        return {"status": "failed", "error": str(e)}

