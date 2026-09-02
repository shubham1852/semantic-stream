"""
api/routes/results.py
=====================
GET /api/v1/results/{job_id}  — Returns analysis job status and, when
complete, the full metrics payload for the frontend to render charts.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get("/results/{job_id}", summary="Get analysis job status and metrics")
async def get_results(
    job_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the current status and metrics for an analysis job.

    Args:
        job_id: UUID of the analysis job.
        db: Injected async database session.

    Returns:
        Standard envelope with job status, progress, and metric arrays.
    """
    service = AnalyticsService(db)
    result = await service.get_job_results(job_id)
    return {"status": "success", "data": result, "message": ""}
