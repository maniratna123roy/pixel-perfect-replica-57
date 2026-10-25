"""
Phase 1: Keyframe Quality Filtering

Uses Laplacian variance (blur detection) + spatial spacing to select
high-quality, non-redundant keyframes from extracted video frames.
"""

import logging
import shutil
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np

logger = logging.getLogger("pipeline.quality_filter")


def compute_blur_score(image_path: str) -> float:
    """
    Compute the Laplacian variance of an image as a blur metric.
    Higher values = sharper image.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.warning("Could not read image: %s", image_path)
        return 0.0
    laplacian = cv2.Laplacian(img, cv2.CV_64F)
    score = float(laplacian.var())
    return score


def score_all_frames(frame_paths: List[str]) -> List[Tuple[str, float]]:
    """
    Score every frame for sharpness using Laplacian variance.
    Returns list of (path, score) sorted by original order.
    """
    scored = []
    for i, path in enumerate(frame_paths):
        score = compute_blur_score(path)
        scored.append((path, score))
        if (i + 1) % 50 == 0 or i == len(frame_paths) - 1:
            logger.info(
                "  Scored %d/%d frames (latest: %s = %.1f)",
                i + 1, len(frame_paths), Path(path).name, score
            )
    return scored


def filter_by_quality(
    scored_frames: List[Tuple[str, float]],
    blur_threshold_percentile: float = 25.0,
    min_frames: int = 20,
) -> List[Tuple[str, float]]:
    """
    Remove the blurriest frames (below the given percentile threshold).
    Always keeps at least min_frames.
    """
    if len(scored_frames) <= min_frames:
        logger.info("Only %d frames available — keeping all.", len(scored_frames))
        return scored_frames

    scores = [s for _, s in scored_frames]
    threshold = float(np.percentile(scores, blur_threshold_percentile))
    logger.info(
        "Blur threshold (%.0fth percentile): %.1f",
        blur_threshold_percentile, threshold
    )

    # Keep frames above threshold
    passed = [(p, s) for p, s in scored_frames if s >= threshold]
    logger.info(
        "Frames passing blur filter: %d/%d",
        len(passed), len(scored_frames)
    )

    # If too few pass, keep the top min_frames by score
    if len(passed) < min_frames:
        logger.warning(
            "Only %d frames passed blur filter — keeping top %d by score.",
            len(passed), min_frames
        )
        sorted_by_score = sorted(scored_frames, key=lambda x: x[1], reverse=True)
        # But preserve original order
        top_paths = {p for p, _ in sorted_by_score[:min_frames]}
        passed = [(p, s) for p, s in scored_frames if p in top_paths]

    return passed


def space_frames_evenly(
    frames: List[Tuple[str, float]],
    target_count: int = 150,
) -> List[Tuple[str, float]]:
    """
    Subsample frames evenly by stride to reach target_count.
    Preserves original temporal order.
    """
    if len(frames) <= target_count:
        return frames

    stride = len(frames) / target_count
    indices = [int(i * stride) for i in range(target_count)]
    selected = [frames[i] for i in indices]
    logger.info(
        "Spaced %d frames down to %d (stride=%.1f)",
        len(frames), len(selected), stride
    )
    return selected


def stage_s2_quality_filter(
    frame_paths: List[str],
    selected_dir: Path,
    target_count: int = 150,
    blur_percentile: float = 25.0,
    min_frames: int = 20,
) -> List[str]:
    """
    Full quality filtering pipeline:
    1. Score all frames for blur (Laplacian variance)
    2. Remove blurriest frames (bottom percentile)
    3. Space remaining frames evenly to target count
    4. Copy selected frames to output directory

    Returns list of selected frame paths in the output directory.
    """
    selected_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=== Quality Filtering: %d input frames ===", len(frame_paths))

    # Step 1: Score
    logger.info("Step 1: Computing blur scores...")
    scored = score_all_frames(frame_paths)
    scores = [s for _, s in scored]
    logger.info(
        "Blur scores — min: %.1f, max: %.1f, mean: %.1f, median: %.1f",
        min(scores), max(scores), np.mean(scores), np.median(scores)
    )

    # Step 2: Filter by quality
    logger.info("Step 2: Filtering by blur quality...")
    quality_passed = filter_by_quality(scored, blur_percentile, min_frames)

    # Step 3: Space evenly
    logger.info("Step 3: Spacing frames evenly to target=%d...", target_count)
    final = space_frames_evenly(quality_passed, target_count)

    # Step 4: Copy to output directory
    logger.info("Step 4: Copying %d selected frames to %s", len(final), selected_dir)
    output_paths = []
    for path, score in final:
        dest = selected_dir / Path(path).name
        shutil.copy2(path, dest)
        output_paths.append(str(dest))

    logger.info(
        "=== Quality Filter Complete: %d → %d frames ===",
        len(frame_paths), len(output_paths)
    )
    return output_paths
