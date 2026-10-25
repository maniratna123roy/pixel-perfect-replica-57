import os
import subprocess
from pathlib import Path
import trimesh

def run_colmap_sparse(images_dir: Path, output_dir: Path) -> Path:
    """
    Runs COLMAP feature extraction, sequential matcher (for drone video),
    and mapper to build a genuine 3D point cloud & camera trajectory.
    Exports to PLY and converts to GLB.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "database.db"
    sparse_dir = output_dir / "sparse"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    # 1. Feature extraction
    cmd_extract = [
        "colmap", "feature_extractor",
        "--database_path", str(db_path),
        "--image_path", str(images_dir),
        "--ImageReader.camera_model", "SIMPLE_RADIAL",
        "--ImageReader.single_camera", "1",
        "--use_gpu", "0"
    ]
    subprocess.run(cmd_extract, check=True)

    # 2. Sequential matcher (drone video order)
    cmd_match = [
        "colmap", "sequential_matcher",
        "--database_path", str(db_path),
        "--SequentialMatching.overlap", "15",
        "--use_gpu", "0"
    ]
    subprocess.run(cmd_match, check=True)

    # 3. Mapper
    cmd_map = [
        "colmap", "mapper",
        "--database_path", str(db_path),
        "--image_path", str(images_dir),
        "--output_path", str(sparse_dir)
    ]
    subprocess.run(cmd_map, check=True)

    # Find model subfolder (e.g. sparse/0)
    submodels = list(sparse_dir.glob("*"))
    model_dir = submodels[0] if submodels else sparse_dir

    # 4. Convert model to PLY
    ply_path = output_dir / "reconstruction.ply"
    cmd_convert = [
        "colmap", "model_converter",
        "--input_path", str(model_dir),
        "--output_path", str(ply_path),
        "--output_type", "PLY"
    ]
    subprocess.run(cmd_convert, check=True)

    # 5. Convert PLY to GLB using trimesh so Three.js renders the exact captured point cloud/mesh
    glb_path = output_dir / "reconstruction.glb"
    mesh_or_cloud = trimesh.load(str(ply_path))
    mesh_or_cloud.export(str(glb_path))

    return glb_path
