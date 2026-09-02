"""
api/routes/stream.py
====================
GET /api/v1/stream/{video_id}   — Serves the HLS master playlist for a
                                   processed video.
GET /api/v1/frame/{video_id}/{frame_number} — Returns a single frame with
                                   optional overlay (heatmap, compressed, etc.)
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.services.streaming_service import StreamingService

router = APIRouter()


@router.get("/stream/{video_id}", summary="Get HLS master playlist for a processed video")
async def get_stream(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the HLS master playlist (.m3u8) for playback.

    Args:
        video_id: UUID of the processed video.
        db: Injected async database session.

    Returns:
        HLS m3u8 playlist file response.
    """
    service = StreamingService(db)
    playlist_path = await service.get_playlist_path(video_id)
    return FileResponse(playlist_path, media_type="application/vnd.apple.mpegurl")


@router.get("/frame/{video_id}/{frame_number}", summary="Get a single annotated frame")
async def get_frame(
    video_id: str,
    frame_number: int,
    overlay: str = Query(default="heatmap", pattern="^(heatmap|original|compressed|sidebyside)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a base64-encoded frame with priority overlay and detection metadata.

    Args:
        video_id: UUID of the video.
        frame_number: Zero-indexed frame number to retrieve.
        overlay: Overlay type — heatmap, original, compressed, or sidebyside.
        db: Injected async database session.

    Returns:
        Standard envelope with frame_base64, priority_map_base64, and detections.
    """
    service = StreamingService(db)
    result = await service.get_annotated_frame(video_id, frame_number, overlay)
    return {"status": "success", "data": result, "message": ""}
