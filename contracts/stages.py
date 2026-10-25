from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

StageName = Literal[
    "S0_INGEST",
    "S1_EXTRACT",
    "S2_SELECT",
    "S3_POSES",
    "S4_MASK",
    "S5_RECONSTRUCT",
    "S6_POST",
    "S7_PACKAGE",
    "S8_PUBLISH",
]

StageStatus = Literal["pending", "running", "ok", "failed", "skipped"]

class StageInput(BaseModel):
    job_id: str
    stage: StageName
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs_prefix: str
    params: Dict[str, Any] = Field(default_factory=dict)

class StageOutput(BaseModel):
    status: StageStatus
    outputs: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None
