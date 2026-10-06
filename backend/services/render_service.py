# FILE: backend/services/render_service.py
"""
services/render_service.py
==========================
Annotated video renderer for SemanticStream — Phase 11 Final Demo Polish.

Produces a processed MP4 video demonstrating clear semantic differentiation:
  1. Background: Aggressively compressed (blocky pixelation downsampling to 6-14%,
     Gaussian blur, near-complete HSV desaturation to 5-12% saturation = near greyscale,
     and JPEG Q=2-6 for maximally visible blocking artefacts).
  2. Semantic ROI: Float32 per-pixel blend mask preserving pristine quality on
     P1 humans (100% + 14% padding) and P2 animals (88%), with partial preservation on P3/P4.
  3. Priority Overlays: Solid per-tier colored borders, P1 corner accent marks & dot,
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
    bandwidth_factor: float = 0.7
) -> np.ndarray:
    import cv2
    import numpy as np

    h, w = frame.shape[:2]

    # ── STEP 1: CREATE DRAMATICALLY COMPRESSED BACKGROUND ──────────────
    # Scale factor: lower bandwidth = more aggressive downscale
    scale = max(0.06, 0.14 - 0.08 * (1.0 - bandwidth_factor))
    small_w = max(1, int(w * scale))
    small_h = max(1, int(h * scale))

    # Pixelate (blocky macroblock look)
    small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
    bg_pixelated = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

    # Gaussian blur on top of pixelation (DCT ringing simulation)
    blur_k = 9 + int(16 * (1.0 - bandwidth_factor))
    blur_k = blur_k if blur_k % 2 == 1 else blur_k + 1
    bg_blurred = cv2.GaussianBlur(bg_pixelated, (blur_k, blur_k), 0)

    # Desaturate: near-complete desaturation (5-12% saturation = almost greyscale background)
    bg_hsv = cv2.cvtColor(bg_blurred, cv2.COLOR_BGR2HSV).astype(np.float32)
    saturation_keep = max(0.05, 0.12 * bandwidth_factor)  # 5-12% saturation = near grey
    bg_hsv[:, :, 1] *= saturation_keep
    bg_desaturated = cv2.cvtColor(bg_hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # JPEG quantization (very low quality = visible blocking artefacts)
    jpeg_q = max(2, int(6 * bandwidth_factor))
    _, enc = cv2.imencode('.jpg', bg_desaturated,
                          [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_q])
    bg_final = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    if bg_final is None:
        bg_final = bg_desaturated

    # ── STEP 2: BUILD PRECISE ROI MASK ─────────────────────────────────
    roi_mask = np.zeros((h, w), dtype=np.float32)

    for det in detections:
        cls = det.get('class', '')
        priority = det.get('priority') or assign_priority(cls)
        x1, y1, x2, y2 = [int(v) for v in det['bbox']]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        # P1: full quality + generous padding
        if priority == 1:
            px = int((x2 - x1) * 0.14)
            py = int((y2 - y1) * 0.14)
            ex1, ey1 = max(0, x1-px), max(0, y1-py)
            ex2, ey2 = min(w, x2+px), min(h, y2+py)
            roi_mask[ey1:ey2, ex1:ex2] = np.maximum(
                roi_mask[ey1:ey2, ex1:ex2], 1.0)
        elif priority == 2:
            roi_mask[y1:y2, x1:x2] = np.maximum(
                roi_mask[y1:y2, x1:x2], 0.88)
        elif priority == 3:
            roi_mask[y1:y2, x1:x2] = np.maximum(
                roi_mask[y1:y2, x1:x2], 0.50)
        elif priority == 4:
            roi_mask[y1:y2, x1:x2] = np.maximum(
                roi_mask[y1:y2, x1:x2], 0.20)

    # ── STEP 3: FEATHER MASK EDGES ─────────────────────────────────────
    # Large kernel feather for seamless blend — no hard edges
    roi_feathered = cv2.GaussianBlur(roi_mask, (81, 81), 28)
    roi_3ch = np.stack([roi_feathered] * 3, axis=-1)

    # ── STEP 4: COMPOSITE ──────────────────────────────────────────────
    orig_f = frame.astype(np.float32)
    comp_f = bg_final.astype(np.float32)
    result_f = orig_f * roi_3ch + comp_f * (1.0 - roi_3ch)
    result = np.clip(result_f, 0, 255).astype(np.uint8)

    # ── STEP 4b: THERMAL-CAMERA BLENDED OVERLAY (Phase 12) ─────────────
    # Intensity map: 30 for background (P5/blue in JET), 100 for P4, 140 for P3,
    # 190 for P2 (warm/cyan), 255 for P1 (red).
    intensity = np.full((h, w), 30, dtype=np.uint8)
    for tier, value in [('P4', 100), ('P3', 140), ('P2', 190), ('P1', 255)]:
        for det in detections:
            p_tier = det.get('priority_tier') if isinstance(det, dict) else getattr(det, 'priority_tier', '')
            if not p_tier:
                p_val = det.get('priority') if isinstance(det, dict) else getattr(det, 'priority', 5)
                p_tier = f"P{p_val}"
            if p_tier == tier:
                bbox = det.get('bbox') if isinstance(det, dict) else (det.x1, det.y1, det.x2, det.y2)
                x1 = max(0, min(int(bbox[0]), w - 1))
                y1 = max(0, min(int(bbox[1]), h - 1))
                x2 = max(0, min(int(bbox[2]), w - 1))
                y2 = max(0, min(int(bbox[3]), h - 1))
                if x2 > x1 and y2 > y1:
                    intensity[y1:y2, x1:x2] = value

    colormap = cv2.applyColorMap(intensity, cv2.COLORMAP_JET)
    alpha_thermal = 0.40
    result = cv2.addWeighted(
        result.astype(np.float32), 1.0 - alpha_thermal,
        colormap.astype(np.float32), alpha_thermal,
        0
    ).astype(np.uint8)

    # ── STEP 5: DRAW BORDERS + LABELS ON COMPOSITED RESULT ─────────────
    overlay = result.copy()
    for det in sorted(detections, key=lambda d: d.get('priority', 5)):
        priority = det.get('priority') or assign_priority(det.get('class', ''))
        if priority >= 5:
            continue
        color = PRIORITY_COLORS_BGR.get(priority, (80, 80, 80))
        x1, y1, x2, y2 = [int(v) for v in det['bbox']]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w-1, x2), min(h-1, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        thick = 3 if priority == 1 else (2 if priority == 2 else 1)
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, thick)

        # Corner accent marks for P1
        if priority == 1:
            corner_len = min(18, (x2-x1)//5, (y2-y1)//5)
            for cx, cy, dx, dy in [
                (x1, y1, 1, 1), (x2, y1, -1, 1),
                (x1, y2, 1, -1), (x2, y2, -1, -1)
            ]:
                cv2.line(overlay, (cx, cy), (cx + dx*corner_len, cy), color, 3)
                cv2.line(overlay, (cx, cy), (cx, cy + dy*corner_len), color, 3)
            cx_dot = (x1 + x2) // 2
            cv2.circle(overlay, (cx_dot, y1), 8, (80, 255, 0), -1)
            cv2.circle(overlay, (cx_dot, y1), 8, (255, 255, 255), 2)

        label = f"{det.get('class', 'obj')} P{priority}"
        lsz, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
        pill_y1 = max(0, y1 - lsz[1] - 7)
        cv2.rectangle(overlay, (x1, pill_y1), (x1+lsz[0]+5, y1), color, -1)
        cv2.putText(overlay, label, (x1+2, y1-3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, (255, 255, 255), 1, cv2.LINE_AA)

    result = cv2.addWeighted(result, 0.72, overlay, 0.28, 0)

    # ── STEP 6: HUD ────────────────────────────────────────────────────
    hud = result.copy()
    cv2.rectangle(hud, (0, 0), (w, 30), (6, 6, 16), -1)
    p1c = sum(1 for d in detections if d.get('priority') == 1)
    p2c = sum(1 for d in detections if d.get('priority') == 2)
    bw_pct = int((1.0 - bandwidth_factor) * 100)
    hud_txt = (f"SEMANTICSTREAM  |  humans(P1):{p1c}  animals(P2):{p2c}"
               f"  |  BG compressed {bw_pct}%  |  semantic ROI preserved")
    cv2.putText(hud, hud_txt, (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 255, 80), 1, cv2.LINE_AA)
    result = cv2.addWeighted(result, 0.10, hud, 0.90, 0)

    return result


def _normalize_detection_dict(det: Any) -> Dict[str, Any]:
    """Convert any detection representation into a uniform dictionary."""
    if isinstance(det, dict):
        cls_name = str(det.get("class") or det.get("class_name") or "object")
        p = det.get("priority") or assign_priority(cls_name)
        bbox = det.get("bbox") or [0, 0, 0, 0]
        p_tier = det.get("priority_tier") or f"P{p}"
        return {
            "class": cls_name,
            "priority": int(p),
            "priority_tier": p_tier,
            "confidence": float(det.get("confidence", 1.0)),
            "bbox": [int(v) for v in bbox],
        }

    cls_name = str(getattr(det, "class_name", "object"))
    p = getattr(det, "priority", None) or assign_priority(cls_name)
    bbox = getattr(det, "bbox", (det.x1, det.y1, det.x2, det.y2))
    p_tier = getattr(det, "priority_tier", f"P{p}")
    return {
        "class": cls_name,
        "priority": int(p),
        "priority_tier": p_tier,
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
