"""
api/routes/bandwidth.py
========================
GET /api/v1/bandwidth-profiles — Returns the list of available bandwidth
simulation profile names and their time-series data.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.services.bandwidth_service import BandwidthService

router = APIRouter()


@router.get("/bandwidth-profiles", summary="List available bandwidth simulation profiles")
async def get_bandwidth_profiles(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return all bandwidth simulation profiles with their time-series data.

    Args:
        db: Injected async database session (unused; included for consistency).

    Returns:
        Standard envelope with a ``profiles`` dict mapping name to data.
    """
    service = BandwidthService()
    profiles = service.get_all_profiles()
    return {"status": "success", "data": {"profiles": profiles}, "message": ""}
