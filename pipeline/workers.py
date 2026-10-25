"""
Pipeline stage workers — real implementations only.

S0: Ingest — ffprobe metadata extraction
S1: Extract — ffmpeg frame extraction at target fps
S2: Quality filter — blur detection + keyframe selection (delegated to quality_filter.py)

All mock/fake functions have been removed.
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("pipeline.workers")


def run_ffprobe(video_path: str) -> Dict[str, Any]:
    """Run ffprobe to extract video metadata."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    logger.info("Running ffprobe: %s", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def stage_s0_ingest(video_path: str, output_dir: Path) -> Dict[str, Any]:
    """
    Stage S0: Ingest — probe video metadata with ffprobe.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("[S0_INGEST] Probing video: %s", video_path)

    meta = {}
    try:
        meta = run_ffprobe(video_path)
        # Extract key info for logging
        fmt = meta.get("format", {})
        duration = fmt.get("duration", "unknown")
        size = fmt.get("size", "unknown")
        streams = meta.get("streams", [])
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        width = video_stream.get("width", "?")
        height = video_stream.get("height", "?")
        codec = video_stream.get("codec_name", "?")
        fps = video_stream.get("r_frame_rate", "?")

        logger.info(
            "[S0_INGEST] Video: %sx%s, codec=%s, fps=%s, duration=%ss, size=%s bytes",
            width, height, codec, fps, duration, size
        )
    except FileNotFoundError:
        logger.warning("[S0_INGEST] ffprobe not found — using basic file metadata")
        meta = {"format": {"size": os.path.getsize(video_path), "duration": "unknown"}}
    except Exception as e:
        logger.warning("[S0_INGEST] ffprobe failed: %s — using basic file metadata", e)
        meta = {"format": {"size": os.path.getsize(video_path), "duration": "unknown"}}

    meta_path = output_dir / "ingest_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info("[S0_INGEST] Metadata saved to %s", meta_path)

    return {"status": "ok", "meta": meta}


def stage_s1_extract(video_path: str, frames_dir: Path, fps: float = 2.0) -> List[str]:
    """
    Stage S1: Extract frames from video using ffmpeg.
    """
    frames_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(frames_dir / "frame_%04d.jpg")

    logger.info("[S1_EXTRACT] Extracting frames at %.1f fps from %s", fps, video_path)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "2",
        out_pattern
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        frames = sorted([str(p) for p in frames_dir.glob("*.jpg")])
        logger.info("[S1_EXTRACT] Extracted %d frames to %s", len(frames), frames_dir)
        return frames
    except FileNotFoundError:
        logger.error("[S1_EXTRACT] ffmpeg not found! Please install ffmpeg.")
        raise RuntimeError("ffmpeg is not installed or not in PATH")
    except subprocess.CalledProcessError as e:
        logger.error("[S1_EXTRACT] ffmpeg failed: %s", e.stderr[:500] if e.stderr else str(e))
        raise RuntimeError(f"ffmpeg frame extraction failed: {e}")
