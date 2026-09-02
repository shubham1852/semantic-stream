"""
database/crud.py
================
All database read/write operations for SemanticStream.

This module is the ONLY place that directly queries the database.
Services call these functions; routes call services.  This separation
keeps business logic out of DB queries and DB queries out of business logic.

All functions accept an ``AsyncSession`` (injected via FastAPI ``get_db``).
All functions are async-compatible using ``await session.execute(...)``.

Functions are grouped by table / entity:
    Video CRUD
    AnalysisJob CRUD
    FrameMetric CRUD
    Experiment CRUD
    ExperimentResult CRUD
    SceneEvent CRUD
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging_config import get_logger
from backend.database.models import (
    AnalysisJob,
    Experiment,
    ExperimentResult,
    FrameMetric,
    SceneEvent,
    Video,
)

logger = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_id() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════
# VIDEO CRUD
# ═══════════════════════════════════════════════════════════════════

async def create_video(
    db: AsyncSession,
    *,
    filename: str,
    filepath: str,
    duration_seconds: float | None = None,
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    size_mb: float | None = None,
) -> Video:
    """Insert a new video record and return it.

    Args:
        db: Active async database session.
        filename: Original file name (display only).
        filepath: Absolute path to the stored file on disk.
        duration_seconds: Video duration in seconds (probed by ffprobe).
        fps: Frames per second.
        width: Frame width in pixels.
        height: Frame height in pixels.
        size_mb: File size in megabytes.

    Returns:
        The newly created ``Video`` ORM instance.
    """
    video = Video(
        id=_new_id(),
        filename=filename,
        filepath=filepath,
        duration_seconds=duration_seconds,
        fps=fps,
        width=width,
        height=height,
        size_mb=size_mb,
    )
    db.add(video)
    await db.flush()
    logger.info("crud.video.created", video_id=video.id, filename=filename)
    return video


async def get_video(db: AsyncSession, video_id: str) -> Video | None:
    """Fetch a video by its UUID.

    Args:
        db: Active async database session.
        video_id: UUID string of the video.

    Returns:
        ``Video`` instance or ``None`` if not found.
    """
    result = await db.execute(select(Video).where(Video.id == video_id))
    return result.scalar_one_or_none()


async def list_videos(db: AsyncSession, limit: int = 50, offset: int = 0) -> list[Video]:
    """Return a paginated list of all videos ordered by upload time descending.

    Args:
        db: Active async database session.
        limit: Maximum number of records to return.
        offset: Number of records to skip.

    Returns:
        List of ``Video`` ORM instances.
    """
    result = await db.execute(
        select(Video)
        .order_by(Video.uploaded_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def delete_video(db: AsyncSession, video_id: str) -> bool:
    """Delete a video record by ID.

    Args:
        db: Active async database session.
        video_id: UUID string of the video to delete.

    Returns:
        ``True`` if a record was deleted, ``False`` otherwise.
    """
    result = await db.execute(delete(Video).where(Video.id == video_id))
    return result.rowcount > 0


# ═══════════════════════════════════════════════════════════════════
# ANALYSIS JOB CRUD
# ═══════════════════════════════════════════════════════════════════

async def create_job(
    db: AsyncSession,
    *,
    video_id: str,
    bandwidth_profile: str | None = None,
    frame_sample_rate: int = 5,
    confidence_threshold: float = 0.45,
    run_comparison: bool = False,
) -> AnalysisJob:
    """Create a new analysis job in ``queued`` status.

    Args:
        db: Active async database session.
        video_id: UUID of the video to analyse.
        bandwidth_profile: Named bandwidth profile for simulation.
        frame_sample_rate: Analyse every Nth frame.
        confidence_threshold: Minimum detection confidence.
        run_comparison: Whether to run all 3 strategies in parallel.

    Returns:
        The newly created ``AnalysisJob`` ORM instance.
    """
    job = AnalysisJob(
        id=_new_id(),
        video_id=video_id,
        status="queued",
        bandwidth_profile=bandwidth_profile,
        frame_sample_rate=frame_sample_rate,
        confidence_threshold=confidence_threshold,
        run_comparison=run_comparison,
    )
    db.add(job)
    await db.flush()
    logger.info("crud.job.created", job_id=job.id, video_id=video_id)
    return job


async def get_job(db: AsyncSession, job_id: str) -> AnalysisJob | None:
    """Fetch an analysis job by its UUID.

    Args:
        db: Active async database session.
        job_id: UUID string of the job.

    Returns:
        ``AnalysisJob`` instance or ``None`` if not found.
    """
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    return result.scalar_one_or_none()


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    *,
    status: str,
    progress_percent: float | None = None,
    error_message: str | None = None,
    avg_spqi: float | None = None,
    avg_ssim: float | None = None,
    avg_bitrate_kbps: float | None = None,
    sees_score: float | None = None,
    bitrate_reduction_pct: float | None = None,
) -> None:
    """Patch mutable fields on an analysis job.

    Args:
        db: Active async database session.
        job_id: UUID of the job to update.
        status: New status string (queued/running/done/failed).
        progress_percent: Optional completion percentage (0–100).
        error_message: Optional error description on failure.
        avg_spqi: Optional cached aggregate SPQI.
        avg_ssim: Optional cached aggregate SSIM.
        avg_bitrate_kbps: Optional cached aggregate bitrate.
        sees_score: Optional SEES score.
        bitrate_reduction_pct: Optional bitrate reduction percentage.
    """
    values: dict[str, Any] = {"status": status}
    if progress_percent is not None:
        values["progress_percent"] = progress_percent
    if error_message is not None:
        values["error_message"] = error_message
    if status == "running":
        values["started_at"] = datetime.utcnow()
    if status in ("done", "failed"):
        values["completed_at"] = datetime.utcnow()
    if avg_spqi is not None:
        values["avg_spqi"] = avg_spqi
    if avg_ssim is not None:
        values["avg_ssim"] = avg_ssim
    if avg_bitrate_kbps is not None:
        values["avg_bitrate_kbps"] = avg_bitrate_kbps
    if sees_score is not None:
        values["sees_score"] = sees_score
    if bitrate_reduction_pct is not None:
        values["bitrate_reduction_pct"] = bitrate_reduction_pct

    await db.execute(update(AnalysisJob).where(AnalysisJob.id == job_id).values(**values))


async def list_jobs(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[AnalysisJob]:
    """Return recent analysis jobs with associated video info.

    Args:
        db: Active async database session.
        limit: Maximum number of records to return.
        offset: Number of records to skip.

    Returns:
        List of ``AnalysisJob`` ORM instances ordered newest first.
    """
    result = await db.execute(
        select(AnalysisJob)
        .order_by(AnalysisJob.started_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════
# FRAME METRIC CRUD
# ═══════════════════════════════════════════════════════════════════

async def bulk_create_frame_metrics(
    db: AsyncSession, metrics: list[dict[str, Any]]
) -> None:
    """Insert multiple frame metric records in a single flush.

    Args:
        db: Active async database session.
        metrics: List of dicts whose keys match ``FrameMetric`` column names.
    """
    db.add_all([FrameMetric(id=_new_id(), **m) for m in metrics])
    await db.flush()


async def get_frame_metrics(
    db: AsyncSession, job_id: str
) -> list[FrameMetric]:
    """Return all frame metrics for a job ordered by frame number.

    Args:
        db: Active async database session.
        job_id: UUID of the parent analysis job.

    Returns:
        Ordered list of ``FrameMetric`` instances.
    """
    result = await db.execute(
        select(FrameMetric)
        .where(FrameMetric.job_id == job_id)
        .order_by(FrameMetric.frame_number)
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════
# EXPERIMENT CRUD
# ═══════════════════════════════════════════════════════════════════

async def create_experiment(
    db: AsyncSession,
    *,
    video_id: str,
    bandwidth_profile: str,
) -> Experiment:
    """Create a new experiment record in ``running`` status.

    Args:
        db: Active async database session.
        video_id: UUID of the source video.
        bandwidth_profile: Bandwidth profile name for the experiment.

    Returns:
        The newly created ``Experiment`` ORM instance.
    """
    experiment = Experiment(
        id=_new_id(),
        video_id=video_id,
        bandwidth_profile=bandwidth_profile,
        status="running",
    )
    db.add(experiment)
    await db.flush()
    return experiment


async def get_experiment(db: AsyncSession, experiment_id: str) -> Experiment | None:
    """Fetch an experiment by its UUID.

    Args:
        db: Active async database session.
        experiment_id: UUID string.

    Returns:
        ``Experiment`` instance or ``None``.
    """
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id)
    )
    return result.scalar_one_or_none()


async def complete_experiment(db: AsyncSession, experiment_id: str) -> None:
    """Mark an experiment as completed and set the completion timestamp.

    Args:
        db: Active async database session.
        experiment_id: UUID of the experiment to complete.
    """
    await db.execute(
        update(Experiment)
        .where(Experiment.id == experiment_id)
        .values(status="done", completed_at=datetime.utcnow())
    )


async def create_experiment_result(
    db: AsyncSession,
    *,
    experiment_id: str,
    strategy_name: str,
    **metrics: Any,
) -> ExperimentResult:
    """Insert one per-strategy result record for an experiment.

    Args:
        db: Active async database session.
        experiment_id: UUID of the parent experiment.
        strategy_name: One of ``uniform_abr``, ``static_roi``, ``semanticstream``.
        **metrics: Metric keyword arguments matching ``ExperimentResult`` columns.

    Returns:
        The newly created ``ExperimentResult`` ORM instance.
    """
    result = ExperimentResult(
        id=_new_id(),
        experiment_id=experiment_id,
        strategy_name=strategy_name,
        **metrics,
    )
    db.add(result)
    await db.flush()
    return result


async def get_experiment_results(
    db: AsyncSession, experiment_id: str
) -> list[ExperimentResult]:
    """Return all strategy results for an experiment.

    Args:
        db: Active async database session.
        experiment_id: UUID of the parent experiment.

    Returns:
        List of ``ExperimentResult`` instances.
    """
    result = await db.execute(
        select(ExperimentResult).where(
            ExperimentResult.experiment_id == experiment_id
        )
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════
# SCENE EVENT CRUD
# ═══════════════════════════════════════════════════════════════════

async def bulk_create_scene_events(
    db: AsyncSession, events: list[dict[str, Any]]
) -> None:
    """Insert multiple scene event records.

    Args:
        db: Active async database session.
        events: List of dicts whose keys match ``SceneEvent`` column names.
    """
    db.add_all([SceneEvent(id=_new_id(), **e) for e in events])
    await db.flush()


async def get_scene_events(
    db: AsyncSession, job_id: str
) -> list[SceneEvent]:
    """Return all scene events for a job ordered by frame number.

    Args:
        db: Active async database session.
        job_id: UUID of the parent job.

    Returns:
        List of ``SceneEvent`` instances.
    """
    result = await db.execute(
        select(SceneEvent)
        .where(SceneEvent.job_id == job_id)
        .order_by(SceneEvent.frame_number)
    )
    return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════
# AGGREGATED HISTORY QUERY
# ═══════════════════════════════════════════════════════════════════

# ── Alias used by report_service.py ──────────────────────────────────────────

async def get_analysis_job(db: AsyncSession, job_id: str) -> AnalysisJob | None:
    """Alias for :func:`get_job` — used by report_service and external callers.

    Args:
        db: Active async database session.
        job_id: UUID of the analysis job.

    Returns:
        ``AnalysisJob`` instance or ``None``.
    """
    return await get_job(db, job_id)


async def list_experiments(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[Experiment]:
    """Return recent experiments ordered by creation time.

    Args:
        db: Active async database session.
        limit: Maximum number of records to return.
        offset: Number of records to skip.

    Returns:
        List of ``Experiment`` instances.
    """
    result = await db.execute(
        select(Experiment)
        .order_by(Experiment.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def fail_experiment(db: AsyncSession, experiment_id: str, error: str) -> None:
    """Mark an experiment as failed.

    Args:
        db: Active async database session.
        experiment_id: UUID of the experiment.
        error: Error message to store.
    """
    from datetime import datetime
    await db.execute(
        update(Experiment)
        .where(Experiment.id == experiment_id)
        .values(status="failed", completed_at=datetime.utcnow())
    )
    logger.error("crud.experiment.failed", experiment_id=experiment_id, error=error)


async def list_history(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[dict[str, Any]]:
    """Return a denormalised history list joining jobs + videos.

    Args:
        db: Active async database session.
        limit: Maximum rows to return.
        offset: Number of rows to skip.

    Returns:
        List of dicts with keys: session_id, filename, bandwidth_profile,
        avg_spqi, bitrate_reduction_pct, created_at (ISO string).
    """
    result = await db.execute(
        select(
            AnalysisJob.id.label("session_id"),
            Video.filename,
            AnalysisJob.bandwidth_profile,
            AnalysisJob.avg_spqi,
            AnalysisJob.bitrate_reduction_pct,
            AnalysisJob.started_at.label("created_at"),
        )
        .join(Video, AnalysisJob.video_id == Video.id)
        .where(AnalysisJob.status == "done")
        .order_by(AnalysisJob.started_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]
