"""
WebODM and NodeODM Integration Provider.

Provides an end-to-end interface to OpenDroneMap (NodeODM / WebODM) for
drone photogrammetry processing:
  1. Health & connectivity checking
  2. Dataset upload & task initialization
  3. Real progress tracking and log streaming
  4. Asset retrieval (textured_model.zip, orthophoto.tif/png, dsm.tif)
  5. Automatic conversion of textured mesh (OBJ+MTL) into a single GLB asset
"""

import json
import logging
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import urllib.request
import urllib.error
import urllib.parse

from pipeline.reconstruction import convert_textured_model_to_glb

logger = logging.getLogger("backend.webodm_provider")


class WebODMProvider:
    """Client and job runner for WebODM and NodeODM photogrammetry APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        token: Optional[str] = None,
    ):
        self.base_url = (base_url or os.getenv("WEBODM_URL", "http://localhost:3000")).rstrip("/")
        self.username = username or os.getenv("WEBODM_USERNAME", "")
        self.password = password or os.getenv("WEBODM_PASSWORD", "")
        self.token = token or os.getenv("WEBODM_TOKEN", "")
        self._is_nodeodm: Optional[bool] = None

    def name(self) -> str:
        return f"WebODMProvider({self.base_url})"

    def check_health(self) -> Dict[str, Any]:
        """
        Check if the remote WebODM or NodeODM service is online and responding.
        Returns a dict with status ('online' | 'unreachable'), mode ('nodeodm' | 'webodm'),
        and diagnostic details.
        """
        # 1. Try NodeODM endpoint /info
        try:
            req = urllib.request.Request(f"{self.base_url}/info", headers={"User-Agent": "BirdsEye/2.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    self._is_nodeodm = True
                    return {
                        "status": "online",
                        "mode": "nodeodm",
                        "version": data.get("version", "unknown"),
                        "task_queue_count": data.get("taskQueueCount", 0),
                        "url": self.base_url,
                    }
        except Exception as e_node:
            logger.debug("NodeODM /info check failed (%s), trying WebODM /api/...", e_node)

        # 2. Try WebODM endpoint /api/projects/
        try:
            headers = {"User-Agent": "BirdsEye/2.0"}
            if self.token:
                headers["Authorization"] = f"JWT {self.token}"
            req = urllib.request.Request(f"{self.base_url}/api/projects/", headers=headers)
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                if resp.status in (200, 401, 403):
                    self._is_nodeodm = False
                    return {
                        "status": "online",
                        "mode": "webodm",
                        "authenticated": resp.status == 200,
                        "url": self.base_url,
                    }
        except Exception as e_web:
            logger.debug("WebODM /api/ check failed: %s", e_web)

        return {
            "status": "unreachable",
            "url": self.base_url,
            "error": "Could not connect to NodeODM (port 3000) or WebODM (port 8000).",
            "docker_hint": "Start with: docker compose -f docker-compose.webodm.yml up -d",
        }

    def run_reconstruction(
        self,
        job_id: str,
        image_paths: List[Path],
        work_dir: Path,
        progress_cb: Optional[Callable[[float, str], None]] = None,
        options: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full photogrammetric reconstruction on the provided image dataset.

        Args:
            job_id: Unique job identifier
            image_paths: List of selected keyframe file paths
            work_dir: Local directory for job artifacts
            progress_cb: Callback function(progress: float 0.0-1.0, message: str)
            options: List of OpenDroneMap options
        """
        health = self.check_health()
        if health["status"] != "online":
            raise RuntimeError(
                f"WebODM/NodeODM is not reachable at {self.base_url}. "
                f"Please ensure the OpenDroneMap container is running. {health.get('docker_hint', '')}"
            )

        is_nodeodm = health.get("mode") == "nodeodm"
        logger.info(
            "[%s] Submitting %d images to %s (%s)...",
            job_id, len(image_paths), self.base_url, "NodeODM" if is_nodeodm else "WebODM"
        )

        # Ensure all image paths are Path objects (handles List[str] or List[Path])
        paths = [Path(p) for p in image_paths]

        if is_nodeodm:
            return self._run_nodeodm(job_id, paths, work_dir, progress_cb, options)
        else:
            return self._run_webodm(job_id, paths, work_dir, progress_cb, options)

    def _run_nodeodm(
        self,
        job_id: str,
        image_paths: List[Path],
        work_dir: Path,
        progress_cb: Optional[Callable[[float, str], None]],
        custom_options: Optional[List[Dict[str, Any]]],
        existing_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handles reconstruction via NodeODM's REST API."""
        recon_dir = work_dir / "reconstruction"
        recon_dir.mkdir(parents=True, exist_ok=True)

        # 1. Default CPU-tuned options for drone video frames
        opts = custom_options or [
            {"name": "feature-quality", "value": "medium"},
            {"name": "mesh-size", "value": 100000},
            {"name": "pc-quality", "value": "medium"},
            {"name": "auto-boundary", "value": True},
            {"name": "dsm", "value": True},
            {"name": "dtm", "value": False},
        ]

        if existing_uuid:
            uuid = existing_uuid
            logger.info("[%s] Resuming NodeODM task with existing UUID: %s", job_id, uuid)
        else:
            if progress_cb:
                progress_cb(0.40, "Initializing NodeODM reconstruction task...")

            # Step A: POST /task/new/init
            init_payload = urllib.parse.urlencode({
                "name": f"BirdsEye_{job_id}",
                "options": json.dumps(opts),
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.base_url}/task/new/init",
                data=init_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            try:
                with urllib.request.urlopen(req, timeout=15.0) as resp:
                    init_data = json.loads(resp.read().decode("utf-8"))
                    uuid = init_data.get("uuid")
                    if not uuid:
                        raise RuntimeError(f"NodeODM did not return a task UUID: {init_data}")
            except Exception as e:
                raise RuntimeError(f"Failed to initialize task on NodeODM: {e}")

            logger.info("[%s] NodeODM task initialized with UUID: %s", job_id, uuid)

            # Step B: POST /task/new/upload/{uuid} - Upload images as multipart/form-data
            if progress_cb:
                progress_cb(0.45, f"Uploading {len(image_paths)} keyframes to NodeODM...")

            self._upload_images_multipart(f"{self.base_url}/task/new/upload/{uuid}", image_paths)
            logger.info("[%s] Successfully uploaded %d images to NodeODM.", job_id, len(image_paths))

            # Step C: POST /task/new/commit/{uuid}
            if progress_cb:
                progress_cb(0.50, "Starting OpenDroneMap photogrammetry engine...")

            commit_req = urllib.request.Request(
                f"{self.base_url}/task/new/commit/{uuid}",
                data=b"",
                headers={"Content-Length": "0"},
            )
            with urllib.request.urlopen(commit_req, timeout=15.0) as resp:
                logger.info("[%s] NodeODM task %s committed. Processing started.", job_id, uuid)

        # Step D: Poll /task/{uuid}/info until completed (status 40) or failed (status 50)
        start_time = time.time()
        while True:
            time.sleep(3.0)
            try:
                info_req = urllib.request.Request(f"{self.base_url}/task/{uuid}/info")
                with urllib.request.urlopen(info_req, timeout=10.0) as resp:
                    info = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                logger.warning("[%s] Transient error reading task info: %s", job_id, e)
                continue

            raw_status = info.get("status")
            if isinstance(raw_status, dict):
                status_code = raw_status.get("code")
            else:
                status_code = raw_status

            progress_pct = info.get("progress", 0)
            elapsed_sec = int(time.time() - start_time)

            # NodeODM status codes:
            # 10 = Queued, 20 = Running, 30 = Failed, 40 = Completed, 50 = Canceled
            if status_code == 20:  # Running
                norm_progress = 0.50 + (progress_pct / 100.0) * 0.40  # Map 0-100% to 0.50-0.90
                msg = f"OpenDroneMap processing: {progress_pct}% ({elapsed_sec}s elapsed)"
                logger.info("[%s] %s", job_id, msg)
                if progress_cb:
                    progress_cb(round(norm_progress, 2), msg)

            elif status_code == 40:  # Completed
                logger.info("[%s] NodeODM task %s completed successfully in %ds!", job_id, uuid, elapsed_sec)
                break

            elif status_code in (30, 50):  # Failed / Canceled
                last_err = info.get("last_error") or "OpenDroneMap task reported failure."
                raise RuntimeError(f"OpenDroneMap task {uuid} failed: {last_err}")

        # Step E: Download outputs
        if progress_cb:
            progress_cb(0.88, "Downloading textured 3D mesh and GIS products...")

        # 1. Download outputs (NodeODM packages all products including odm_texturing into all.zip)
        all_zip_path = recon_dir / "all.zip"
        try:
            self._download_file(f"{self.base_url}/task/{uuid}/download/textured_model.zip", recon_dir / "textured_model.zip")
            model_zip_path = recon_dir / "textured_model.zip"
        except Exception:
            model_zip_path = None

        extracted_model_dir = recon_dir / "textured_model"
        extracted_model_dir.mkdir(parents=True, exist_ok=True)

        if model_zip_path and model_zip_path.exists() and model_zip_path.stat().st_size > 500:
            with zipfile.ZipFile(model_zip_path, "r") as zf:
                zf.extractall(extracted_model_dir)
        else:
            # Download all.zip which is always available in NodeODM
            self._download_file(f"{self.base_url}/task/{uuid}/download/all.zip", all_zip_path)
            with zipfile.ZipFile(all_zip_path, "r") as zf:
                for member in zf.namelist():
                    if "odm_texturing/" in member and not member.endswith("/"):
                        filename = Path(member).name
                        with zf.open(member) as source_f, open(extracted_model_dir / filename, "wb") as target_f:
                            shutil.copyfileobj(source_f, target_f)

            # Also create standalone textured_model.zip for user download
            with zipfile.ZipFile(recon_dir / "textured_model.zip", "w", zipfile.ZIP_DEFLATED) as zf_out:
                for file_path in extracted_model_dir.glob("*"):
                    if file_path.is_file():
                        zf_out.write(file_path, arcname=file_path.name)

        logger.info("[%s] Extracted textured model to %s", job_id, extracted_model_dir)

        # 3. Convert OBJ + textures to self-contained GLB
        if progress_cb:
            progress_cb(0.93, "Converting textured mesh to web-optimized GLB...")

        output_glb_path = recon_dir / "reconstruction.glb"
        conv_res = convert_textured_model_to_glb(extracted_model_dir, output_glb_path)
        if conv_res["status"] != "ok":
            raise RuntimeError(f"Failed to convert textured mesh to GLB: {conv_res.get('error')}")

        # 4. Attempt to download orthophoto if available
        ortho_path = recon_dir / "orthophoto.png"
        try:
            self._download_file(f"{self.base_url}/task/{uuid}/download/orthophoto.png", ortho_path)
            has_ortho = ortho_path.exists() and ortho_path.stat().st_size > 0
        except Exception:
            has_ortho = False

        # 5. Write metadata report
        report = {
            "job_id": job_id,
            "task_uuid": uuid,
            "provider": "NodeODM",
            "num_images": len(image_paths),
            "processing_time_sec": elapsed_sec,
            "mesh_vertices": conv_res.get("num_vertices", 0),
            "mesh_faces": conv_res.get("num_faces", 0),
            "glb_size_mb": conv_res.get("file_size_mb", 0.0),
            "has_orthophoto": has_ortho,
            "options": opts,
        }
        with open(recon_dir / "report.json", "w") as f:
            json.dump(report, f, indent=2)

        return {
            "status": "ok",
            "model_url": f"/artifacts/{job_id}/reconstruction/reconstruction.glb",
            "obj_zip_url": f"/artifacts/{job_id}/reconstruction/textured_model.zip",
            "orthophoto_url": f"/artifacts/{job_id}/reconstruction/orthophoto.png" if has_ortho else None,
            "report_url": f"/artifacts/{job_id}/reconstruction/report.json",
            "metrics": report,
        }

    def _run_webodm(
        self,
        job_id: str,
        image_paths: List[Path],
        work_dir: Path,
        progress_cb: Optional[Callable[[float, str], None]],
        custom_options: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Handles reconstruction via full WebODM API (/api/projects/...)."""
        recon_dir = work_dir / "reconstruction"
        recon_dir.mkdir(parents=True, exist_ok=True)

        headers = {"User-Agent": "BirdsEye/2.0"}
        if self.token:
            headers["Authorization"] = f"JWT {self.token}"

        # 1. Get or create project
        project_id = 1
        try:
            req = urllib.request.Request(f"{self.base_url}/api/projects/", headers=headers)
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                projects = json.loads(resp.read().decode("utf-8"))
                if isinstance(projects, list) and len(projects) > 0:
                    project_id = projects[0]["id"]
                else:
                    # Create project
                    create_payload = json.dumps({"name": "BirdsEye_Drones", "description": "Automated reconstructions"}).encode("utf-8")
                    h = dict(headers)
                    h["Content-Type"] = "application/json"
                    c_req = urllib.request.Request(f"{self.base_url}/api/projects/", data=create_payload, headers=h)
                    with urllib.request.urlopen(c_req, timeout=5.0) as c_resp:
                        project_id = json.loads(c_resp.read().decode("utf-8"))["id"]
        except Exception as e:
            logger.warning("[%s] Could not list/create WebODM project: %s. Using project_id=1", job_id, e)

        # 2. Submit task via multipart POST to /api/projects/{project_id}/tasks/
        opts = custom_options or [
            {"name": "feature-quality", "value": "medium"},
            {"name": "mesh-size", "value": 100000},
            {"name": "auto-boundary", "value": True},
            {"name": "dsm", "value": True},
        ]

        if progress_cb:
            progress_cb(0.45, f"Submitting {len(image_paths)} images to WebODM Project #{project_id}...")

        # Multipart submission with images and options
        boundary = f"----BirdsEyeBoundary{uuid.uuid4().hex}"
        body_parts = []

        # Add name & options
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\nBirdsEye_{job_id}\r\n".encode("utf-8"))
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"options\"\r\n\r\n{json.dumps(opts)}\r\n".encode("utf-8"))

        for img_path in image_paths:
            with open(img_path, "rb") as f:
                content = f.read()
            body_parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"images\"; filename=\"{img_path.name}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode("utf-8")
                + content + b"\r\n"
            )
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        multipart_data = b"".join(body_parts)

        task_headers = dict(headers)
        task_headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        task_headers["Content-Length"] = str(len(multipart_data))

        task_req = urllib.request.Request(
            f"{self.base_url}/api/projects/{project_id}/tasks/",
            data=multipart_data,
            headers=task_headers,
        )
        with urllib.request.urlopen(task_req, timeout=120.0) as resp:
            task_data = json.loads(resp.read().decode("utf-8"))
            task_id = task_data["id"]

        logger.info("[%s] WebODM Task created with ID: %s", job_id, task_id)

        # 3. Poll task status
        start_time = time.time()
        while True:
            time.sleep(3.0)
            status_req = urllib.request.Request(f"{self.base_url}/api/projects/{project_id}/tasks/{task_id}/", headers=headers)
            with urllib.request.urlopen(status_req, timeout=10.0) as resp:
                t_info = json.loads(resp.read().decode("utf-8"))

            status_code = t_info.get("status")
            progress_pct = t_info.get("progress", 0)
            elapsed_sec = int(time.time() - start_time)

            if status_code == 20:  # Running
                norm_progress = 0.50 + (progress_pct / 100.0) * 0.35
                msg = f"WebODM processing: {progress_pct}% ({elapsed_sec}s elapsed)"
                if progress_cb:
                    progress_cb(round(norm_progress, 2), msg)
            elif status_code == 40:  # Completed
                logger.info("[%s] WebODM task %s finished in %ds", job_id, task_id, elapsed_sec)
                break
            elif status_code in (30, 50):
                raise RuntimeError(f"WebODM task {task_id} failed: {t_info.get('last_error')}")

        # 4. Download outputs
        model_zip_path = recon_dir / "textured_model.zip"
        self._download_file(
            f"{self.base_url}/api/projects/{project_id}/tasks/{task_id}/download/textured_model.zip",
            model_zip_path,
            headers=headers,
        )

        extracted_model_dir = recon_dir / "textured_model"
        extracted_model_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(model_zip_path, "r") as zf:
            zf.extractall(extracted_model_dir)

        output_glb_path = recon_dir / "reconstruction.glb"
        conv_res = convert_textured_model_to_glb(extracted_model_dir, output_glb_path)

        ortho_path = recon_dir / "orthophoto.png"
        try:
            self._download_file(
                f"{self.base_url}/api/projects/{project_id}/tasks/{task_id}/download/orthophoto.png",
                ortho_path,
                headers=headers,
            )
            has_ortho = ortho_path.exists() and ortho_path.stat().st_size > 0
        except Exception:
            has_ortho = False

        return {
            "status": "ok",
            "model_url": f"/artifacts/{job_id}/reconstruction/reconstruction.glb",
            "obj_zip_url": f"/artifacts/{job_id}/reconstruction/textured_model.zip",
            "orthophoto_url": f"/artifacts/{job_id}/reconstruction/orthophoto.png" if has_ortho else None,
            "report_url": f"/artifacts/{job_id}/reconstruction/report.json",
            "metrics": {
                "num_images": len(image_paths),
                "processing_time_sec": elapsed_sec,
                "mesh_vertices": conv_res.get("num_vertices", 0),
                "mesh_faces": conv_res.get("num_faces", 0),
            },
        }

    def _upload_images_multipart(self, url: str, image_paths: List[Path]) -> None:
        """Helper to stream-upload image files as multipart/form-data."""
        boundary = "----BirdsEyeUploadBoundary7MA4YWxkTrZu0gW"
        body_parts = []
        for img in image_paths:
            img_p = Path(img)
            with open(img_p, "rb") as f:
                content = f.read()
            part = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="images"; filename="{img_p.name}"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n"
            ).encode("utf-8") + content + b"\r\n"
            body_parts.append(part)
        body_parts.append(f"--{boundary}--\r\n".encode("utf-8"))

        payload = b"".join(body_parts)
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(payload)),
            },
        )
        with urllib.request.urlopen(req, timeout=180.0) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Upload failed with HTTP status {resp.status}")

    def _download_file(self, url: str, dest_path: Path, headers: Optional[Dict[str, str]] = None) -> None:
        """Download remote asset and stream write to local destination."""
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=120.0) as resp:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        logger.info("Downloaded %s (%.2f MB)", dest_path.name, dest_path.stat().st_size / (1024 * 1024))
