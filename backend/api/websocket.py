"""
api/websocket.py
================
WebSocket endpoint at /ws/live for real-time camera frame processing.

Client sends base64-encoded JPEG frames; server responds with:
  - Priority heatmap (base64 PNG)
  - Detected object list with priority tiers and QP assignments
  - Current SPQI score and scene type
  - Processing latency in milliseconds

This handler delegates all computation to the detection and analytics
services.  The WebSocket handler itself only manages the connection
lifecycle and message serialisation.
"""

import asyncio
import base64
import json
import time

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.logging_config import get_logger
from backend.core.exceptions import WebSocketError

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/live")
async def live_camera_ws(websocket: WebSocket) -> None:
    """Handle real-time webcam frame analysis over WebSocket.

    Protocol:
        Client → Server: JSON ``{ "frame_base64": "<JPEG base64 string>" }``
        Server → Client: JSON ``{ "priority_map_base64": "...", "detections": [...],
                                   "spqi": float, "confidence": float,
                                   "scene_type": str, "current_qp_assignments": {...},
                                   "processing_time_ms": float }``

    Args:
        websocket: The WebSocket connection instance managed by FastAPI/Starlette.
    """
    await websocket.accept()
    logger.info("ws.live.connected", client=websocket.client)

    # Use module-level singletons (already initialised at startup)
    from backend.services.detection_service import detection_service
    from backend.services.analytics_service import AnalyticsService

    analytics_service = AnalyticsService(db=None)  # Stateless for WS mode
    frame_counter: int = 0

    try:
        while True:
            # Receive message
            raw = await websocket.receive_text()
            message = json.loads(raw)

            frame_b64 = message.get("frame_base64")
            if not frame_b64:
                await websocket.send_json(
                    {"error": "Missing 'frame_base64' in message."}
                )
                continue

            t_start = time.perf_counter()

            # Decode JPEG frame
            frame_bytes = base64.b64decode(frame_b64)
            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame_bgr = _decode_jpeg_array(frame_array)

            if frame_bgr is None:
                await websocket.send_json({"error": "Failed to decode frame."})
                continue

            # Run detection pipeline (blocking I/O offloaded to thread pool)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                detection_service.analyse_frame,
                frame_bgr,
                frame_counter,
                (time.perf_counter() - t_start) * 1000.0,
                "ws_live",
            )
            frame_counter += 1

            t_end = time.perf_counter()
            processing_ms = (t_end - t_start) * 1000.0

            response = analytics_service.summarise_frame(result)
            response["processing_time_ms"] = round(processing_ms, 2)
            await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.info("ws.live.disconnected", client=websocket.client)
    except Exception as exc:
        logger.exception("ws.live.error", exc_info=exc)
        try:
            await websocket.send_json({"error": str(exc)})
        except Exception:
            pass
        await websocket.close(code=1011)


def _decode_jpeg_array(frame_array: np.ndarray) -> np.ndarray | None:
    """Decode a raw JPEG byte array into a BGR numpy frame.

    Args:
        frame_array: 1-D uint8 numpy array of JPEG bytes.

    Returns:
        Decoded BGR frame or ``None`` on failure.
    """
    import cv2

    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
    return frame if frame is not None else None



