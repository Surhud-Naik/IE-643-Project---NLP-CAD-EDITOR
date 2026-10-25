"""
Pydantic schemas and data transfer objects for the CAD Patch Editor Web API.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    GENERATING = "GENERATING"
    APPLYING = "APPLYING"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EditMode(str, Enum):
    PATCH = "patch"
    FULL_REGEN = "full_regen"
    LOCATE_INFILL = "locate_infill"


class EditRequest(BaseModel):
    script: str = Field(..., description="CadQuery Python script to edit", max_length=20480)
    instruction: str = Field(..., description="Natural language editing instruction", max_length=500)
    mode: EditMode = Field(default=EditMode.PATCH, description="Editing mode")
    retry_count: int = Field(default=3, ge=1, le=5, description="Maximum patch retries on malformed output")
    temperature: float = Field(default=0.2, ge=0.0, le=1.5, description="Sampling temperature")


class ValidateRequest(BaseModel):
    script: str = Field(..., description="CadQuery Python script to validate", max_length=20480)


class BoundingBoxInfo(BaseModel):
    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float
    xlen: float
    ylen: float
    zlen: float
    diagonal: float


class ParameterChange(BaseModel):
    name: str
    old_value: Any
    new_value: Any


class ChangeSummary(BaseModel):
    parameters_changed: List[ParameterChange] = Field(default_factory=list)
    lines_added: int = 0
    lines_removed: int = 0
    lines_touched: int = 0
    output_tokens: int = 0
    full_program_tokens: int = 0
    token_savings_pct: float = 0.0


class GeometryMetrics(BaseModel):
    validity: bool = True
    original_volume: float = 0.0
    edited_volume: float = 0.0
    volume_change_pct: float = 0.0
    bbox_diagonal_original: float = 0.0
    bbox_diagonal_edited: float = 0.0
    chamfer_distance_relative: float = 0.0
    volumetric_iou: float = 0.0


class BaselineComparison(BaseModel):
    baseline_name: str
    edited_script: str
    unintended_change_count: int
    output_tokens: int


class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    original_script: str
    edited_script: Optional[str] = None
    patch_text: Optional[str] = None
    raw_patch: Optional[str] = None
    attempts_used: int = 1
    metrics: Optional[GeometryMetrics] = None
    change_summary: Optional[ChangeSummary] = None
    baseline_comparison: Optional[BaselineComparison] = None
    error: Optional[str] = None
    download_urls: Dict[str, str] = Field(default_factory=dict)
    created_at: float
    completed_at: Optional[float] = None
    execution_time_seconds: Optional[float] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    queue_position: int = 0
    current_attempt: int = 1
    max_attempts: int = 3
    message: str = ""
    result: Optional[JobResult] = None


class ValidateResponse(BaseModel):
    valid: bool
    status: str
    error: Optional[str] = None
    volume: Optional[float] = None
    bbox: Optional[BoundingBoxInfo] = None
    duration: float = 0.0


class ExampleItem(BaseModel):
    id: str
    title: str
    category: str
    instruction: str
    script: str
    description: str


class ConfigResponse(BaseModel):
    model_backend: str
    base_model: str
    available_modes: List[str]
    has_full_regen_adapter: bool
    has_locate_infill_adapter: bool
    max_script_bytes: int
    max_instruction_chars: int
    timeout_seconds: float
