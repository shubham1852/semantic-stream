"""
services/render_service.py
==========================
Annotated video renderer for SemanticStream.

Produces a processed MP4 where every analysed frame is drawn with:
  - Coloured bounding boxes per detection (P1 face/person = green, etc.)
  - Class label + confidence + QP tier badge
  - Semi-transparent priority heatmap blended onto the frame
  - HUD overlay: scene type, dominant tier, SPQI, frame number

Unannotated frames (between sampled frames) are copied from the source
video unmodified so the output has the same duration and FPS as the input.

Output path
-----------
  settings.PROCESSED_DIR / f"{video_id}_annotated.mp4"
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.services.detection_service import FrameAnalysisResult

log = get_logger(__name__)

# ── Tier colour palette (BGR) ─────────────────────────────────────────────────
TIER_COLORS: Dict[str, Tuple[int, int, int]] = {
    "P1": (0,   255,  135),   # green  - face/person
    "P2": (255, 230,   0 ),   # cyan-yellow - text
    "P3": (0,   190,  245),   # amber  - motion
    "P4": (200,  90,  255),   # indigo - objects
    "P5": (60,   60,  200),   # muted red - background
}

HEATMAP_ALPHA = 0.30
FONT          = cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE    = 0.48
FONT_THICK    = 1
BOX_THICK     = 2


def render_annotated_video(
    source_path: Path,
    video_id: str,
    frame_results: List[FrameAnalysisResult],
) -> Optional[Path]:
    """Render an annotated MP4 from a list of frame analysis results.

    Produces an H.264-encoded MP4 that browsers can play natively.
    Strategy:
      1. Try OpenCV ``avc1`` (H.264) codec directly — fastest and most compatible.
      2. If ``avc1`` is unavailable, write a temp ``mp4v`` file then re-encode
         to H.264 using FFmpeg.
    """
    output_path = settings.PROCESSED_DIR / f"{video_id}_annotated.mp4"

    if output_path.exists():
        log.info("render.already_exists", video_id=video_id)
        return output_path

    log.info("render.start", video_id=video_id, frames=len(frame_results))
    t0 = time.perf_counter()

    results_by_frame: Dict[int, FrameAnalysisResult] = {
        r.frame_number: r for r in frame_results
    }

    cap = cv2.VideoCapture(str(source_path))
    if not cap.isOpened():
        log.error("render.open_failed", path=str(source_path))
        return None

    fps    = cap.get(cv2.CAP_PROP_FPS) or 30.0
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Use avc1 (H.264) directly — browser-compatible, supported via OpenCV's bundled FFmpeg.
    # Falls back to a temp mp4v file + FFmpeg re-encode if avc1 is unavailable.
    fourcc_avc1 = cv2.VideoWriter_fourcc(*"avc1")
    writer = cv2.VideoWriter(str(output_path), fourcc_avc1, fps, (width, height))
    temp_path = output_path  # same path — no re-encode needed when avc1 succeeds

    if not writer.isOpened():
        # avc1 not available — fall back to mp4v temp file + FFmpeg re-encode
        log.warning("render.avc1_unavailable", video_id=video_id,
                    advice="avc1 not available; using mp4v+FFmpeg fallback")
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
            result = results_by_frame.get(frame_idx)
            if result is not None:
                frame = _annotate_frame(frame, result)
            writer.write(frame)
            frame_idx += 1
    except Exception as exc:
        log.error("render.frame_error", frame=frame_idx, error=str(exc))
    finally:
        cap.release()
        writer.release()

    # Re-encode to H.264 via FFmpeg so browsers can play the file
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
                import shutil
                shutil.copyfile(final_path, subfolder_file)
            except Exception:
                pass

    elapsed = time.perf_counter() - t0
    size_mb = final_path.stat().st_size / 1024 / 1024 if final_path and final_path.exists() else 0
    log.info("render.done", video_id=video_id, elapsed_s=round(elapsed, 2), size_mb=round(size_mb, 2))
    return final_path if final_path and final_path.exists() else None


MACROBLOCK_SIZE = 16
JPEG_QUALITY = 15
BACKGROUND_BLUR_SIGMA = 2.0


def _apply_semantic_roi_compression(frame: np.ndarray, result: FrameAnalysisResult) -> np.ndarray:
    """Apply spatial non-uniform compression:
    - High-priority (P1/P2/P4) ROIs are kept sharp from the original frame (low QP).
    - Low-priority (P5) background is degraded (simulating high-QP macroblock compression).
    """
    h, w = frame.shape[:2]

    # 1. Create the heavily compressed/quantized background layer (simulating P5 QP=42)
    # Apply Gaussian blur on background before JPEG quantization
    bg_blurred = cv2.GaussianBlur(frame, (0, 0), BACKGROUND_BLUR_SIGMA)

    # Downsample by 16x16 macroblock grid and scale back with nearest-neighbor
    bw, bh = max(1, w // MACROBLOCK_SIZE), max(1, h // MACROBLOCK_SIZE)
    bg_pixel = cv2.resize(bg_blurred, (bw, bh), interpolation=cv2.INTER_AREA)
    bg_pixel = cv2.resize(bg_pixel, (w, h), interpolation=cv2.INTER_NEAREST)

    # Apply JPEG quantization with Q=15 to simulate DCT block compression artifacts
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]
    _, encimg = cv2.imencode(".jpg", bg_pixel, encode_param)
    bg_compressed = cv2.imdecode(encimg, cv2.IMREAD_COLOR)
    if bg_compressed is None:
        bg_compressed = bg_pixel

    # If no detections and no priority map, return compressed background
    if not result.detections and result.priority_map is None:
        return bg_compressed

    # 2. Build the ROI mask for salient objects (P1 faces/persons, P2 text, P4 objects)
    mask = np.zeros((h, w), dtype=np.float32)

    # Use detection bounding boxes
    for det in result.detections:
        x1, y1, x2, y2 = det.bbox
        # Add a 10px margin around detected object
        px1 = max(0, int(x1 * w) - 10)
        py1 = max(0, int(y1 * h) - 10)
        px2 = min(w, int(x2 * w) + 10)
        py2 = min(h, int(y2 * h) + 10)
        mask[py1:py2, px1:px2] = 1.0

    # Also incorporate priority_map if available (regions above 0.35 threshold)
    if result.priority_map is not None:
        pmap = cv2.resize(result.priority_map, (w, h), interpolation=cv2.INTER_LINEAR)
        mask = np.maximum(mask, np.where(pmap > 0.35, 1.0, 0.0).astype(np.float32))

    # Feather the boundary with Gaussian blur on the mask (31x31 kernel for smooth transition)
    feathered_mask = cv2.GaussianBlur(mask.astype(np.float32), (31, 31), 0)
    mask_3ch = np.repeat(feathered_mask[:, :, np.newaxis], 3, axis=2)

    # Blend: sharp original inside ROI (P1-P4), quantized background outside (P5)
    blended = frame.astype(np.float32) * mask_3ch + bg_compressed.astype(np.float32) * (1.0 - mask_3ch)
    return np.clip(blended, 0, 255).astype(np.uint8)


def _annotate_frame(frame: np.ndarray, result: FrameAnalysisResult) -> np.ndarray:
    frame = frame.copy()
    # 1. Apply semantic ROI spatial degradation:
    # Foreground objects stay sharp at original quality;
    # Background is compressed with visible macroblock quantization.
    frame = _apply_semantic_roi_compression(frame, result)

    # 2. Draw detections (crisp bounding box + tier/QP badge)
    for det in result.detections:
        _draw_detection(frame, det, frame.shape[:2])

    # 3. Draw HUD
    _draw_hud(frame, result)
    return frame


def _draw_detection(frame: np.ndarray, det, frame_shape: Tuple[int, int]) -> None:
    h, w = frame_shape
    x1, y1, x2, y2 = det.bbox
    px1, py1 = max(0, int(x1 * w)), max(0, int(y1 * h))
    px2, py2 = min(w - 1, int(x2 * w)), min(h - 1, int(y2 * h))

    tier  = "P1" if det.is_person else "P4"
    color = TIER_COLORS.get(tier, TIER_COLORS["P4"])
    qp    = settings.QP_P1 if tier == "P1" else settings.QP_P4
    label = f"{det.class_name} {det.confidence:.2f} [{tier} QP{qp} · High-Res]"

    cv2.rectangle(frame, (px1, py1), (px2, py2), color, BOX_THICK)

    (tw, th), baseline = cv2.getTextSize(label, FONT, FONT_SCALE, FONT_THICK)
    label_y = max(py1 - 4, th + 4)
    cv2.rectangle(frame, (px1, label_y - th - baseline - 2), (px1 + tw + 6, label_y + 2), color, cv2.FILLED)
    cv2.putText(frame, label, (px1 + 3, label_y - baseline), FONT, FONT_SCALE, (10, 10, 10), FONT_THICK, cv2.LINE_AA)


def _draw_hud(frame: np.ndarray, result: FrameAnalysisResult) -> None:
    scene_raw = (result.scene_type or "GENERAL").upper()
    scene  = "GENERAL" if scene_raw in ("AMBIENT", "NONE", "") else scene_raw
    spqi   = f"SPQI: {result.spqi_score:.3f}" if result.spqi_score is not None else "SPQI: --"
    n_dets = len(result.detections)

    dominant = "P5"
    if result.priority_stats:
        for key, lbl in zip(
            ["p1_frac", "p2_frac", "p3_frac", "p4_frac", "p5_frac"],
            ["P1", "P2", "P3", "P4", "P5"],
        ):
            if result.priority_stats.get(key, 0.0) > 0.01:
                dominant = lbl
                break

    tier_color = TIER_COLORS.get(dominant, TIER_COLORS["P5"])
    lines = [
        ("SEMANTICSTREAM ROI",             (0, 255, 135)),
        (f"Frame {result.frame_number:03d} | {scene}", (200, 200, 200)),
        (f"ROI: {n_dets} object(s) [P1-P4 QP18]", (100, 220, 255)),
        ("Background: [P5 QP42 Quantized]", (140, 140, 240)),
        (spqi,                             tier_color),
    ]

    padding, line_h, box_w = 8, 18, 220
    box_h = len(lines) * line_h + padding * 2
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (box_w, box_h), (8, 12, 24), cv2.FILLED)
    cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    for i, (text, color) in enumerate(lines):
        cv2.putText(frame, text, (padding, padding + (i + 1) * line_h - 2), FONT, 0.40, color, 1, cv2.LINE_AA)


def _ffmpeg_reencode(src: Path, dst: Path, video_id: str) -> None:
    """Re-encode src (mp4v) to dst as H.264 using FFmpeg.

    This ensures the annotated video is browser-compatible regardless of
    the OpenCV codec used during frame-by-frame writing.
    Falls back silently if FFmpeg is not installed.
    """
    import subprocess
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-movflags", "+faststart",   # enables streaming from start
            "-an",                         # no audio (annotated frames only)
            str(dst),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode == 0:
            log.info("render.ffmpeg_reencode_done", video_id=video_id, dst=str(dst))
        else:
            error = (result.stderr or "")[-400:]
            log.warning("render.ffmpeg_reencode_failed", video_id=video_id, stderr=error)
            # If FFmpeg failed but produced a partial file, clean it up
            if dst.exists() and dst.stat().st_size < 1024:
                dst.unlink(missing_ok=True)
            # Fall back: just copy the raw mp4v file so video is at least accessible
            import shutil
            shutil.copy2(src, dst)
    except FileNotFoundError:
        # FFmpeg not installed — copy raw mp4v as fallback
        log.warning("render.ffmpeg_not_found", video_id=video_id,
                    advice="Install FFmpeg for browser-compatible H.264 output")
        import shutil
        shutil.copy2(src, dst)
    except subprocess.TimeoutExpired:
        log.error("render.ffmpeg_reencode_timeout", video_id=video_id)
        import shutil
        if not dst.exists():
            shutil.copy2(src, dst)


def get_annotated_video_path(video_id: str) -> Optional[Path]:
    """Return the path to a pre-rendered annotated video, or None."""
    path = settings.PROCESSED_DIR / f"{video_id}_annotated.mp4"
    return path if path.exists() else None
