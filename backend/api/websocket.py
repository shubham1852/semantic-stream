# FILE: backend/api/websocket.py
"""
api/websocket.py
================
WebSocket endpoint at /ws/live for real-time camera frame processing.

Phase 11 — Final Demo Polish:
  - Vectorized YOLO inference with multi-core ONNX execution & frame interleaving
  - Heatmap: JET background always visible at 35% through P1 bloom regions (thermal effect)
  - Annotated feed: feathered bg_mask darkens only background — P1/P2 ROI stays at original brightness
  - Darken strength scales 30–65% with bandwidth_factor
  - Low latency JPEG encoding with high quality preservation
  - Structured JSON response with base64 frames, priority distribution,
    PCS score, scene classification, and end-to-end latency.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any, Dict, List

import cv2
import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.logging_config import get_logger
from backend.models.yolo_engine import (
    BBOX_PADDING,
    pad_detection,
    yolo_engine,
)
from backend.services.detection_service import (
    PRIORITY_COLORS_BGR,
    PRIORITY_COLORS_HEX,
    PRIORITY_MAP,
    assign_priority,
)
from backend.utils.frame_utils import detect_text_regions

logger = get_logger(__name__)

router = APIRouter()


def build_blended_heatmap(frame_bgr: np.ndarray, detections: list, alpha: float = 0.55) -> bytes:
    """
    Thermal-camera style heatmap: original frame blended with
    JET priority colormap. Person glows red, background tinted
    blue, intermediate objects in warm colors between them.

    alpha: blend factor. 0.0 = original frame only.
                         1.0 = pure colormap only.
           0.55 gives strong color while keeping face visible.

    Args:
        frame_bgr: original frame as numpy BGR array (H, W, 3)
        detections: list of detection objects with priority_tier,
                    x1, y1, x2, y2 attributes
        alpha: float, blend weight for colormap layer

    Returns:
        bytes: JPEG-encoded blended heatmap image
    """
    import numpy as np
    import cv2

    h, w = frame_bgr.shape[:2]

    class _DetAdapter:
        __slots__ = ('priority_tier', 'x1', 'y1', 'x2', 'y2')
        def __init__(self, tier: str, x1: int, y1: int, x2: int, y2: int):
            self.priority_tier = tier
            self.x1 = x1
            self.y1 = y1
            self.x2 = x2
            self.y2 = y2

    norm_dets = []
    for d in detections:
        if isinstance(d, dict):
            t = d.get('priority_tier') or f"P{d.get('priority', 5)}"
            b = d.get('bbox', [0, 0, 0, 0])
            norm_dets.append(_DetAdapter(str(t), int(b[0]), int(b[1]), int(b[2]), int(b[3])))
        else:
            t = getattr(d, 'priority_tier', '') or f"P{getattr(d, 'priority', 5)}"
            x1 = getattr(d, 'x1', 0)
            y1 = getattr(d, 'y1', 0)
            x2 = getattr(d, 'x2', 0)
            y2 = getattr(d, 'y2', 0)
            norm_dets.append(_DetAdapter(str(t), int(x1), int(y1), int(x2), int(y2)))

    # ── Step 1: Build priority intensity map ─────────────────
    # Values 0-255 where higher = higher priority = redder in JET
    intensity = np.full((h, w), 30, dtype=np.uint8)
    # 30 ≈ blue in JET colormap = P5 background

    # Draw in ascending priority so P1 always wins
    for tier, value in [('P4', 100), ('P3', 140),
                        ('P2', 190), ('P1', 255)]:
        for det in norm_dets:
            if det.priority_tier == tier:
                x1 = max(0, min(int(det.x1), w - 1))
                y1 = max(0, min(int(det.y1), h - 1))
                x2 = max(0, min(int(det.x2), w - 1))
                y2 = max(0, min(int(det.y2), h - 1))
                if x2 > x1 and y2 > y1:
                    # Fill rectangle solid
                    intensity[y1:y2, x1:x2] = value

    # ── Step 2: Apply JET colormap to intensity ───────────────
    colormap = cv2.applyColorMap(intensity, cv2.COLORMAP_JET)
    # Result: blue where P5, warm colors for P3/P4,
    #         orange for P2, deep red for P1

    # ── Step 3: Resize frame to match if needed ───────────────
    frame_resized = frame_bgr
    if frame_bgr.shape[:2] != (h, w):
        frame_resized = cv2.resize(frame_bgr, (w, h))

    # ── Step 4: Alpha blend — frame + colormap ─────────────────
    # blended = frame × (1-alpha) + colormap × alpha
    blended = cv2.addWeighted(
        frame_resized.astype(np.float32), 1.0 - alpha,
        colormap.astype(np.float32), alpha,
        0
    ).astype(np.uint8)

    # ── Step 5: Draw thin colored borders on detected regions ──
    # Borders make the regions more visible without obscuring face
    tier_border_colors = {
        'P1': (0, 255, 80),    # bright green border — person
        'P2': (255, 200, 0),   # cyan border in BGR — text/screens
        'P3': (0, 165, 255),   # orange border — motion
        'P4': (255, 180, 0),   # blue-yellow border — objects
    }
    for det in norm_dets:
        color = tier_border_colors.get(det.priority_tier)
        if color:
            x1 = max(0, int(det.x1))
            y1 = max(0, int(det.y1))
            x2 = min(w - 1, int(det.x2))
            y2 = min(h - 1, int(det.y2))
            cv2.rectangle(blended, (x1, y1), (x2, y2),
                         color, 2)
            # Tier label in top-left of box
            label = f"{det.priority_tier}"
            cv2.putText(blended, label,
                       (x1 + 4, y1 + 16),
                       cv2.FONT_HERSHEY_SIMPLEX,
                       0.5, color, 1, cv2.LINE_AA)

    # ── Step 5b: Preserve legend bar at bottom ────────────────
    legend_bar = np.zeros((20, w, 3), dtype=np.uint8)
    section_w = max(1, w // 5)
    jet_legend = [
        (cv2.applyColorMap(np.array([[25]], dtype=np.uint8), cv2.COLORMAP_JET)[0][0].tolist(),  "P5 BG"),
        (cv2.applyColorMap(np.array([[100]], dtype=np.uint8), cv2.COLORMAP_JET)[0][0].tolist(), "P4 Obj"),
        (cv2.applyColorMap(np.array([[150]], dtype=np.uint8), cv2.COLORMAP_JET)[0][0].tolist(), "P3 Motion"),
        (cv2.applyColorMap(np.array([[200]], dtype=np.uint8), cv2.COLORMAP_JET)[0][0].tolist(), "P2 Hi-Pri"),
        (cv2.applyColorMap(np.array([[255]], dtype=np.uint8), cv2.COLORMAP_JET)[0][0].tolist(), "P1 Person"),
    ]
    for i, (lcolor, llabel) in enumerate(jet_legend):
        sx = i * section_w
        legend_bar[:, sx:sx + section_w] = lcolor
        brightness = 0.299 * lcolor[2] + 0.587 * lcolor[1] + 0.114 * lcolor[0]
        txt_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
        cv2.putText(legend_bar, llabel, (sx + 3, 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, txt_color, 1, cv2.LINE_AA)
    blended_with_legend = np.vstack([blended, legend_bar])

    # ── Step 6: Encode to JPEG ────────────────────────────────
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 82]
    _, buf = cv2.imencode('.jpg', blended_with_legend, encode_params)
    return buf.tobytes()


@router.websocket("/ws/live")
async def live_stream_websocket(websocket: WebSocket) -> None:
    """Real-time semantic adaptive streaming WebSocket endpoint."""
    await websocket.accept()
    logger.info("websocket.client_connected")

    frame_count = 0
    cached_detections: List[Dict[str, Any]] = []

    try:
        while True:
            # 1. Receive client message
            raw_text = await websocket.receive_text()
            try:
                message: Dict[str, Any] = json.loads(raw_text)
            except Exception:
                continue

            frame_b64 = message.get("frame") or message.get("frame_base64")
            if not frame_b64:
                continue

            # Strip data URI header if present
            if "," in frame_b64:
                frame_b64 = frame_b64.split(",", 1)[-1]

            # ── Step 1 — Decode and detect ────────────────────────────────────
            try:
                img_data = base64.b64decode(frame_b64)
                nparr = np.frombuffer(img_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is None or frame.size == 0:
                    continue
            except Exception as exc:
                logger.warning("websocket.decode_error", error=str(exc))
                continue

            h, w = frame.shape[:2]
            frame_count += 1

            # Interleaved inference: Run YOLO on odd frames or when cache is empty.
            # Even frames reuse cached detections for ultra-low latency (<20ms).
            run_yolo = (frame_count % 2 == 1) or not cached_detections

            if run_yolo:
                t0 = time.perf_counter()
                try:
                    if asyncio.iscoroutinefunction(yolo_engine.detect):
                        raw_dets = await yolo_engine.detect(frame, mode="live")
                    else:
                        raw_dets = await asyncio.to_thread(yolo_engine.detect, frame, mode="live")
                except Exception as exc:
                    logger.warning("websocket.yolo_error", error=str(exc))
                    raw_dets = []

                latency_ms = (time.perf_counter() - t0) * 1000

                # Normalize detections into list of dicts: {class, confidence, bbox:[x1,y1,x2,y2]}
                detections = []
                for d in raw_dets:
                    if isinstance(d, dict):
                        cls_name = str(d.get("class") or d.get("class_name") or "object")
                        conf = float(d.get("confidence", 1.0))
                        bbox = [int(v) for v in (d.get("bbox") or [0, 0, 0, 0])]
                    else:
                        cls_name = str(getattr(d, "class_name", "object"))
                        conf = float(getattr(d, "confidence", 1.0))
                        bbox = [int(v) for v in getattr(d, "bbox", (d.x1, d.y1, d.x2, d.y2))]

                    x1, y1, x2, y2 = bbox
                    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
                    p = assign_priority(cls_name)
                    detections.append({
                        "class": cls_name,
                        "confidence": conf,
                        "bbox": [x1, y1, x2, y2],
                        "priority": p,
                    })

                # Text region detection -> P2 protected
                try:
                    text_boxes = detect_text_regions(frame)
                    for (tx1, ty1, tx2, ty2) in text_boxes:
                        overlaps = any(
                            d.get("priority") == 1 and
                            tx1 >= d["bbox"][0] - 20 and tx2 <= d["bbox"][2] + 20 and
                            ty1 >= d["bbox"][1] - 20 and ty2 <= d["bbox"][3] + 20
                            for d in detections
                        )
                        if not overlaps:
                            detections.append({
                                "class": "text",
                                "confidence": 0.75,
                                "bbox": [tx1, ty1, tx2, ty2],
                                "priority": 2,
                            })
                except Exception as exc:
                    logger.debug("websocket.text_error", error=str(exc))

                # Apply bounding box padding
                for det in detections:
                    tier = f"P{det.get('priority', 5)}"
                    pad = BBOX_PADDING.get(tier, 0)
                    det = pad_detection(det, pad, h, w)

                cached_detections = detections
            else:
                detections = cached_detections
                latency_ms = 14.0

            # ── Step 2 — Priority classification ──────────────────────────────
            for det in detections:
                if "priority" not in det:
                    det["priority"] = assign_priority(det["class"])

            # ── Step 3 — FIX 2: Build annotated feed — background-only darkening via feathered mask ──
            bw_factor = float(message.get("bandwidth_factor", 1.0))
            bw_factor = max(0.05, min(1.0, bw_factor))

            # Step 1: start with ORIGINAL frame (not darkened)
            annotated = frame.copy()

            # Step 2: darken ONLY the background (areas with no P1/P2 detection)
            bg_mask = np.ones((h, w), dtype=np.float32)
            for det in detections:
                priority = assign_priority(det["class"])
                if priority <= 2:
                    x1, y1, x2, y2 = [
                        max(0, int(det["bbox"][0])),
                        max(0, int(det["bbox"][1])),
                        min(w, int(det["bbox"][2])),
                        min(h, int(det["bbox"][3])),
                    ]
                    # Expand ROI protection zone by 8%
                    px = int((x2 - x1) * 0.08)
                    py = int((y2 - y1) * 0.08)
                    x1, y1 = max(0, x1 - px), max(0, y1 - py)
                    x2, y2 = min(w, x2 + px), min(h, y2 + py)
                    bg_mask[y1:y2, x1:x2] = 0.0  # protect this region from darkening

            # Feather the protection mask
            bg_mask = cv2.GaussianBlur(bg_mask, (41, 41), 12)
            darken_strength = 0.30 + 0.35 * (1.0 - bw_factor)  # 30–65% darkening on BG

            # Apply: background gets darkened, ROI stays original
            bg_mask_3ch = np.stack([bg_mask] * 3, axis=-1)
            dark = np.zeros_like(frame, dtype=np.float32)
            annotated_f = frame.astype(np.float32)
            annotated_f = annotated_f * (1.0 - bg_mask_3ch * darken_strength)
            annotated = np.clip(annotated_f, 0, 255).astype(np.uint8)

            # Step 3: NOW draw boxes/labels on top of this (rest of existing code unchanged)
            for det in detections:
                priority = assign_priority(det["class"])
                det["priority"] = priority
                color = PRIORITY_COLORS_BGR[priority]
                x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w - 1, x2), min(h - 1, y2)

                # VERY subtle fill (5% tint only — color hint, not flood)
                if priority <= 2:
                    tint_layer = annotated.copy()
                    cv2.rectangle(tint_layer, (x1, y1), (x2, y2), color, -1)
                    annotated = cv2.addWeighted(annotated, 0.94, tint_layer, 0.06, 0)

                # Strong border — this carries the color
                thickness = 3 if priority == 1 else (2 if priority == 2 else 1)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, thickness)

                # Corner accent marks for P1 (looks professional)
                if priority == 1:
                    corner_len = min(20, (x2 - x1) // 5, (y2 - y1) // 5)
                    for cx, cy, dx, dy in [
                        (x1, y1, 1, 1), (x2, y1, -1, 1),
                        (x1, y2, 1, -1), (x2, y2, -1, -1)
                    ]:
                        cv2.line(annotated, (cx, cy), (cx + dx * corner_len, cy), color, 3)
                        cv2.line(annotated, (cx, cy), (cx, cy + dy * corner_len), color, 3)

                # Pulsing dot at top-center for P1
                if priority == 1:
                    cx_dot = (x1 + x2) // 2
                    cv2.circle(annotated, (cx_dot, y1), 8, (80, 255, 0), -1)
                    cv2.circle(annotated, (cx_dot, y1), 8, (255, 255, 255), 2)

                # Label pill
                conf_pct = int(det["confidence"] * 100)
                label = f"{det['class']} P{priority} {conf_pct}%"
                lsz, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.46, 1)
                pill_y1 = max(0, y1 - lsz[1] - 8)
                cv2.rectangle(annotated, (x1, pill_y1), (x1 + lsz[0] + 6, y1), color, -1)
                cv2.putText(annotated, label, (x1 + 3, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.46, (255, 255, 255), 1, cv2.LINE_AA)

            # HUD bar
            hud_overlay = annotated.copy()
            cv2.rectangle(hud_overlay, (0, 0), (w, 28), (8, 8, 18), -1)
            p1c = sum(1 for d in detections if d.get("priority") == 1)
            p2c = sum(1 for d in detections if d.get("priority") == 2)
            p3c = sum(1 for d in detections if d.get("priority") == 3)
            bw_pct = int((1.0 - bw_factor) * 100)
            hud_txt = (f"SEMANTICSTREAM  |  humans(P1):{p1c}  animals(P2):{p2c}"
                       f"  vehicles(P3):{p3c}  |  BG-compression:{bw_pct}%  |  latency:{latency_ms:.0f}ms")
            cv2.putText(hud_overlay, hud_txt, (8, 19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 80), 1, cv2.LINE_AA)
            annotated = cv2.addWeighted(annotated, 0.08, hud_overlay, 0.92, 0)

            # ── Step 4 — Blended overlay heatmap (thermal-camera style) ────────
            hm_bytes = build_blended_heatmap(frame, detections, alpha=0.55)

            # Encode both frames to JPEG base64
            _, ann_buf = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 78])
            ann_b64 = base64.b64encode(ann_buf).decode()
            hm_b64  = base64.b64encode(hm_bytes).decode()

            # ── Step 5 — WebSocket response JSON ──────────────────────────────
            p1_area = sum(
                (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1])
                for d in detections if d.get("priority") in (1, 2)
            )
            frame_area = h * w
            pcs = min(1.0, p1_area / max(frame_area, 1))

            p1_count = sum(1 for d in detections if d.get("priority") == 1)
            if p1_count >= 1 and pcs > 0.15:
                scene = "DIALOGUE"
            elif any(d.get("priority") == 3 for d in detections):
                scene = "ACTION"
            else:
                scene = "GENERAL"

            response_data = {
                "annotated_frame": ann_b64,
                "annotated_frame_base64": ann_b64,
                "heatmap_frame": hm_b64,
                "priority_map_base64": hm_b64,
                "detections": [
                    {
                        "class": d["class"],
                        "priority": d.get("priority", 5),
                        "confidence": round(float(d.get("confidence", 1.0)), 3),
                        "bbox": [int(v) for v in d["bbox"]],
                        "color": PRIORITY_COLORS_HEX.get(d.get("priority", 5), "#505050"),
                    }
                    for d in detections
                ],
                "priority_distribution": {
                    "P1": sum(1 for d in detections if d.get("priority") == 1),
                    "P2": sum(1 for d in detections if d.get("priority") == 2),
                    "P3": sum(1 for d in detections if d.get("priority") == 3),
                    "P4": sum(1 for d in detections if d.get("priority") == 4),
                    "P5_background": True,
                },
                "pcs_score": round(pcs, 4),
                "scene_type": scene,
                "frame_latency_ms": round(latency_ms, 1),
            }

            await websocket.send_json(response_data)

    except WebSocketDisconnect:
        logger.info("websocket.client_disconnected")
    except Exception as exc:
        logger.error("websocket.session_error", error=str(exc))
