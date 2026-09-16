"""
api/routes/demo.py
==================
GET /api/v1/demo/status — system component health summary.

Used by:
  * DashboardPage System Status card
  * LiveCameraPage mock-mode warning banner
  * Integration smoke tests and evaluation
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from typing import Any

import numpy as np
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.database import crud
from backend.database.database import get_db

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_yolo() -> dict[str, Any]:
    """Report current YOLO engine status and perform a quick inference probe."""
    try:
        from backend.models.yolo_engine import yolo_engine

        is_mock = getattr(yolo_engine, "is_mock", True)
        engine_mode = "MOCK_FALLBACK" if is_mock else "REAL_ONNX"

        inference_ms = -1.0
        try:
            start = time.perf_counter()
            test_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            yolo_engine.detect(test_frame)
            inference_ms = round((time.perf_counter() - start) * 1000, 1)
        except Exception:
            inference_ms = -1.0

        return {
            "status": "degraded" if is_mock else "ok",
            "mode": engine_mode,
            "inference_test_ms": inference_ms,
            "model_loaded": not is_mock,
            "detail": "ONNX model loaded and ready." if not is_mock else "ONNX model not found. Run export_onnx.py",
            "model_path": str(settings.YOLO_MODEL_PATH),
        }
    except Exception as exc:
        return {
            "status": "error",
            "mode": "UNKNOWN",
            "inference_test_ms": -1.0,
            "model_loaded": False,
            "detail": str(exc),
        }


def _check_ffmpeg() -> dict[str, Any]:
    """Verify ffmpeg is accessible and probe version."""
    try:
        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            known_paths = [
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"),
                r"C:\ffmpeg\bin\ffmpeg.exe",
            ]
            for kp in known_paths:
                if os.path.exists(kp):
                    ffmpeg_bin = kp
                    bin_dir = os.path.dirname(kp)
                    if bin_dir not in os.environ["PATH"]:
                        os.environ["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
                    break
        ffmpeg_bin = ffmpeg_bin or "ffmpeg"
        res = subprocess.run(
            [ffmpeg_bin, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ffmpeg_ok = res.returncode == 0
        ffmpeg_version = res.stdout.split("\n")[0] if ffmpeg_ok else "unavailable"
        return {
            "status": "ok" if ffmpeg_ok else "degraded",
            "available": ffmpeg_ok,
            "version": ffmpeg_version,
            "detail": f"Found: {ffmpeg_version}" if ffmpeg_ok else "ffmpeg not found on PATH. Video encoding will fail.",
        }
    except Exception as exc:
        return {
            "status": "degraded",
            "available": False,
            "version": "not found",
            "detail": str(exc),
        }


async def _check_database(db: AsyncSession) -> dict[str, Any]:
    """Verify database connectivity and count sessions."""
    try:
        jobs = await crud.list_jobs(db, limit=100)
        session_count = len(jobs) if jobs else 0
        return {
            "status": "ok",
            "connected": True,
            "total_sessions": session_count,
            "detail": f"Database connected ({session_count} total sessions recorded).",
        }
    except Exception as exc:
        return {
            "status": "error",
            "connected": False,
            "total_sessions": 0,
            "detail": str(exc),
        }


def _check_storage() -> dict[str, Any]:
    """Verify upload and processed storage directories exist and are writable."""
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


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/demo/status", summary="System component health snapshot", tags=["Demo"])
@router.get("/status", summary="System component health snapshot", tags=["Demo"])
async def demo_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return a comprehensive health snapshot for all SemanticStream system components."""
    ai_comp = _check_yolo()
    ffmpeg_comp = _check_ffmpeg()
    db_comp = await _check_database(db)
    storage_comp = _check_storage()
    hls_comp = _check_hls()

    components = {
        "ai_engine": ai_comp,
        "ffmpeg": ffmpeg_comp,
        "database": db_comp,
        "storage": storage_comp,
        "hls": hls_comp,
        "bandwidth_profiles": {
            "available": 5,
            "profiles": [
                "strong_wifi",
                "weak_wifi",
                "4g_degrading",
                "burst_loss",
                "stress_test",
            ],
        },
        "novel_metrics": {
            "spqi": "Semantic Perceptual Quality Index — active",
            "sees": "Semantic Energy Efficiency Score — active",
        },
    }

    is_mock = ai_comp.get("mode") == "MOCK_FALLBACK"
    overall_ok = (not is_mock) and db_comp.get("connected", False)

    payload = {
        "status": "ready" if overall_ok else "degraded",
        "overall": "ok" if overall_ok else "degraded",
        "components": components,
        "ai_engine": ai_comp,
        "ffmpeg": ffmpeg_comp,
        "database": db_comp,
        "storage": storage_comp,
        "hls": hls_comp,
        "project": {
            "name": "SemanticStream",
            "version": settings.APP_VERSION,
            "institution": "VIT Vellore",
            "course": "BITE314L — Multimedia Systems",
            "team": [
                "Mayukh Banerjee (23BIT0061)",
                "Shubham Kumar (23BIT0079)",
                "Yashwant Sahoo (23BIT0115)",
            ],
        },
    }

    return payload
