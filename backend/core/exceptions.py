"""
core/exceptions.py
==================
Custom exception hierarchy for SemanticStream.

All domain-specific errors raised inside the service and utility layers
are subclasses of ``SemanticStreamError``.  FastAPI exception handlers
registered in ``main.py`` catch these types and convert them to structured
HTTP error responses.

Hierarchy:
    SemanticStreamError
    ├── VideoNotFoundError
    ├── JobNotFoundError
    ├── ExperimentNotFoundError
    ├── VideoProcessingError
    │   └── FFmpegError
    ├── DetectionError
    │   └── ModelLoadError
    ├── StorageError
    │   ├── UploadError
    │   └── FileTooLargeError
    ├── AnalysisError
    ├── ReportGenerationError
    ├── BandwidthProfileError
    └── WebSocketError
"""


class SemanticStreamError(Exception):
    """Base exception for all SemanticStream domain errors.

    Args:
        message: Human-readable description of the error.
        detail: Optional additional context (e.g. underlying exception message).
    """

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.message} — {self.detail}"
        return self.message


# ── Not Found ────────────────────────────────────────────────────────────────

class VideoNotFoundError(SemanticStreamError):
    """Raised when a requested video ID does not exist in the database."""


class JobNotFoundError(SemanticStreamError):
    """Raised when a requested analysis job ID does not exist."""


class ExperimentNotFoundError(SemanticStreamError):
    """Raised when a requested experiment ID does not exist."""


# ── Video Processing ─────────────────────────────────────────────────────────

class VideoProcessingError(SemanticStreamError):
    """Raised when a video processing operation fails."""


class FFmpegError(VideoProcessingError):
    """Raised when an FFmpeg subprocess call fails or returns a non-zero exit code."""


# ── AI / Detection ────────────────────────────────────────────────────────────

class DetectionError(SemanticStreamError):
    """Raised when the object detection pipeline fails."""


class ModelLoadError(DetectionError):
    """Raised when the ONNX model cannot be loaded from disk."""


# ── Storage ───────────────────────────────────────────────────────────────────

class StorageError(SemanticStreamError):
    """Raised when a file-system or storage operation fails."""


class UploadError(StorageError):
    """Raised when a file upload cannot be saved to disk."""


class FileTooLargeError(StorageError):
    """Raised when an uploaded file exceeds MAX_UPLOAD_SIZE_MB."""

    def __init__(self, size_mb: float, limit_mb: int) -> None:
        super().__init__(
            f"Upload rejected: file size {size_mb:.1f} MB exceeds the "
            f"{limit_mb} MB limit.",
        )
        self.size_mb = size_mb
        self.limit_mb = limit_mb


class InvalidVideoFormatError(StorageError):
    """Raised when the uploaded file has an unsupported extension."""

    def __init__(self, extension: str, allowed: list[str]) -> None:
        super().__init__(
            f"Unsupported file type '{extension}'. "
            f"Allowed: {', '.join(allowed)}",
        )


# ── Analysis ──────────────────────────────────────────────────────────────────

class AnalysisError(SemanticStreamError):
    """Raised when a metrics computation or analysis step fails."""


# ── Report Generation ─────────────────────────────────────────────────────────

class ReportGenerationError(SemanticStreamError):
    """Raised when PDF report generation fails."""


# ── Bandwidth ─────────────────────────────────────────────────────────────────

class BandwidthProfileError(SemanticStreamError):
    """Raised when an unknown or misconfigured bandwidth profile is requested."""


# ── WebSocket ─────────────────────────────────────────────────────────────────

class WebSocketError(SemanticStreamError):
    """Raised when a WebSocket communication error occurs."""
