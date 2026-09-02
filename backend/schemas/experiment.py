"""
schemas/experiment.py
=====================
Pydantic v2 models for the experiment comparison API endpoints.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ExperimentRequest(BaseModel):
    """Request body for POST /api/v1/experiment."""

    video_id: str = Field(..., description="UUID of the video to run strategies on.")
    strategies: List[str] = Field(
        default=["uniform_abr", "static_roi", "semanticstream"],
        description="List of strategy names to compare.",
    )
    bandwidth_profile: str = Field(
        default="strong_wifi",
        description="Named bandwidth profile for the experiment.",
    )


class StrategyMetrics(BaseModel):
    """Per-strategy result metrics within an experiment."""

    strategy: str
    avg_spqi: Optional[float]
    avg_ssim: Optional[float]
    avg_bitrate_mbps: Optional[float]
    face_ssim: Optional[float]
    bg_ssim: Optional[float]
    encode_time_ms: Optional[float]
    sees_score: Optional[float]
    bitrate_reduction_pct: Optional[float]


class ExperimentQueuedResponse(BaseModel):
    """Response returned immediately after queuing an experiment."""

    experiment_id: str
    status: str = "running"


class ExperimentResultsResponse(BaseModel):
    """Full results for a completed experiment."""

    experiment_id: str
    strategies: dict
    winner: Optional[str]
