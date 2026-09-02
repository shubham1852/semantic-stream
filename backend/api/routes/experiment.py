"""
api/routes/experiment.py
========================
POST /api/v1/experiment        — Start a multi-strategy parallel comparison.
GET  /api/v1/experiment/{id}/results — Fetch results for a completed experiment.
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.schemas.experiment import ExperimentRequest
from backend.services.analytics_service import AnalyticsService

router = APIRouter()


@router.post("/experiment", summary="Run a multi-strategy parallel experiment")
async def run_experiment(
    body: ExperimentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Start a 3-strategy comparison experiment in the background.

    Args:
        body: Experiment configuration (video_id, strategies, profile).
        background_tasks: FastAPI background task runner.
        db: Injected async database session.

    Returns:
        Standard envelope with ``experiment_id`` and status ``running``.
    """
    service = AnalyticsService(db)
    result = await service.queue_experiment(body, background_tasks)
    return {"status": "success", "data": result, "message": "Experiment started."}


@router.get("/experiment/{experiment_id}/results", summary="Get experiment results")
async def get_experiment_results(
    experiment_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return per-strategy metrics for a completed experiment.

    Args:
        experiment_id: UUID of the experiment.
        db: Injected async database session.

    Returns:
        Standard envelope with strategy comparison data and winner.
    """
    service = AnalyticsService(db)
    result = await service.get_experiment_results(experiment_id)
    return {"status": "success", "data": result, "message": ""}
