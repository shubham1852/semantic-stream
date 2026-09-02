"""
services/upload_service.py
==========================
Handles video file uploads for SemanticStream.

Responsibilities:
  - Save the uploaded file to storage/uploads/
  - Probe video metadata (duration, fps, resolution) via cv2 / av
  - Create a Video record in the database
  - Validate file extension and size
  - Return video_id and metadata to the caller

This service contains all business logic for the upload flow.
The route handler (api/routes/upload.py) is a pure HTTP adapter.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2
from fastapi import UploadFile

from backend.core.config import settings
from backend.core.exceptions import FileTooLargeError, InvalidVideoFormatError, UploadError
from backend.core.logging_config import get_logger
from backend.database import crud

logger = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MAX_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB
UPLOAD_DIR = Path("storage/uploads")


class UploadService:
    """Handles video file upload, validation, metadata probing, and DB creation.

    Args:
        db: Async database session injected by FastAPI.
    """

    def __init__(self, db) -> None:
        self._db = db

    async def handle_upload(self, file: UploadFile) -> dict:
        """Accept a multipart upload, store it, probe metadata, create DB record.

        Args:
            file: The FastAPI UploadFile object from the multipart request.

        Returns:
            Dict with ``video_id``, ``filename``, ``duration_seconds``,
            ``fps``, ``width``, ``height``, ``size_mb``.

        Raises:
            InvalidVideoFormatError: Unsupported file extension.
            FileTooLargeError: File exceeds the 2 GB limit.
            UploadError: Any other IO error during save.
        """
        # ── Validate extension ────────────────────────────────────────────────
        filename = file.filename or "upload.mp4"
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise InvalidVideoFormatError(suffix, list(ALLOWED_EXTENSIONS))

        # ── Ensure storage directory exists ───────────────────────────────────
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # ── Stream to disk with size check ────────────────────────────────────
        video_id = str(uuid.uuid4())
        dest_path = UPLOAD_DIR / f"{video_id}{suffix}"

        try:
            total_bytes = 0
            chunk_size = 1024 * 1024  # 1 MB chunks
            with open(dest_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_SIZE_BYTES:
                        dest_path.unlink(missing_ok=True)
                        raise FileTooLargeError(total_bytes / (1024 * 1024), 2048)
                    f.write(chunk)
        except (FileTooLargeError, InvalidVideoFormatError):
            raise
        except Exception as exc:
            dest_path.unlink(missing_ok=True)
            raise UploadError(f"Failed to save uploaded file: {exc}") from exc

        size_mb = round(total_bytes / (1024 * 1024), 2)
        logger.info("upload.saved", video_id=video_id, filename=filename, size_mb=size_mb)

        # ── Probe metadata via OpenCV (no FFmpeg required) ────────────────────
        duration_seconds, fps, width, height = self._probe_metadata(str(dest_path))

        # ── Create DB record ──────────────────────────────────────────────────
        video = await crud.create_video(
            self._db,
            filename=filename,
            filepath=str(dest_path.resolve()),
            duration_seconds=duration_seconds,
            fps=fps,
            width=width,
            height=height,
            size_mb=size_mb,
        )

        logger.info(
            "upload.complete",
            video_id=video.id,
            duration=duration_seconds,
            fps=fps,
            resolution=f"{width}x{height}",
        )

        return {
            "video_id": video.id,
            "filename": filename,
            "duration_seconds": duration_seconds,
            "fps": fps,
            "width": width,
            "height": height,
            "size_mb": size_mb,
        }

    @staticmethod
    def _probe_metadata(filepath: str) -> tuple[float | None, float | None, int | None, int | None]:
        """Probe video metadata using OpenCV VideoCapture.

        Args:
            filepath: Absolute path to the video file on disk.

        Returns:
            Tuple of (duration_seconds, fps, width, height).
            All values may be None if probing fails.
        """
        try:
            cap = cv2.VideoCapture(filepath)
            if not cap.isOpened():
                logger.warning("upload.probe_failed", filepath=filepath)
                return None, None, None, None

            fps = cap.get(cv2.CAP_PROP_FPS) or None
            frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or None
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or None
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or None
            cap.release()

            duration_seconds = None
            if fps and frame_count:
                duration_seconds = round(frame_count / fps, 2)

            return duration_seconds, fps, width, height
        except Exception as exc:
            logger.warning("upload.probe_error", exc=str(exc))
            return None, None, None, None
