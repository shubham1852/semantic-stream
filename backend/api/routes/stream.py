"""
api/routes/stream.py
====================
GET /api/v1/stream/{video_id}               — HLS master playlist (legacy).
GET /api/v1/stream/{video_id}/playlist.m3u8 — HLS playlist (canonical).
GET /api/v1/stream/{video_id}/raw           — Raw source video (MP4 fallback).
GET /api/v1/stream/{video_id}/status        — Stream readiness check.
GET /api/v1/stream/{video_id}/{segment}     — Individual HLS .ts segments.
GET /api/v1/frame/{video_id}/{frame_number} — Single annotated frame.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.database import get_db
from backend.database import crud
from backend.services.streaming_service import StreamingService
from backend.utils.file_utils import hls_dir

router = APIRouter()

# Raw video extensions — if the streaming service falls back to one of these
# we must NOT serve it as application/vnd.apple.mpegurl.
_RAW_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})


def _file_response_for_path(resolved_path: str) -> FileResponse:
    """Return a FileResponse with the correct Content-Type.

    When FFmpeg is missing the streaming service falls back to the raw upload
    file.  We must serve it as ``video/mp4`` so the browser can play it
    natively — hls.js will otherwise try to parse the MP4 bytes as an HLS
    manifest and fail silently, leaving the player blank.
    """
    suffix = Path(resolved_path).suffix.lower()

    if suffix in _RAW_VIDEO_EXTENSIONS:
        return FileResponse(
            resolved_path,
            media_type="video/mp4",
            headers={
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes",
                # Custom header so the frontend knows this is not HLS
                "X-Stream-Type": "raw",
            },
        )

    # Real HLS playlist
    return FileResponse(
        resolved_path,
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Cache-Control": "no-cache",
            "X-Stream-Type": "hls",
        },
    )


@router.get(
    "/stream/{video_id}/status",
    summary="Check if a processed HLS or MP4 stream is ready",
)
async def get_stream_status(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return stream readiness for the frontend player.

    Checks whether an HLS playlist or processed annotated MP4 has been generated
    for this video.
    """
    video = await crud.get_video(db, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    service = StreamingService(db)
    hls_directory = hls_dir(video_id)
    playlist = hls_directory / "master.m3u8"
    hls_ready = playlist.exists()

    segment_count = 0
    if hls_ready:
        segment_count = len(list(hls_directory.glob("*.ts")))

    processed_ready = False
    try:
        p_path = await service.get_processed_video_path(video_id)
        # Check that it's an annotated/processed file, not merely raw
        if "_annotated" in p_path or "_encoded" in p_path or "_semanticstream" in p_path:
            processed_ready = Path(p_path).exists()
    except Exception:
        pass

    raw_path = Path(video.filepath)
    fallback_available = raw_path.exists()

    if hls_ready:
        stream_type = "hls"
        stream_url = f"/api/v1/stream/{video_id}/playlist.m3u8"
    elif processed_ready:
        stream_type = "processed"
        stream_url = f"/api/v1/stream/{video_id}/processed"
    elif fallback_available:
        stream_type = "raw"
        stream_url = f"/api/v1/stream/{video_id}/raw"
    else:
        stream_type = "none"
        stream_url = None

    return JSONResponse({
        "ready": hls_ready or processed_ready or fallback_available,
        "hls_ready": hls_ready,
        "processed_ready": processed_ready,
        "segment_count": segment_count,
        "fallback_available": fallback_available,
        "stream_type": stream_type,
        "stream_url": stream_url,
    })


@router.api_route(
    "/stream/{video_id}/processed",
    methods=["GET", "HEAD"],
    summary="Serve processed / annotated video (MP4 direct playback)",
)
async def get_stream_processed(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the annotated processed MP4 video directly with full byte-range support.

    Falls back to the raw source video if annotated rendering has not completed.
    """
    service = StreamingService(db)
    resolved_path = await service.get_processed_video_path(video_id)
    return FileResponse(
        resolved_path,
        media_type="video/mp4",
        headers={
            "Cache-Control": "no-cache",
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{Path(resolved_path).name}"',
            "X-Stream-Type": "processed",
        },
    )


@router.api_route(
    "/stream/{video_id}/playlist.m3u8",
    methods=["GET", "HEAD"],
    summary="Get HLS master playlist (canonical)",
)
async def get_stream_playlist(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the HLS playlist (.m3u8) or processed video fallback.

    Falls back to the processed video file when FFmpeg / HLS has not run yet.
    Content-Type is set correctly for whichever file is returned.
    """
    service = StreamingService(db)
    resolved_path = await service.get_playlist_path(video_id)
    return _file_response_for_path(resolved_path)


@router.api_route(
    "/stream/{video_id}/raw",
    methods=["GET", "HEAD"],
    summary="Serve raw source video (MP4 direct playback)",
)
async def get_stream_raw(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the original uploaded video file directly.

    Used as a native-player fallback when HLS is not available (e.g. FFmpeg
    not installed on the host).
    """
    from backend.database import crud

    video = await crud.get_video(db, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    raw_path = Path(video.filepath)
    if not raw_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    return FileResponse(
        str(raw_path),
        media_type="video/mp4",
        headers={"Cache-Control": "no-cache", "Accept-Ranges": "bytes"},
    )


@router.get("/stream/{video_id}/{segment}", summary="Serve an HLS segment file")
async def get_stream_segment(
    video_id: str,
    segment: str,
) -> FileResponse:
    """Serve an individual HLS .ts segment or playlist file."""
    if not (segment.endswith(".ts") or segment.endswith(".m3u8")):
        raise HTTPException(status_code=400, detail="Invalid segment filename")
    if "/" in segment or "\\" in segment or ".." in segment:
        raise HTTPException(status_code=400, detail="Invalid path")

    seg_path = hls_dir(video_id) / segment
    if not seg_path.exists():
        raise HTTPException(status_code=404, detail=f"Segment '{segment}' not found")

    media_type = (
        "video/mp2t" if segment.endswith(".ts")
        else "application/vnd.apple.mpegurl"
    )
    return FileResponse(
        str(seg_path),
        media_type=media_type,
        headers={"Cache-Control": "max-age=3600"},
    )


@router.get("/stream/{video_id}", summary="Get HLS master playlist (legacy)")
async def get_stream(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the HLS playlist or raw video fallback (legacy route)."""
    service = StreamingService(db)
    resolved_path = await service.get_playlist_path(video_id)
    return _file_response_for_path(resolved_path)


@router.get("/frame/{video_id}/{frame_number}", summary="Get a single annotated frame")
async def get_frame(
    video_id: str,
    frame_number: int,
    overlay: str = Query(
        default="heatmap",
        pattern="^(heatmap|original|compressed|sidebyside)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a base64-encoded frame with priority overlay and detections."""
    service = StreamingService(db)
    result = await service.get_annotated_frame(video_id, frame_number, overlay)
    return {"status": "success", "data": result, "message": ""}
