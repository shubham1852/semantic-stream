"""
api/routes/analyze.py
=====================
POST /api/v1/analyze/{video_id} — Queues an asynchronous analysis job for a
previously uploaded video.  Returns a job_id immediately; clients poll
GET /api/v1/results/{job_id} for progress and final results.
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.schemas.analysis import AnalyzeRequest
from backend.services.analytics_service import AnalyticsService

router = APIRouter()


@router.post("/analyze/{video_id}", summary="Queue an analysis job for a video")
async def analyze_video(
    video_id: str,
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue an analysis job and return a job_id for polling.

    Args:
        video_id: UUID of the previously uploaded video.
        body: Analysis configuration (sample rate, profile, etc.).
        background_tasks: FastAPI background task runner.
        db: Injected async database session.

    Returns:
        Standard envelope with ``job_id``, status, and estimated time.
    """
    service = AnalyticsService(db)
    result = await service.queue_analysis(
        video_id=video_id,
        request=body,
        background_tasks=background_tasks,
    )
    return {"status": "success", "data": result, "message": "Analysis job queued."}
