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

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database.database import get_db
from backend.database import crud
from backend.services.streaming_service import StreamingService
from backend.utils.file_utils import hls_dir

router = APIRouter()

# Raw video extensions — if the streaming service falls back to one of these
# we must NOT serve it as application/vnd.apple.mpegurl.
_RAW_VIDEO_EXTENSIONS = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})


def _resolve_stream_file(video_id: str, video_filepath: Optional[str] = None) -> Optional[Path]:
    """Find the best available video file in the priority hierarchy:
    1. Annotated MP4 with HUD & bounding boxes (settings.PROCESSED_DIR / f'{video_id}_annotated.mp4')
    2. Subfolder annotated MP4 (settings.PROCESSED_DIR / video_id / f'{video_id}_annotated.mp4')
    3. Storage root processed annotated MP4
    4. Encoded semantic stream MP4
    5. Subfolder encoded MP4
    6. Original uploaded video
    """
    base = settings.STORAGE_DIR / "processed" / video_id
    base_sub = settings.PROCESSED_DIR / video_id
    root_base = Path("storage") / "processed" / video_id
    candidates = [
        settings.PROCESSED_DIR / f"{video_id}_annotated.mp4",
        base / f"{video_id}_annotated.mp4",
        base_sub / f"{video_id}_annotated.mp4",
        Path("storage") / "processed" / f"{video_id}_annotated.mp4",
        root_base / f"{video_id}_annotated.mp4",
        settings.PROCESSED_DIR / f"{video_id}_semanticstream.mp4",
        settings.PROCESSED_DIR / f"{video_id}_encoded.mp4",
        base / f"{video_id}_encoded.mp4",
        base_sub / f"{video_id}_encoded.mp4",
        settings.PROCESSED_DIR / f"{video_id}_uniform_abr.mp4",
    ]
    if video_filepath:
        candidates.extend([
            Path(video_filepath),
            settings.UPLOAD_DIR / Path(video_filepath).name,
            Path("storage") / "uploads" / Path(video_filepath).name,
            settings.UPLOAD_DIR / f"{video_id}.mp4",
        ])
    for c in candidates:
        if c and Path(c).exists() and Path(c).is_file():
            return Path(c)
    return None


def _stream_video_file(file_path: Path, request: Request):
    """Serve MP4 with full HTTP 206 Partial Content (Byte-Range) seeking support."""
    file_size = os.path.getsize(file_path)

    if request.method == "HEAD":
        return Response(
            status_code=200,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            },
        )

    range_header = request.headers.get("Range")

    if range_header:
        # Parse Range: bytes=start-end
        range_val = range_header.replace("bytes=", "").strip()
        parts = range_val.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        end = min(end, file_size - 1)
        chunk_size = end - start + 1

        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_file(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            },
        )
    else:
        def iter_full():
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    yield chunk

        return StreamingResponse(
            iter_full(),
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(file_size),
                "Cache-Control": "no-cache",
                "Access-Control-Allow-Origin": "*",
            },
        )


def _file_response_for_path(resolved_path: str) -> FileResponse:
    """Return a FileResponse with the correct Content-Type."""
    suffix = Path(resolved_path).suffix.lower()

    if suffix in _RAW_VIDEO_EXTENSIONS:
        return FileResponse(
            resolved_path,
            media_type="video/mp4",
            headers={
                "Cache-Control": "no-cache",
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
                "X-Stream-Type": "raw",
            },
        )

    # Real HLS playlist
    return FileResponse(
        resolved_path,
        media_type="application/vnd.apple.mpegurl",
        headers={
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
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
    """Return stream readiness for the frontend player."""
    video = await crud.get_video(db, video_id)
    if video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    hls_directory = hls_dir(video_id)
    playlist = hls_directory / "master.m3u8"
    hls_ready = playlist.exists()

    segment_count = 0
    if hls_ready:
        segment_count = len(list(hls_directory.glob("*.ts")))

    resolved_file = _resolve_stream_file(video_id, video.filepath if video else None)
    processed_ready = resolved_file is not None and "_annotated" in resolved_file.name
    fallback_available = resolved_file is not None

    if processed_ready:
        stream_type = "raw"  # prefer annotated MP4 direct playback
        stream_url = f"/api/v1/stream/{video_id}/raw"
    elif hls_ready:
        stream_type = "hls"
        stream_url = f"/api/v1/stream/{video_id}/playlist.m3u8"
    elif fallback_available:
        stream_type = "raw"
        stream_url = f"/api/v1/stream/{video_id}/raw"
    else:
        stream_type = "none"
        stream_url = None

    return JSONResponse({
        "ready": processed_ready or hls_ready or fallback_available,
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
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Serve the annotated processed MP4 video directly with full byte-range support."""
    video = await crud.get_video(db, video_id)
    file_path = _resolve_stream_file(video_id, video.filepath if video else None)
    if not file_path:
        raise HTTPException(status_code=404, detail="No processed video found")
    return _stream_video_file(file_path, request)


@router.api_route(
    "/stream/{video_id}/playlist.m3u8",
    methods=["GET", "HEAD"],
    summary="Get HLS master playlist (canonical)",
)
async def get_stream_playlist(
    video_id: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Serve the HLS playlist (.m3u8) or processed video fallback."""
    service = StreamingService(db)
    resolved_path = await service.get_playlist_path(video_id)
    return _file_response_for_path(resolved_path)


@router.api_route(
    "/stream/{video_id}/raw",
    methods=["GET", "HEAD"],
    summary="Serve annotated or source video (MP4 direct playback with HTTP 206 byte-range)",
)
async def get_stream_raw(
    video_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Serve the annotated MP4 video directly with fallback hierarchy and HTTP 206 byte-range support."""
    video = await crud.get_video(db, video_id)
    file_path = _resolve_stream_file(video_id, video.filepath if video else None)
    if not file_path:
        raise HTTPException(status_code=404, detail="No video found")

    return _stream_video_file(file_path, request)


@router.api_route(
    "/stream/{video_id}",
    methods=["GET", "HEAD"],
    summary="Get stream or video fallback (legacy route)",
)
async def get_stream(
    video_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Serve the annotated MP4 or HLS master playlist."""
    video = await crud.get_video(db, video_id)
    file_path = _resolve_stream_file(video_id, video.filepath if video else None)
    if file_path:
        return _stream_video_file(file_path, request)

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
