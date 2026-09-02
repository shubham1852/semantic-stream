"""
models/model_cache.py
=====================
Singleton model instance manager for SemanticStream.

Ensures that the YOLOv8 ONNX engine is loaded exactly once per process
lifetime and reused across all requests.  Thread-safe via asyncio lock.

Usage
-----
    from backend.models.model_cache import get_yolo_engine

    engine = await get_yolo_engine()
    detections = engine.infer(frame_bgr)
"""

from __future__ import annotations

import asyncio
from typing import Optional

from backend.core.logging_config import get_logger
from backend.models.yolo_engine import YOLOEngine

log = get_logger(__name__)

# ── Module-level singleton state ───────────────────────────────────────────────

_engine: Optional[YOLOEngine] = None
_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


# ── Public API ─────────────────────────────────────────────────────────────────

async def get_yolo_engine() -> YOLOEngine:
    """Return the singleton :class:`YOLOEngine`, loading it on first call.

    Uses an asyncio lock to prevent duplicate initialisation under concurrent
    request load.  Subsequent calls return the cached instance immediately.

    Returns
    -------
    YOLOEngine
        Loaded and ready-to-use inference engine.

    Raises
    ------
    ModelLoadError
        Propagated from :class:`YOLOEngine` if the ONNX file is present but
        cannot be parsed.
    """
    global _engine

    if _engine is not None:
        return _engine

    async with _get_lock():
        # Double-checked locking — another coroutine may have loaded it
        # while we were waiting for the lock.
        if _engine is not None:
            return _engine

        log.info("model_cache.loading", message="Initialising YOLOEngine singleton")
        _engine = YOLOEngine()
        log.info(
            "model_cache.ready",
            message="YOLOEngine singleton ready",
            mock_mode=_engine.is_mock,
        )

    return _engine


def get_yolo_engine_sync() -> YOLOEngine:
    """Synchronous accessor for the engine singleton.

    Returns the cached instance if already loaded, or creates a new one
    synchronously (suitable for startup or testing contexts where an event
    loop is not available).

    Returns
    -------
    YOLOEngine
        Loaded engine, possibly in mock mode if the ONNX file is absent.
    """
    global _engine

    if _engine is None:
        log.info("model_cache.sync_loading", message="Synchronous YOLOEngine initialisation")
        _engine = YOLOEngine()
        log.info("model_cache.sync_ready", mock_mode=_engine.is_mock)

    return _engine


async def release_engine() -> None:
    """Release the singleton and free any held resources.

    Intended for graceful shutdown in the FastAPI lifespan handler.
    Safe to call even if the engine was never loaded.
    """
    global _engine

    async with _get_lock():
        if _engine is not None:
            log.info("model_cache.releasing", message="Releasing YOLOEngine singleton")
            _engine = None
