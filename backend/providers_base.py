from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel

class ReconstructionJobRequest(BaseModel):
    job_id: str
    capture_id: str
    mode: str = "splat"  # "splat" or "photo"
    frames_dir: str
    poses_path: Optional[str] = None
    params: Dict[str, Any] = {}

class ReconstructionJobResult(BaseModel):
    status: str  # "ok", "failed", "pending"
    artifacts: Dict[str, str] = {}
    metrics: Dict[str, Any] = {}
    error: Optional[str] = None

class BaseReconstructionProvider(ABC):
    @abstractmethod
    def name(self) -> str:
        """Name of the reconstruction provider."""
        pass

    @abstractmethod
    def submit_job(self, request: ReconstructionJobRequest) -> ReconstructionJobResult:
        """Submit a reconstruction job."""
        pass

    @abstractmethod
    def check_status(self, provider_job_id: str) -> ReconstructionJobResult:
        """Poll or check status of a running job."""
        pass
