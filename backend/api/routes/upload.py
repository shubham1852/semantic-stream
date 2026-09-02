"""
api/routes/upload.py
====================
POST /api/v1/upload — Accepts a multipart video file, stores it on disk,
probes its metadata with ffprobe, and creates a Video record in the database.

All validation (size, extension) is delegated to the upload service.
This route contains NO business logic.
"""

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.services.upload_service import UploadService

router = APIRouter()


@router.post("/upload", summary="Upload a video file for analysis")
async def upload_video(
    file: UploadFile = File(..., description="MP4, MOV, or AVI file (max 2 GB)"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Accept a multipart/form-data video file upload.

    Args:
        file: The uploaded video file.
        db: Injected async database session.

    Returns:
        Standard response envelope with ``video_id`` and video metadata.
    """
    service = UploadService(db)
    result = await service.handle_upload(file)
    return {"status": "success", "data": result, "message": "Video uploaded successfully."}
