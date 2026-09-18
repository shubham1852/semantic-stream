# FILE: backend/services/render_service.py
"""
services/render_service.py
==========================
Annotated video renderer for SemanticStream — Phase 10 Visible Compression.

Produces a processed MP4 video demonstrating clear semantic differentiation:
  1. Background: Aggressively compressed (macroblock downsampling, Gaussian blur,
     HSV desaturation, and low-quality JPEG quantization).
  2. Semantic ROI: Float32 per-pixel blend mask preserving pristine quality on
     P1 (100% + 12% padding) and P2 (90%), with partial preservation on P3/P4.
  3. Priority Overlays: Solid per-tier colored borders, P1 pulsing dots,
     label pills, and real-time HUD bar.
  4. Compression severity is dynamically controlled by `bandwidth_factor`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.services.detection_service import (
    PRIORITY_COLORS_BGR,
    PRIORITY_MAP,
    FrameAnalysisResult,
    assign_priority,
)

log = get_logger(__name__)


def process_frame_with_visible_compression(
    frame: np.ndarray,
    detections: list,
    bandwidth_factor: float = 1.0,
) -> np.ndarray:
    """Apply visible compression differentiation to a single frame.

    Aggressively degrades background while preserving full quality for
    semantic ROIs according to priority tiers (P1-P4).
    """
    h, w = frame.shape[:2]

    # ── BACKGROUND: aggressively compress ──────────────────────────────
    scale = max(0.12, 0.22 - 0.10 * (1.0 - bandwidth_factor))
    small = cv2.resize(
        frame,
        (max(1, int(w * scale)), max(1, int(h * scale))),
        interpolation=cv2.INTER_LINEAR,
    )
    bg = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    blur_k = 13 + int(22 * (1.0 - bandwidth_factor))
    blur_k = blur_k if blur_k % 2 == 1 else blur_k + 1
    bg = cv2.GaussianBlur(bg, (blur_k, blur_k), 0)

    hsv = cv2.cvtColor(bg, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= 0.35
    bg = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    q = max(4, int(10 * bandwidth_factor))
    _, enc = cv2.imencode(".jpg", bg, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    bg = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    if bg is None:
        bg = frame.copy()

    # ── ROI MASK: float32 per-pixel blend weight ────────────────────────
    roi_mask = np.zeros((h, w), dtype=np.float32)
    for det in detections:
        priority = det.get("priority") or assign_priority(det.get("class", ""))
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        if priority == 1:
            px = int((x2 - x1) * 0.12)
            py = int((y2 - y1) * 0.12)
            x1, y1 = max(0, x1 - px), max(0, y1 - py)
            x2, y2 = min(w, x2 + px), min(h, y2 + py)
            roi_mask[y1:y2, x1:x2] = np.maximum(roi_mask[y1:y2, x1:x2], 1.0)
        elif priority == 2:
            roi_mask[y1:y2, x1:x2] = np.maximum(roi_mask[y1:y2, x1:x2], 0.90)
        elif priority == 3:
            roi_mask[y1:y2, x1:x2] = np.maximum(roi_mask[y1:y2, x1:x2], 0.55)
        elif priority == 4:
            roi_mask[y1:y2, x1:x2] = np.maximum(roi_mask[y1:y2, x1:x2], 0.25)

    # Feather mask edges
    roi_mask = cv2.GaussianBlur(roi_mask, (71, 71), 25)
    roi_3 = np.stack([roi_mask] * 3, axis=-1)

    # ── COMPOSITE ──────────────────────────────────────────────────────
    result = (
        frame.astype(np.float32) * roi_3
        + bg.astype(np.float32) * (1.0 - roi_3)
    )
    result = np.clip(result, 0, 255).astype(np.uint8)

    # ── DRAW PRIORITY BORDERS + LABELS ────────────────────────────────
    overlay = result.copy()
    for det in sorted(detections, key=lambda d: d.get("priority", 5)):
        priority = det.get("priority") or assign_priority(det.get("class", ""))
        if priority >= 5:
            continue
        color = PRIORITY_COLORS_BGR.get(priority, (80, 80, 80))
        x1, y1, x2, y2 = [int(v) for v in det["bbox"]]
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w - 1, x2), min(h - 1, y2)
        thick = 3 if priority == 1 else (2 if priority == 2 else 1)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thick)
        if priority == 1:
            cx = (x1 + x2) // 2
            cv2.circle(overlay, (cx, y1), 8, (80, 255, 0), -1)
            cv2.circle(overlay, (cx, y1), 8, (255, 255, 255), 1)
        label = f"{det.get('class', 'obj')} P{priority}"
        lsz = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)[0]
        cv2.rectangle(overlay, (x1, y1 - lsz[1] - 7), (x1 + lsz[0] + 5, y1), color, -1)
        cv2.putText(
            overlay,
            label,
            (x1 + 2, y1 - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.44,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    result = cv2.addWeighted(result, 0.7, overlay, 0.3, 0)

    # ── HUD ───────────────────────────────────────────────────────────
    hud = result.copy()
    cv2.rectangle(hud, (0, 0), (w, 28), (8, 8, 18), -1)
    p1c = sum(1 for d in detections if d.get("priority") == 1)
    bw_pct = int(bandwidth_factor * 100)
    cv2.putText(
        hud,
        f"SEMANTICSTREAM | humans(P1):{p1c} | BG compressed {100 - bw_pct}% | semantic ROI preserved",
        (8, 19),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (0, 255, 80),
        1,
        cv2.LINE_AA,
    )
    result = cv2.addWeighted(result, 0.15, hud, 0.85, 0)

    return result


def _normalize_detection_dict(det: Any) -> Dict[str, Any]:
    """Convert any detection representation into a uniform dictionary."""
    if isinstance(det, dict):
        cls_name = str(det.get("class") or det.get("class_name") or "object")
        p = det.get("priority") or assign_priority(cls_name)
        bbox = det.get("bbox") or [0, 0, 0, 0]
        return {
            "class": cls_name,
            "priority": int(p),
            "confidence": float(det.get("confidence", 1.0)),
            "bbox": [int(v) for v in bbox],
        }

    cls_name = str(getattr(det, "class_name", "object"))
    p = getattr(det, "priority", None) or assign_priority(cls_name)
    bbox = getattr(det, "bbox", (det.x1, det.y1, det.x2, det.y2))
    return {
        "class": cls_name,
        "priority": int(p),
        "confidence": float(getattr(det, "confidence", 1.0)),
        "bbox": [int(v) for v in bbox],
    }


def render_annotated_video(
    source_path: Path,
    video_id: str,
    frame_results: List[FrameAnalysisResult],
    bandwidth_factor: float = 0.7,
) -> Optional[Path]:
    """Render an annotated MP4 video with visible compression differentiation.

    Applies `process_frame_with_visible_compression` to all analysed frames
    and encodes the final video for direct browser playback.
    """
    output_path = settings.PROCESSED_DIR / f"{video_id}_annotated.mp4"

    if output_path.exists():
        log.info("render.already_exists", video_id=video_id)
        return output_path

    log.info(
        "render.start",
        video_id=video_id,
        frames=len(frame_results),
        bandwidth_factor=bandwidth_factor,
    )
    t0 = time.perf_counter()

    results_by_frame: Dict[int, List[Dict[str, Any]]] = {}
    last_detections: List[Dict[str, Any]] = []

    for r in frame_results:
        dets = [_normalize_detection_dict(d) for d in r.detections]
        results_by_frame[r.frame_number] = dets

    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        log.error("render.open_failed", path=str(source_path))
        return None

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc_avc1 = cv2.VideoWriter_fourcc(*"avc1")
    writer = cv2.VideoWriter(str(output_path), fourcc_avc1, fps, (width, height))
    temp_path = output_path

    if not writer.isOpened():
        log.warning(
            "render.avc1_unavailable",
            video_id=video_id,
            advice="Falling back to mp4v + FFmpeg re-encode",
        )
        temp_path = settings.PROCESSED_DIR / f"{video_id}_annotated_tmp.mp4"
        fourcc_mp4v = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(temp_path), fourcc_mp4v, fps, (width, height))
        if not writer.isOpened():
            log.error("render.writer_failed", path=str(temp_path))
            cap.release()
            return None

    frame_idx = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx in results_by_frame:
                last_detections = results_by_frame[frame_idx]

            # Render with visible compression differentiation
            processed_frame = process_frame_with_visible_compression(
                frame,
                last_detections,
                bandwidth_factor=bandwidth_factor,
            )
            writer.write(processed_frame)
            frame_idx += 1
    except Exception as exc:
        log.error("render.frame_error", frame=frame_idx, error=str(exc))
    finally:
        cap.release()
        writer.release()

    # Re-encode mp4v -> H.264 if needed
    if temp_path != output_path and temp_path.exists():
        _ffmpeg_reencode(temp_path, output_path, video_id)
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass

    final_path = output_path if output_path.exists() else (temp_path if temp_path.exists() else None)

    if final_path and final_path.exists():
        subfolder = settings.PROCESSED_DIR / video_id
        subfolder.mkdir(parents=True, exist_ok=True)
        subfolder_file = subfolder / f"{video_id}_annotated.mp4"
        if not subfolder_file.exists():
            try:
                shutil.copyfile(final_path, subfolder_file)
            except Exception:
                pass

    elapsed = time.perf_counter() - t0
    size_mb = final_path.stat().st_size / (1024 * 1024) if final_path and final_path.exists() else 0
    log.info(
        "render.done",
        video_id=video_id,
        elapsed_s=round(elapsed, 2),
        size_mb=round(size_mb, 2),
    )
    return final_path if final_path and final_path.exists() else None


def get_annotated_video_path(video_id: str) -> Optional[Path]:
    """Return the path to a pre-rendered annotated video, or None."""
    path = settings.PROCESSED_DIR / f"{video_id}_annotated.mp4"
    return path if path.exists() else None


def _ffmpeg_reencode(src: Path, dst: Path, video_id: str) -> None:
    """Re-encode *src* as browser-friendly H.264 in *dst* using FFmpeg."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-movflags", "+faststart",
            "-an",
            str(dst),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0:
            log.info("render.ffmpeg_reencode_done", video_id=video_id, dst=str(dst))
        else:
            error = (result.stderr or "")[-400:]
            log.warning("render.ffmpeg_reencode_failed", video_id=video_id, stderr=error)
            if dst.exists() and dst.stat().st_size < 1024:
                dst.unlink(missing_ok=True)
            shutil.copy2(src, dst)
    except FileNotFoundError:
        log.warning("render.ffmpeg_not_found", video_id=video_id)
        shutil.copy2(src, dst)
    except subprocess.TimeoutExpired:
        log.error("render.ffmpeg_reencode_timeout", video_id=video_id)
        if not dst.exists():
            shutil.copy2(src, dst)
