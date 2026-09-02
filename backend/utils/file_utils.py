"""
utils/file_utils.py
===================
File and path management utilities for SemanticStream.

Responsibilities
----------------
* Construct canonical storage paths for uploads, frames, processed
  videos, and PDF reports — all based on ``settings`` paths so nothing
  is ever hardcoded.
* Validate uploaded file metadata (extension, size) before writing to
  disk.
* Provide safe atomic write helpers (write-to-temp, then rename) to
  avoid partially written files being read by other coroutines.
* Clean up stale session artifacts after a configurable retention period.

All paths are :class:`pathlib.Path` objects.  String concatenation is
never used for path construction.
"""

from __future__ import annotations

import hashlib
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

from backend.core.config import settings
from backend.core.exceptions import StorageError
from backend.core.logging_config import get_logger

log = get_logger(__name__)

# ── Allowed upload extensions ──────────────────────────────────────────────────

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".mov", ".avi", ".mkv", ".webm"})

# ── Path builders ──────────────────────────────────────────────────────────────


def upload_path(video_id: str, filename: str) -> Path:
    """Return the canonical path for an uploaded video file.

    Parameters
    ----------
    video_id:
        UUID string assigned to the uploaded video.
    filename:
        Original filename supplied by the client (used to preserve extension).

    Returns
    -------
    Path
        Absolute path under ``settings.UPLOAD_DIR``.
    """
    ext = Path(filename).suffix.lower()
    return settings.UPLOAD_DIR / f"{video_id}{ext}"


def frame_dir(video_id: str) -> Path:
    """Return the directory used to cache extracted frames for a video.

    Parameters
    ----------
    video_id:
        UUID string.

    Returns
    -------
    Path
        Directory path under ``settings.FRAMES_DIR``.  Created on first call.
    """
    path = settings.FRAMES_DIR / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def frame_path(video_id: str, frame_number: int) -> Path:
    """Return the path for a cached extracted frame JPEG.

    Parameters
    ----------
    video_id:
        UUID string.
    frame_number:
        Zero-indexed frame number.

    Returns
    -------
    Path
        ``{frames_dir}/{video_id}/frame_{frame_number:06d}.jpg``
    """
    return frame_dir(video_id) / f"frame_{frame_number:06d}.jpg"


def processed_path(video_id: str, suffix: str = "_encoded.mp4") -> Path:
    """Return the canonical path for a processed (encoded) video.

    Parameters
    ----------
    video_id:
        UUID string.
    suffix:
        File suffix appended after the video_id (default ``_encoded.mp4``).

    Returns
    -------
    Path
        Absolute path under ``settings.PROCESSED_DIR``.
    """
    return settings.PROCESSED_DIR / f"{video_id}{suffix}"


def hls_dir(video_id: str) -> Path:
    """Return the HLS segment output directory for a processed video.

    Parameters
    ----------
    video_id:
        UUID string.

    Returns
    -------
    Path
        Directory path under ``settings.PROCESSED_DIR / video_id / hls``.
    """
    path = settings.PROCESSED_DIR / video_id / "hls"
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_path(session_id: str) -> Path:
    """Return the canonical path for a generated PDF report.

    Parameters
    ----------
    session_id:
        UUID string (analysis job ID used as session identifier).

    Returns
    -------
    Path
        ``{reports_dir}/{session_id}.pdf``
    """
    return settings.REPORTS_DIR / f"{session_id}.pdf"


# ── Validation ─────────────────────────────────────────────────────────────────


def validate_upload(filename: str, size_bytes: int) -> None:
    """Validate an uploaded file's extension and size.

    Parameters
    ----------
    filename:
        Original filename from the client.
    size_bytes:
        File size in bytes.

    Raises
    ------
    StorageError
        If the extension is not allowed or the file exceeds the configured
        maximum size.
    """
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise StorageError(
            f"File type '{ext}' is not supported. "
            f"Allowed types: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if size_bytes > max_bytes:
        raise StorageError(
            f"File size {size_bytes / (1024**2):.1f} MB exceeds "
            f"the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )


# ── Atomic write helpers ────────────────────────────────────────────────────────


async def save_upload(source_bytes: bytes, video_id: str, filename: str) -> Path:
    """Write upload bytes to the canonical upload path atomically.

    Writes to a temporary ``.tmp`` file first, then renames to avoid
    partially written files being visible to other coroutines.

    Parameters
    ----------
    source_bytes:
        Raw bytes of the uploaded video file.
    video_id:
        UUID string assigned to the video.
    filename:
        Original filename (used for extension).

    Returns
    -------
    Path
        The final file path after the atomic rename.

    Raises
    ------
    StorageError
        If writing or renaming fails.
    """
    dest = upload_path(video_id, filename)
    tmp  = dest.with_suffix(".tmp")

    try:
        settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(source_bytes)
        tmp.rename(dest)
        log.info("file_utils.saved", path=str(dest), size_bytes=len(source_bytes))
        return dest
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise StorageError(f"Failed to save upload to {dest}: {exc}") from exc


def compute_sha256(path: Path) -> str:
    """Compute the SHA-256 hash of a file for integrity checking.

    Parameters
    ----------
    path:
        Absolute path to the file.

    Returns
    -------
    str
        Lowercase hex-encoded SHA-256 digest.
    """
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


# ── Cleanup ─────────────────────────────────────────────────────────────────────


def cleanup_session(video_id: str) -> None:
    """Remove all cached artifacts for a video session.

    Deletes the extracted frame cache directory.  Processed videos and
    uploads are retained (managed separately).

    Parameters
    ----------
    video_id:
        UUID string.
    """
    frames = settings.FRAMES_DIR / video_id
    if frames.exists():
        shutil.rmtree(frames, ignore_errors=True)
        log.info("file_utils.cleanup", video_id=video_id, removed=str(frames))


def purge_old_frames(max_age_hours: float = 24.0) -> int:
    """Delete frame cache directories older than ``max_age_hours``.

    Parameters
    ----------
    max_age_hours:
        Age threshold in hours.

    Returns
    -------
    int
        Number of directories purged.
    """
    cutoff = time.time() - max_age_hours * 3600
    count = 0
    for entry in settings.FRAMES_DIR.iterdir():
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry, ignore_errors=True)
            count += 1
            log.info("file_utils.purged", path=str(entry))
    return count


def ensure_storage_dirs() -> None:
    """Create all required storage directories if they do not exist.

    Called during application startup (FastAPI lifespan).
    """
    for directory in (
        settings.UPLOAD_DIR,
        settings.PROCESSED_DIR,
        settings.FRAMES_DIR,
        settings.REPORTS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    log.info("file_utils.dirs_ready", base=str(settings.STORAGE_DIR))
