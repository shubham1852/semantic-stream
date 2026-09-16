"""
api/websocket.py
================
WebSocket endpoint at /ws/live for real-time camera frame processing.

Client sends base64-encoded JPEG frames; server responds with:
  - Priority heatmap (base64 JPEG with jet colormap)
  - Detected object list with priority tiers and QP assignments
  - Priority Coverage Score (PCS) and scene classification
  - Processing latency in milliseconds (optimised for <200ms CPU execution)

Optimisations applied (Phase 10):
  1. Input resize to 640x640 before YOLO inference with coordinate re-scaling
  2. Strategic frame-skipping (inference every 2nd frame, reusing detections)
  3. Half-resolution JPEG heatmap encoding with COLORMAP_JET
  4. Farneback optical flow downscaled to 320x240 for real-time motion detection (P3)
  5. Solid filled priority map regions (P1=1.00, P3=0.60, P4=0.40, P5=0.10)
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.models.yolo_engine import Detection, yolo_engine

logger = get_logger(__name__)

router = APIRouter()


# ── Priority Map Builder ──────────────────────────────────────────────────────

def build_priority_map(
    frame_height: int,
    frame_width: int,
    detections: List[Detection],
    optical_flow_mag: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Build a filled priority map where every pixel has a priority score.

    Higher score = more important = lower QP = higher quality.

    Priority tiers:
      P5 = 0.10  Background — entire frame starts here
      P4 = 0.40  Other detected objects
      P3 = 0.60  Motion regions (optical flow)
      P2 = 0.80  Text overlays
      P1 = 1.00  Face / Person — drawn last, highest priority
    """
    # Step 1: Initialize entire frame as P5 (background)
    priority_map = np.full(
        (frame_height, frame_width),
        fill_value=0.10,
        dtype=np.float32,
    )

    # Step 2: Fill motion regions P3 (optical flow magnitude)
    if optical_flow_mag is not None:
        flow_norm = cv2.normalize(optical_flow_mag, None, 0, 1, cv2.NORM_MINMAX)
        motion_mask = flow_norm > 0.3  # threshold
        priority_map[motion_mask] = 0.60

    # Step 3: Fill P4 detected object boxes (non-person classes)
    for det in detections:
        tier = getattr(det, "priority_tier", "") or ("P1" if det.is_person else "P4")
        if tier == "P4":
            x1 = max(0, min(int(det.x1), frame_width - 1))
            x2 = max(0, min(int(det.x2), frame_width - 1))
            y1 = max(0, min(int(det.y1), frame_height - 1))
            y2 = max(0, min(int(det.y2), frame_height - 1))
            if x2 > x1 and y2 > y1:
                priority_map[y1:y2, x1:x2] = 0.40

    # Step 4: Fill P1 face/person boxes LAST (highest priority wins)
    for det in detections:
        tier = getattr(det, "priority_tier", "") or ("P1" if det.is_person else "P4")
        if tier in ("P1", "P2"):
            score = 1.00 if tier == "P1" else 0.80
            x1 = max(0, min(int(det.x1), frame_width - 1))
            x2 = max(0, min(int(det.x2), frame_width - 1))
            y1 = max(0, min(int(det.y1), frame_height - 1))
            y2 = max(0, min(int(det.y2), frame_height - 1))
            if x2 > x1 and y2 > y1:
                priority_map[y1:y2, x1:x2] = score

    return priority_map


def priority_map_to_heatmap_jpg_b64(priority_map: np.ndarray) -> str:
    """Convert float priority map to jet colormap JPEG base64 string.

    Applies COLORMAP_JET (blue=low priority background, red=high priority face).
    Resizes to half resolution before JPEG encode for ~75% faster encoding.
    """
    h, w = priority_map.shape[:2]
    scaled = (priority_map * 255.0).clip(0, 255).astype(np.uint8)
    heatmap_bgr = cv2.applyColorMap(scaled, cv2.COLORMAP_JET)

    # Optimization 3: Halve resolution before encoding
    heatmap_small = cv2.resize(
        heatmap_bgr,
        (max(1, w // 2), max(1, h // 2)),
        interpolation=cv2.INTER_LINEAR,
    )
    _, buffer = cv2.imencode(".jpg", heatmap_small, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return base64.b64encode(buffer.tobytes()).decode("utf-8")


# ── Frame Processing Pipeline ─────────────────────────────────────────────────

def _process_live_frame(
    frame_bgr: np.ndarray,
    frame_counter: int,
    prev_gray: Optional[np.ndarray],
    last_detections: List[Detection],
) -> Tuple[dict, np.ndarray, List[Detection]]:
    """Process a single live camera frame with all 4 latency optimizations."""
    h, w = frame_bgr.shape[:2]

    # ── 1. Optical Flow for Motion Detection (P3) ───────────────────────────
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gray_small = cv2.resize(gray, (320, 240), interpolation=cv2.INTER_LINEAR)

    flow_mag: Optional[np.ndarray] = None
    motion_area_frac: float = 0.0
    if prev_gray is not None and prev_gray.shape == gray_small.shape:
        try:
            flow = cv2.calcOpticalFlowFarneback(
                prev_gray,
                gray_small,
                None,
                pyr_scale=0.5,
                levels=2,
                winsize=15,
                iterations=2,
                poly_n=5,
                poly_sigma=1.1,
                flags=0,
            )
            mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            flow_mag = cv2.resize(mag, (w, h), interpolation=cv2.INTER_LINEAR)
            motion_area_frac = float(np.mean(flow_mag > 2.0))
        except Exception as exc:
            logger.debug("ws.flow_error", error=str(exc))

    # ── 2. Strategic Frame-Skip & Inference Resize (Optimizations 1 & 2) ─────
    should_infer = (frame_counter % 2 == 0) or not last_detections
    if should_infer:
        # Optimization 1: Resize to 640x640 before sending to engine
        frame_for_infer = cv2.resize(frame_bgr, (640, 640), interpolation=cv2.INTER_LINEAR)
        raw_dets = yolo_engine.detect(frame_for_infer, conf_threshold=0.40)

        # Scale detection coordinates back to original frame dimensions
        scale_x = w / 640.0
        scale_y = h / 640.0
        detections: List[Detection] = []
        for det in raw_dets:
            x1 = max(0, min(int(det.x1 * scale_x), w - 1))
            y1 = max(0, min(int(det.y1 * scale_y), h - 1))
            x2 = max(0, min(int(det.x2 * scale_x), w - 1))
            y2 = max(0, min(int(det.y2 * scale_y), h - 1))
            if x2 > x1 and y2 > y1:
                detections.append(
                    Detection(
                        class_id=det.class_id,
                        class_name=det.class_name,
                        confidence=round(det.confidence, 3),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                        priority_tier=det.priority_tier,
                    )
                )
        current_detections = detections
    else:
        current_detections = list(last_detections)

    # ── 3. Build Solid Filled Priority Map ───────────────────────────────────
    priority_map = build_priority_map(h, w, current_detections, optical_flow_mag=flow_mag)

    # Compute Priority Coverage Score (PCS)
    total_px = priority_map.size or 1
    high_pri_px = np.sum(priority_map >= 0.80)
    pcs = round(float(high_pri_px / total_px * 100.0), 1)

    priority_stats = {
        "p1_frac": float(np.sum(priority_map >= 1.0) / total_px),
        "p2_frac": float(np.sum((priority_map >= 0.8) & (priority_map < 1.0)) / total_px),
        "p3_frac": float(np.sum((priority_map >= 0.6) & (priority_map < 0.8)) / total_px),
        "p4_frac": float(np.sum((priority_map >= 0.4) & (priority_map < 0.6)) / total_px),
        "p5_frac": float(np.sum(priority_map < 0.4) / total_px),
    }

    # ── 4. Encode Heatmap (Optimization 3) ───────────────────────────────────
    heatmap_b64 = priority_map_to_heatmap_jpg_b64(priority_map)

    # ── 5. Scene Classification ──────────────────────────────────────────────
    has_person = any(d.priority_tier == "P1" for d in current_detections)
    high_motion = motion_area_frac >= 0.05
    if has_person and high_motion:
        scene_type = "ACTION"
    elif has_person:
        scene_type = "DIALOGUE"
    elif high_motion:
        scene_type = "MOTION"
    else:
        scene_type = "GENERAL"

    # ── 6. Serialise Detections ──────────────────────────────────────────────
    serialised = [
        {
            "class_id": d.class_id,
            "class_name": d.class_name,
            "confidence": d.confidence,
            "x1": d.x1,
            "y1": d.y1,
            "x2": d.x2,
            "y2": d.y2,
            "bbox": [d.x1, d.y1, d.x2 - d.x1, d.y2 - d.y1],
            "is_person": d.is_person,
            "area": d.area,
            "priority_tier": d.priority_tier,
        }
        for d in current_detections
    ]

    avg_conf = (
        round(float(np.mean([d.confidence for d in current_detections])), 3)
        if current_detections else 0.0
    )

    result_dict = {
        "frame_number": frame_counter,
        "scene_type": scene_type,
        "spqi": None,  # No reference frame in live mode
        "pcs": pcs,
        "confidence": avg_conf,
        "text_area_frac": 0.0,
        "motion_area_frac": round(motion_area_frac, 4),
        "priority_stats": priority_stats,
        "detections": serialised,
        "current_qp_assignments": {
            "P1_person_face": settings.QP_P1,
            "P2_text": settings.QP_P2,
            "P3_motion": settings.QP_P3,
            "P4_objects": settings.QP_P4,
            "P5_background": settings.QP_P5,
        },
        "priority_map_base64": heatmap_b64,
    }

    return result_dict, gray_small, current_detections


# ── WebSocket Route ───────────────────────────────────────────────────────────

@router.websocket("/ws/live")
async def live_camera_ws(websocket: WebSocket) -> None:
    """Handle real-time webcam frame analysis over WebSocket."""
    await websocket.accept()
    logger.info("ws.live.connected", client=websocket.client)

    frame_counter: int = 0
    prev_gray: Optional[np.ndarray] = None
    last_detections: List[Detection] = []

    try:
        while True:
            # Receive frame payload
            raw = await websocket.receive_text()
            message = json.loads(raw)

            frame_b64 = message.get("frame_base64")
            if not frame_b64:
                await websocket.send_json({"error": "Missing 'frame_base64' in message."})
                continue

            t_start = time.perf_counter()

            # Decode JPEG frame
            frame_bytes = base64.b64decode(frame_b64)
            frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
            frame_bgr = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame_bgr is None:
                await websocket.send_json({"error": "Failed to decode frame."})
                continue

            # Process frame in thread pool to prevent blocking asyncio loop
            payload, prev_gray, last_detections = await asyncio.get_event_loop().run_in_executor(
                None,
                _process_live_frame,
                frame_bgr,
                frame_counter,
                prev_gray,
                last_detections,
            )
            frame_counter += 1

            t_end = time.perf_counter()
            proc_ms = round((t_end - t_start) * 1000.0, 2)
            payload["timestamp_ms"] = proc_ms
            payload["processing_time_ms"] = proc_ms
            payload["processing_ms"] = proc_ms

            await websocket.send_json(payload)

    except WebSocketDisconnect:
        logger.info("ws.live.disconnected", client=websocket.client)
    except Exception as exc:
        logger.exception("ws.live.error", exc_info=exc)
        try:
            await websocket.send_json({"error": str(exc)})
        except Exception:
            pass
        await websocket.close(code=1011)



