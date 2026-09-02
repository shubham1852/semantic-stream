"""
utils/frame_utils.py
====================
Frame-level utilities for the SemanticStream AI pipeline.

Responsibilities
----------------
* Extract individual frames from a video file via FFmpeg or OpenCV.
* Resize / pad frames to the inference canvas size.
* Normalise pixel values for model input.
* Compute dense optical flow between two consecutive frames (Farneback).
* Detect candidate text regions using morphological gradient analysis.
* Compute per-frame histogram for scene-cut detection.

All functions are *pure* (no side-effects on external state) and operate on
NumPy arrays so they can be used in both sync and async contexts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Generator, List, Optional, Tuple

import numpy as np

from backend.core.config import settings
from backend.core.exceptions import FFmpegError
from backend.core.logging_config import get_logger

log = get_logger(__name__)

# ── Type aliases ─────────────────────────────────────────────────────────────
Frame = np.ndarray          # uint8 BGR (H, W, 3)
GrayFrame = np.ndarray      # uint8 grayscale (H, W)
FlowField = np.ndarray      # float32 (H, W, 2) — dx, dy per pixel


# ── Frame extraction ──────────────────────────────────────────────────────────

def extract_frames(
    video_path: str | Path,
    sample_rate: int = settings.DEFAULT_FRAME_SAMPLE_RATE,
    max_frames: Optional[int] = None,
) -> Generator[Tuple[int, float, Frame], None, None]:
    """Yield (frame_number, timestamp_ms, frame_bgr) for a video file.

    Uses OpenCV's ``VideoCapture`` for low-latency sequential reads.
    Only every *sample_rate*-th frame is yielded (1 = every frame).

    Parameters
    ----------
    video_path:
        Path to the source video file.
    sample_rate:
        Yield one frame every *N* frames (default from settings).
    max_frames:
        Stop after yielding this many frames.  ``None`` = no limit.

    Yields
    ------
    (frame_number, timestamp_ms, frame_bgr)
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required for frame extraction") from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FFmpegError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_number = 0
    yielded = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_number % sample_rate == 0:
                timestamp_ms = (frame_number / fps) * 1000.0
                yield frame_number, timestamp_ms, frame
                yielded += 1
                if max_frames is not None and yielded >= max_frames:
                    break

            frame_number += 1
    finally:
        cap.release()

    log.debug("frame_extraction_done", total=frame_number, yielded=yielded)


def get_video_metadata(video_path: str | Path) -> dict:
    """Return basic metadata for a video file using OpenCV.

    Returns a dict with keys: ``fps``, ``width``, ``height``,
    ``total_frames``, ``duration_seconds``.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FFmpegError(f"Cannot open video: {video_path}")

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total / fps if fps else 0.0
        return {
            "fps": fps,
            "width": w,
            "height": h,
            "total_frames": total,
            "duration_seconds": duration,
        }
    finally:
        cap.release()


# ── Resize & normalise ────────────────────────────────────────────────────────

def resize_frame(
    frame: Frame,
    width: int = settings.INFERENCE_WIDTH,
    height: int = settings.INFERENCE_HEIGHT,
    keep_aspect: bool = False,
) -> Frame:
    """Resize a frame to the target (width, height).

    Parameters
    ----------
    keep_aspect:
        If True, letterbox the frame with black padding instead of
        squashing it.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    if not keep_aspect:
        return cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)

    orig_h, orig_w = frame.shape[:2]
    ratio = min(width / orig_w, height / orig_h)
    new_w = int(orig_w * ratio)
    new_h = int(orig_h * ratio)
    resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    pad_y = (height - new_h) // 2
    pad_x = (width - new_w) // 2
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    return canvas


def normalise_frame(frame: Frame) -> np.ndarray:
    """Convert uint8 BGR to float32 RGB in [0, 1]."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return rgb.astype(np.float32) / 255.0


def to_nchw_blob(frame_rgb_f32: np.ndarray) -> np.ndarray:
    """Convert (H, W, 3) float32 → (1, 3, H, W) NCHW blob."""
    chw = np.transpose(frame_rgb_f32, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


# ── Optical flow ──────────────────────────────────────────────────────────────

def compute_optical_flow(
    prev_gray: GrayFrame,
    curr_gray: GrayFrame,
    pyr_scale: float = 0.5,
    levels: int = 3,
    winsize: int = 15,
    iterations: int = 3,
    poly_n: int = 5,
    poly_sigma: float = 1.2,
) -> FlowField:
    """Compute dense Farneback optical flow between two grayscale frames.

    Returns a float32 array of shape (H, W, 2) where
    ``flow[y, x] = (dx, dy)`` describes the pixel displacement.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    flow = cv2.calcOpticalFlowFarneback(
        prev_gray,
        curr_gray,
        None,
        pyr_scale,
        levels,
        winsize,
        iterations,
        poly_n,
        poly_sigma,
        0,
    )
    return flow  # (H, W, 2)


def flow_magnitude(flow: FlowField) -> np.ndarray:
    """Return per-pixel optical-flow magnitude map (float32, H × W)."""
    dx = flow[..., 0]
    dy = flow[..., 1]
    return np.sqrt(dx ** 2 + dy ** 2)


def high_motion_mask(
    flow: FlowField,
    threshold: float = settings.FLOW_THRESHOLD,
) -> np.ndarray:
    """Boolean mask of pixels whose flow magnitude exceeds *threshold*."""
    return flow_magnitude(flow) > threshold


def to_grayscale(frame: Frame) -> GrayFrame:
    """Convert BGR frame to single-channel grayscale."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)


# ── Text-region detection ─────────────────────────────────────────────────────

def detect_text_regions(
    frame: Frame,
    min_area_frac: float = 0.001,
    max_area_frac: float = 0.15,
) -> np.ndarray:
    """Return a binary mask where potential text regions are white.

    Strategy
    --------
    1. Convert to grayscale.
    2. Apply morphological gradient (dilation − erosion) to highlight
       sharp intensity transitions characteristic of characters.
    3. Threshold → find contours → keep those in the area range.

    Parameters
    ----------
    min_area_frac / max_area_frac:
        Contour area must be between these fractions of the total frame
        area to be considered a text region.

    Returns
    -------
    Binary mask (uint8 0/255), same H × W as input.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    total_area = gray.shape[0] * gray.shape[1]

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel)
    _, thresh = cv2.threshold(gradient, 50, 255, cv2.THRESH_BINARY)

    # Close small gaps → merge nearby strokes
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    mask = np.zeros_like(gray, dtype=np.uint8)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        frac = area / total_area
        if min_area_frac <= frac <= max_area_frac:
            cv2.drawContours(mask, [cnt], -1, 255, thickness=cv2.FILLED)

    return mask


def text_area_fraction(frame: Frame) -> float:
    """Return the fraction of the frame covered by detected text regions."""
    mask = detect_text_regions(frame)
    total = mask.shape[0] * mask.shape[1]
    return float(np.count_nonzero(mask)) / total if total else 0.0


# ── Histogram utilities ────────────────────────────────────────────────────────

def compute_histogram(
    frame: Frame,
    bins: int = settings.HISTOGRAM_BINS,
) -> np.ndarray:
    """Compute a normalised 3-channel (BGR) histogram for *frame*.

    Returns a 1-D float32 array of length ``3 * bins`` (R, G, B channels
    concatenated), normalised so that each channel sums to 1.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    hists: List[np.ndarray] = []
    for ch in range(3):
        h = cv2.calcHist([frame], [ch], None, [bins], [0, 256])
        h = h.flatten().astype(np.float32)
        total = h.sum()
        hists.append(h / total if total > 0 else h)
    return np.concatenate(hists)


def histogram_distance(hist_a: np.ndarray, hist_b: np.ndarray) -> float:
    """Bhattacharyya distance between two normalised histograms.

    Returns a value in [0, 1]; values > settings.SCENE_CUT_THRESHOLD
    indicate a scene cut.
    """
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    # Split back into per-channel blocks and compare channel-by-channel
    bins = len(hist_a) // 3
    distances: List[float] = []
    for i in range(3):
        a = hist_a[i * bins : (i + 1) * bins].reshape(-1, 1).astype(np.float32)
        b = hist_b[i * bins : (i + 1) * bins].reshape(-1, 1).astype(np.float32)
        distances.append(cv2.compareHist(a, b, cv2.HISTCMP_BHATTACHARYYA))
    return float(np.mean(distances))


# ── Bounding-box helpers ──────────────────────────────────────────────────────

def bbox_mask(
    shape: Tuple[int, int],
    boxes: List[Tuple[int, int, int, int]],
) -> np.ndarray:
    """Create a binary mask from a list of (x1, y1, x2, y2) bounding boxes.

    Parameters
    ----------
    shape:
        (height, width) of the output mask.
    boxes:
        List of pixel-space bounding boxes.

    Returns
    -------
    uint8 array with 255 inside boxes, 0 elsewhere.
    """
    mask = np.zeros(shape, dtype=np.uint8)
    for x1, y1, x2, y2 in boxes:
        mask[y1:y2, x1:x2] = 255
    return mask


def mask_area_fraction(
    mask: np.ndarray,
    total_pixels: Optional[int] = None,
) -> float:
    """Fraction of *total_pixels* covered by non-zero pixels in *mask*."""
    total = total_pixels or (mask.shape[0] * mask.shape[1])
    return float(np.count_nonzero(mask)) / total if total else 0.0
