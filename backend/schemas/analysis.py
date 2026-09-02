"""
schemas/analysis.py
===================
Pydantic v2 request and response models for analysis job endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/analyze/{video_id}."""

    frame_sample_rate: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Analyse every Nth frame (1 = every frame, 30 = every 30th).",
    )
    confidence_threshold: float = Field(
        default=0.45,
        ge=0.1,
        le=1.0,
        description="Minimum YOLO detection confidence to accept a bounding box.",
    )
    bandwidth_profile: Optional[str] = Field(
        default=None,
        description="Named bandwidth profile for simulation (see GET /bandwidth-profiles).",
    )
    run_comparison: bool = Field(
        default=False,
        description="If true, run all 3 strategies (Uniform ABR, Static ROI, SemanticStream) in parallel.",
    )


class RegionMetrics(BaseModel):
    """Quality metrics for a single priority region."""

    ssim: Optional[float]
    spqi: Optional[float]


class JobQueuedResponse(BaseModel):
    """Response returned immediately after queuing an analysis job."""

    job_id: str
    status: str = "queued"
    estimated_time_seconds: Optional[int]


class JobResultsResponse(BaseModel):
    """Full metrics payload for a completed analysis job."""

    job_id: str
    status: str
    progress_percent: float
    metrics: Optional[Dict[str, Any]] = None


class FrameAnnotationResponse(BaseModel):
    """Response for the single-frame annotation endpoint."""

    frame_base64: str
    priority_map_base64: str
    detections: List[Dict[str, Any]]
