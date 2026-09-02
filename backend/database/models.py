"""
database/models.py
==================
SQLAlchemy ORM table definitions for SemanticStream.

All tables follow the authoritative schema defined in Section 6 of the
master build specification.  UUIDs are used as primary keys throughout
for portability between SQLite (dev) and PostgreSQL (prod).

Tables:
    Video            — uploaded source video metadata
    AnalysisJob      — one async analysis run per video
    FrameMetric      — per-frame quality metrics for a job
    Experiment       — a multi-strategy comparison run
    ExperimentResult — per-strategy metrics for an experiment
    SceneEvent       — scene transition events within a job
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def _uuid() -> str:
    """Generate a new UUID4 string for use as a primary key."""
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


# ── Video ─────────────────────────────────────────────────────────────────────

class Video(Base):
    """Uploaded source video file record."""

    __tablename__ = "videos"

    id: str = Column(String(36), primary_key=True, default=_uuid, index=True)
    filename: str = Column(String(512), nullable=False)
    filepath: str = Column(String(1024), nullable=False)
    duration_seconds: float = Column(Float, nullable=True)
    fps: float = Column(Float, nullable=True)
    width: int = Column(Integer, nullable=True)
    height: int = Column(Integer, nullable=True)
    size_mb: float = Column(Float, nullable=True)
    uploaded_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    jobs = relationship("AnalysisJob", back_populates="video", cascade="all, delete-orphan")
    experiments = relationship("Experiment", back_populates="video", cascade="all, delete-orphan")


# ── AnalysisJob ───────────────────────────────────────────────────────────────

class AnalysisJob(Base):
    """One asynchronous analysis run for a video."""

    __tablename__ = "analysis_jobs"

    id: str = Column(String(36), primary_key=True, default=_uuid, index=True)
    video_id: str = Column(String(36), ForeignKey("videos.id"), nullable=False, index=True)
    status: str = Column(String(32), nullable=False, default="queued")
    # status values: queued | running | done | failed
    bandwidth_profile: str = Column(String(64), nullable=True)
    frame_sample_rate: int = Column(Integer, nullable=False, default=5)
    confidence_threshold: float = Column(Float, nullable=False, default=0.45)
    progress_percent: float = Column(Float, nullable=False, default=0.0)
    run_comparison: bool = Column(Boolean, nullable=False, default=False)
    started_at: datetime = Column(DateTime, nullable=True)
    completed_at: datetime = Column(DateTime, nullable=True)
    error_message: str = Column(Text, nullable=True)

    # Aggregate metrics (cached after completion)
    avg_spqi: float = Column(Float, nullable=True)
    avg_ssim: float = Column(Float, nullable=True)
    avg_bitrate_kbps: float = Column(Float, nullable=True)
    sees_score: float = Column(Float, nullable=True)
    bitrate_reduction_pct: float = Column(Float, nullable=True)

    # Relationships
    video = relationship("Video", back_populates="jobs")
    frame_metrics = relationship(
        "FrameMetric", back_populates="job", cascade="all, delete-orphan"
    )
    scene_events = relationship(
        "SceneEvent", back_populates="job", cascade="all, delete-orphan"
    )


# ── FrameMetric ───────────────────────────────────────────────────────────────

class FrameMetric(Base):
    """Per-frame quality and detection metrics for an analysis job."""

    __tablename__ = "frame_metrics"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    job_id: str = Column(String(36), ForeignKey("analysis_jobs.id"), nullable=False, index=True)
    frame_number: int = Column(Integer, nullable=False)
    timestamp_ms: float = Column(Float, nullable=True)

    # Quality metrics
    spqi_score: float = Column(Float, nullable=True)
    ssim_score: float = Column(Float, nullable=True)
    psnr_score: float = Column(Float, nullable=True)
    bitrate_kbps: float = Column(Float, nullable=True)

    # Detection metadata
    detection_confidence: float = Column(Float, nullable=True)
    scene_type: str = Column(String(32), nullable=True)

    # SEES contribution
    sees_contribution_ms: float = Column(Float, nullable=True)

    # Per-region SSIM
    p1_ssim: float = Column(Float, nullable=True)
    p2_ssim: float = Column(Float, nullable=True)
    p3_ssim: float = Column(Float, nullable=True)
    p4_ssim: float = Column(Float, nullable=True)
    p5_ssim: float = Column(Float, nullable=True)

    # Relationship
    job = relationship("AnalysisJob", back_populates="frame_metrics")


# ── Experiment ────────────────────────────────────────────────────────────────

class Experiment(Base):
    """A multi-strategy comparison experiment run."""

    __tablename__ = "experiments"

    id: str = Column(String(36), primary_key=True, default=_uuid, index=True)
    video_id: str = Column(String(36), ForeignKey("videos.id"), nullable=False, index=True)
    bandwidth_profile: str = Column(String(64), nullable=False)
    status: str = Column(String(32), nullable=False, default="running")
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: datetime = Column(DateTime, nullable=True)

    # Relationships
    video = relationship("Video", back_populates="experiments")
    results = relationship(
        "ExperimentResult", back_populates="experiment", cascade="all, delete-orphan"
    )


# ── ExperimentResult ──────────────────────────────────────────────────────────

class ExperimentResult(Base):
    """Per-strategy metrics for a single experiment run."""

    __tablename__ = "experiment_results"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    experiment_id: str = Column(
        String(36), ForeignKey("experiments.id"), nullable=False, index=True
    )
    strategy_name: str = Column(String(64), nullable=False)
    # strategy values: uniform_abr | static_roi | semanticstream

    avg_spqi: float = Column(Float, nullable=True)
    avg_ssim: float = Column(Float, nullable=True)
    avg_bitrate_mbps: float = Column(Float, nullable=True)
    face_ssim: float = Column(Float, nullable=True)
    bg_ssim: float = Column(Float, nullable=True)
    encode_time_ms: float = Column(Float, nullable=True)
    sees_score: float = Column(Float, nullable=True)
    bitrate_reduction_pct: float = Column(Float, nullable=True)

    # Relationship
    experiment = relationship("Experiment", back_populates="results")


# ── SceneEvent ────────────────────────────────────────────────────────────────

class SceneEvent(Base):
    """A detected scene transition within an analysis job."""

    __tablename__ = "scene_events"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    job_id: str = Column(String(36), ForeignKey("analysis_jobs.id"), nullable=False, index=True)
    frame_number: int = Column(Integer, nullable=False)
    timestamp_ms: float = Column(Float, nullable=True)
    previous_scene_type: str = Column(String(32), nullable=True)
    new_scene_type: str = Column(String(32), nullable=True)
    histogram_score: float = Column(Float, nullable=True)

    # Relationship
    job = relationship("AnalysisJob", back_populates="scene_events")
