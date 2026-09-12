"""
api/routes/demo.py
==================
GET /api/v1/demo/status — system component health summary.

Used by:
  * DashboardPage System Status card
  * LiveCameraPage mock-mode warning banner
  * Integration smoke tests

This endpoint performs lightweight, non-blocking checks on each system
component and returns a single JSON snapshot.  It intentionally avoids
heavy DB queries — it only touches the module singletons that are already
loaded in memory.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from fastapi import APIRouter

from backend.core.config import settings
from backend.core.logging_config import get_logger

log = get_logger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_yolo() -> dict[str, Any]:
    """Report the current YOLO engine mode and model path."""
    try:
        from backend.models.yolo_engine import yolo_engine

        if yolo_engine.is_mock:
            return {
                "status": "degraded",
                "mode": "MOCK_FALLBACK",
                "detail": "ONNX model not found. Run: python backend/models/export_onnx.py",
                "model_path": str(settings.YOLO_MODEL_PATH),
            }
        return {
            "status": "ok",
            "mode": "REAL_ONNX",
            "detail": "ONNX model loaded and ready.",
            "model_path": str(settings.YOLO_MODEL_PATH),
        }
    except Exception as exc:
        return {"status": "error", "mode": "UNKNOWN", "detail": str(exc)}


def _check_database() -> dict[str, Any]:
    """Return ok if the database file / connection string is reachable."""
    try:
        db_url = str(settings.DATABASE_URL)
        # For SQLite — check the file exists
        if "sqlite" in db_url:
            db_file = db_url.replace("sqlite+aiosqlite:///", "").split("?")[0]
            if os.path.exists(db_file):
                return {"status": "ok", "detail": "SQLite database file present."}
            return {"status": "degraded", "detail": "SQLite file not found — run migrations."}
        return {"status": "ok", "detail": "Non-SQLite DB configured (file check skipped)."}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_ffmpeg() -> dict[str, Any]:
    """Verify ffmpeg is on PATH."""
    try:
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return {"status": "ok", "detail": f"Found at {ffmpeg_path}"}
        return {
            "status": "degraded",
            "detail": "ffmpeg not found on PATH. Video encoding will fail.",
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_storage() -> dict[str, Any]:
    """Verify the upload and processed storage directories exist and are writable."""
    try:
        upload_dir = str(settings.UPLOAD_DIR)
        processed_dir = str(settings.PROCESSED_DIR)
        issues = []
        for d in (upload_dir, processed_dir):
            if not os.path.isdir(d):
                issues.append(f"{d} missing")
            elif not os.access(d, os.W_OK):
                issues.append(f"{d} not writable")
        if issues:
            return {"status": "degraded", "detail": "; ".join(issues)}
        return {
            "status": "ok",
            "detail": "Upload and processed directories are present and writable.",
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


def _check_hls() -> dict[str, Any]:
    """Check that the HLS output directory exists."""
    try:
        hls_root = getattr(settings, "HLS_DIR", None) or getattr(settings, "PROCESSED_DIR", None)
        if hls_root and os.path.isdir(str(hls_root)):
            return {"status": "ok", "detail": "HLS output directory ready."}
        return {"status": "degraded", "detail": "HLS output directory not found."}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get(
    "/demo/status",
    summary="System component health snapshot",
    tags=["Demo"],
)
async def demo_status() -> dict[str, Any]:
    """Return a health snapshot for all 5 SemanticStream system components.

    Used by the Dashboard System Status card and the Live Camera mock-mode
    warning banner to surface degraded components to the user.

    Returns
    -------
    Dict with keys:
        ``ai_engine``, ``database``, ``ffmpeg``, ``storage``, ``hls``
    Each value is a dict with at minimum ``status`` ("ok" | "degraded" | "error")
    and ``detail`` (human-readable explanation).
    """
    components = {
        "ai_engine": _check_yolo(),
        "database": _check_database(),
        "ffmpeg": _check_ffmpeg(),
        "storage": _check_storage(),
        "hls": _check_hls(),
    }

    overall_ok = all(c.get("status") == "ok" for c in components.values())
    any_error = any(c.get("status") == "error" for c in components.values())

    log.info(
        "demo.status_check",
        overall="ok" if overall_ok else ("error" if any_error else "degraded"),
    )

    return {
        "overall": "ok" if overall_ok else ("error" if any_error else "degraded"),
        **components,
    }
