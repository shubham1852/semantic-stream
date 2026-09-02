"""
core/config.py
==============
Central application configuration for SemanticStream.

All configuration values are loaded from environment variables (via a .env
file in development).  No constant should be hardcoded anywhere else in the
codebase — import from this module instead.

Usage:
    from backend.core.config import settings
"""

from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Project Identity ────────────────────────────────────────────────────
    APP_NAME: str = "SemanticStream"
    APP_VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    DEBUG: bool = Field(default=False)

    # ── Server ──────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # ── Database ────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./semanticstream.db"

    # ── Storage Paths ────────────────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOAD_DIR: Path = STORAGE_DIR / "uploads"
    PROCESSED_DIR: Path = STORAGE_DIR / "processed"
    FRAMES_DIR: Path = STORAGE_DIR / "frames"
    REPORTS_DIR: Path = STORAGE_DIR / "reports"

    # ── Upload Constraints ───────────────────────────────────────────────────
    MAX_UPLOAD_SIZE_MB: int = 2048  # 2 GB
    ALLOWED_VIDEO_EXTENSIONS: List[str] = [".mp4", ".mov", ".avi", ".mkv"]

    # ── AI / Detection ───────────────────────────────────────────────────────
    YOLO_MODEL_PATH: Path = BASE_DIR / "models" / "weights" / "yolov8n.onnx"
    CONFIDENCE_THRESHOLD: float = 0.45
    NMS_THRESHOLD: float = 0.45
    INFERENCE_WIDTH: int = 640
    INFERENCE_HEIGHT: int = 480

    # ── Priority Tier Scores ─────────────────────────────────────────────────
    PRIORITY_P1: float = 1.0   # Face / Person
    PRIORITY_P2: float = 0.8   # Text overlays
    PRIORITY_P3: float = 0.6   # High optical-flow regions
    PRIORITY_P4: float = 0.4   # Other detected objects
    PRIORITY_P5: float = 0.1   # Background

    # ── Temporal Smoothing ───────────────────────────────────────────────────
    TEMPORAL_ALPHA: float = 0.3   # EMA weight for current frame
    FLOW_THRESHOLD: float = 2.0   # Pixels — optical flow magnitude cutoff

    # ── Graceful-Degradation Threshold ───────────────────────────────────────
    DEGRADED_CONFIDENCE_THRESHOLD: float = 0.5

    # ── QP Lookup (bitrate-to-QP for 720p/30fps) ────────────────────────────
    # Format: {qp_value: approximate_mbps}
    QP_BITRATE_TABLE: dict = {
        18: 4.0,
        24: 2.0,
        28: 1.2,
        34: 0.6,
        40: 0.3,
    }

    # Default per-tier QP values
    QP_P1: int = 18
    QP_P2: int = 22
    QP_P3: int = 26
    QP_P4: int = 32
    QP_P5: int = 40

    # Uniform ABR baseline QP
    QP_UNIFORM: int = 28

    # Static-ROI baseline QPs
    QP_STATIC_ROI_FACE: int = 20
    QP_STATIC_ROI_BG: int = 35

    # ── Bitrate Budget Allocation (fraction of total per tier) ────────────────
    BUDGET_P1: float = 0.40
    BUDGET_P2: float = 0.15
    BUDGET_P3: float = 0.20
    BUDGET_P4: float = 0.15
    BUDGET_P5: float = 0.10

    # Emergency budget (when buffer < 4 s)
    EMERGENCY_BUDGET_P1: float = 0.40
    EMERGENCY_BUDGET_P2: float = 0.15
    EMERGENCY_BUDGET_P3: float = 0.20
    EMERGENCY_BUDGET_P4: float = 0.10
    EMERGENCY_BUDGET_P5: float = 0.05

    # ── BOLA / Bandwidth ─────────────────────────────────────────────────────
    BANDWIDTH_SAFETY_MARGIN: float = 0.85
    BUFFER_TARGET_SECONDS: float = 8.0
    BUFFER_EMERGENCY_SECONDS: float = 4.0
    BUFFER_HIGH_BITRATE_FRACTION: float = 0.80
    BUFFER_EMERGENCY_FRACTION: float = 0.40
    BW_WINDOW_SIZE: int = 5

    # ── SPQI / Rate Control ───────────────────────────────────────────────────
    SPQI_P1_THRESHOLD: float = 0.75
    SPQI_REALLOC_STEP: float = 0.05

    # ── Scene Detection ───────────────────────────────────────────────────────
    HISTOGRAM_BINS: int = 32
    SCENE_CUT_THRESHOLD: float = 0.65
    SCENE_FRESH_FRAMES: int = 3
    MOTION_DOMINANT_THRESHOLD: float = 5.0
    TEXT_AREA_THRESHOLD: float = 0.20
    DIALOGUE_AREA_THRESHOLD: float = 0.60

    # ── HLS Streaming ─────────────────────────────────────────────────────────
    HLS_SEGMENT_DURATION: int = 4
    HLS_PLAYLIST_TYPE: str = "event"

    # ── Analysis Job Defaults ─────────────────────────────────────────────────
    DEFAULT_FRAME_SAMPLE_RATE: int = 5

    # ── WebSocket ─────────────────────────────────────────────────────────────
    WS_FRAME_RATE: int = 10

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True


# Singleton instance — import this everywhere
settings = Settings()

# Ensure storage directories exist at import time
for _dir in (
    settings.UPLOAD_DIR,
    settings.PROCESSED_DIR,
    settings.FRAMES_DIR,
    settings.REPORTS_DIR,
):
    _dir.mkdir(parents=True, exist_ok=True)
