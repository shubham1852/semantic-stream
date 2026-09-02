"""
api/routes/history.py
=====================
GET /api/v1/history — Returns a paginated list of completed analysis sessions.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.database import crud

router = APIRouter()


@router.get("/history", summary="List past analysis sessions")
async def get_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return paginated history of completed analysis sessions.

    Args:
        limit: Maximum number of sessions to return (1–100).
        offset: Number of sessions to skip.
        db: Injected async database session.

    Returns:
        Standard envelope with a ``sessions`` list.
    """
    sessions = await crud.list_history(db, limit=limit, offset=offset)
    return {"status": "success", "data": {"sessions": sessions}, "message": ""}
