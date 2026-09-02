"""
utils/qp_utils.py
=================
Priority-map builder and QP-matrix generator for SemanticStream.

The SemanticStream encoding strategy works by assigning each pixel a
*priority score* (0–1) based on its semantic importance, then deriving a
per-macroblock Quantization Parameter (QP) value from that score.

Pipeline
--------
1. Build a **priority score map** (float32, H × W) from:
   - Detection bounding boxes (persons, faces → P1)
   - Text-region masks (P2)
   - Optical-flow high-motion masks (P3)
   - Other object bounding boxes (P4)
   - Everything else (P5 background)

2. Optionally apply **temporal EMA smoothing** so the priority map
   doesn't jitter frame to frame.

3. Convert the priority map to a **QP matrix** (int, H × W) using the
   5-tier lookup defined in ``settings``.

4. Export an FFmpeg-compatible **QP override map** as a flat string
   suitable for the ``-qpfile`` argument.

The QP matrix is at frame resolution (not macroblock resolution) to keep
the maths clean; the compression service resamples it to macroblock
boundaries before passing it to FFmpeg.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.models.yolo_engine import Detection

log = get_logger(__name__)

# ── Type aliases ──────────────────────────────────────────────────────────────
PriorityMap = np.ndarray   # float32 (H, W)   values in [0, 1]
QPMatrix = np.ndarray      # int32   (H, W)   QP per pixel


# ── Priority score constants ───────────────────────────────────────────────────
_P1 = settings.PRIORITY_P1   # 1.0
_P2 = settings.PRIORITY_P2   # 0.8
_P3 = settings.PRIORITY_P3   # 0.6
_P4 = settings.PRIORITY_P4   # 0.4
_P5 = settings.PRIORITY_P5   # 0.1


# ── Priority map builder ──────────────────────────────────────────────────────

def build_priority_map(
    frame_shape: Tuple[int, int],
    detections: List[Detection],
    text_mask: Optional[np.ndarray] = None,
    flow_mask: Optional[np.ndarray] = None,
) -> PriorityMap:
    """Construct a pixel-level priority map from multi-source signals.

    Priority assignment (highest priority wins at each pixel):

    ┌───────┬───────────────────────────────────────────────────────────┐
    │ Tier  │ Source                                                    │
    ├───────┼───────────────────────────────────────────────────────────┤
    │  P1   │ Person/face bounding boxes from YOLO                     │
    │  P2   │ Text-region mask (morphological gradient detector)       │
    │  P3   │ High-motion pixels (optical-flow magnitude > threshold)  │
    │  P4   │ All other YOLO detection bounding boxes                  │
    │  P5   │ Background (default — everything else)                   │
    └───────┴───────────────────────────────────────────────────────────┘

    Pixels that satisfy multiple tiers retain the highest priority.

    Parameters
    ----------
    frame_shape:
        ``(height, width)`` of the source video frame.
    detections:
        List of YOLO detections for the current frame.
    text_mask:
        uint8 binary mask (255 = text) from :func:`frame_utils.detect_text_regions`.
        Pass ``None`` to skip P2 tier.
    flow_mask:
        Boolean/uint8 mask where high-motion pixels are non-zero.
        Pass ``None`` to skip P3 tier.

    Returns
    -------
    float32 priority map of shape ``(height, width)`` with values in
    ``{P5, P4, P3, P2, P1}``.
    """
    h, w = frame_shape

    # Start everything at background (P5)
    pmap = np.full((h, w), _P5, dtype=np.float32)

    # ── P4: other YOLO detections ─────────────────────────────────────────
    for det in detections:
        if not det.is_person:
            x1, y1, x2, y2 = _clamp_bbox(det.bbox, w, h)
            pmap[y1:y2, x1:x2] = np.maximum(pmap[y1:y2, x1:x2], _P4)

    # ── P3: high-motion pixels ─────────────────────────────────────────────
    if flow_mask is not None:
        motion_bool = (flow_mask > 0).astype(bool)
        pmap[motion_bool] = np.maximum(pmap[motion_bool], _P3)

    # ── P2: text regions ───────────────────────────────────────────────────
    if text_mask is not None:
        text_bool = (text_mask > 0).astype(bool)
        pmap[text_bool] = np.maximum(pmap[text_bool], _P2)

    # ── P1: persons / faces ────────────────────────────────────────────────
    for det in detections:
        if det.is_person:
            x1, y1, x2, y2 = _clamp_bbox(det.bbox, w, h)
            pmap[y1:y2, x1:x2] = np.maximum(pmap[y1:y2, x1:x2], _P1)

    return pmap


def _clamp_bbox(
    bbox: Tuple[int, int, int, int],
    w: int,
    h: int,
) -> Tuple[int, int, int, int]:
    """Clamp a bounding box to frame boundaries."""
    x1, y1, x2, y2 = bbox
    return (
        max(0, x1),
        max(0, y1),
        min(w, x2),
        min(h, y2),
    )


# ── Temporal smoothing ────────────────────────────────────────────────────────

def smooth_priority_map(
    current: PriorityMap,
    previous: Optional[PriorityMap],
    alpha: float = settings.TEMPORAL_ALPHA,
) -> PriorityMap:
    """Apply exponential moving average (EMA) smoothing between frames.

    EMA formula:  smoothed = alpha * current + (1 − alpha) * previous

    Parameters
    ----------
    current:
        Priority map for the current frame.
    previous:
        Priority map from the previous processed frame.  If ``None``
        (first frame), the current map is returned unchanged.
    alpha:
        Weight of the current frame (0 < alpha ≤ 1).

    Returns
    -------
    Smoothed float32 priority map.
    """
    if previous is None:
        return current.copy()
    if previous.shape != current.shape:
        log.warning(
            "priority_map_shape_mismatch",
            prev=previous.shape,
            curr=current.shape,
        )
        return current.copy()
    return (alpha * current + (1.0 - alpha) * previous).astype(np.float32)


# ── QP matrix ─────────────────────────────────────────────────────────────────

def priority_to_qp(priority_map: PriorityMap) -> QPMatrix:
    """Convert a priority map to a per-pixel QP matrix using tier thresholds.

    Priority → QP mapping
    ────────────────────────────────────────────
    priority ≥ P1 (1.00)  →  QP_P1  (18)  — max quality
    priority ≥ P2 (0.80)  →  QP_P2  (22)
    priority ≥ P3 (0.60)  →  QP_P3  (26)
    priority ≥ P4 (0.40)  →  QP_P4  (32)
    priority <  P4         →  QP_P5  (40)  — background
    ────────────────────────────────────────────

    Returns
    -------
    int32 QP matrix of shape (H, W).
    """
    qp = np.full(priority_map.shape, settings.QP_P5, dtype=np.int32)
    qp[priority_map >= _P4] = settings.QP_P4
    qp[priority_map >= _P3] = settings.QP_P3
    qp[priority_map >= _P2] = settings.QP_P2
    qp[priority_map >= _P1] = settings.QP_P1
    return qp


def get_macroblock_qp(
    qp_matrix: QPMatrix,
    mb_size: int = 16,
) -> np.ndarray:
    """Downsample QP matrix to macroblock resolution (default 16×16 px).

    Uses the *minimum* (highest quality) QP in each macroblock so that
    important content is never under-served by rounding.

    Returns
    -------
    int32 array of shape (ceil(H/mb_size), ceil(W/mb_size)).
    """
    h, w = qp_matrix.shape
    mb_h = (h + mb_size - 1) // mb_size
    mb_w = (w + mb_size - 1) // mb_size
    out = np.zeros((mb_h, mb_w), dtype=np.int32)

    for r in range(mb_h):
        for c in range(mb_w):
            r0, r1 = r * mb_size, min((r + 1) * mb_size, h)
            c0, c1 = c * mb_size, min((c + 1) * mb_size, w)
            out[r, c] = int(qp_matrix[r0:r1, c0:c1].min())

    return out


# ── Statistics ────────────────────────────────────────────────────────────────

def priority_map_stats(pmap: PriorityMap) -> dict:
    """Compute per-tier pixel coverage statistics for a priority map.

    Returns a dict with keys ``p1_frac``, ``p2_frac``, ``p3_frac``,
    ``p4_frac``, ``p5_frac`` — each the fraction of total pixels at
    that tier.
    """
    total = pmap.size or 1
    return {
        "p1_frac": float(np.sum(pmap >= _P1) / total),
        "p2_frac": float(np.sum((pmap >= _P2) & (pmap < _P1)) / total),
        "p3_frac": float(np.sum((pmap >= _P3) & (pmap < _P2)) / total),
        "p4_frac": float(np.sum((pmap >= _P4) & (pmap < _P3)) / total),
        "p5_frac": float(np.sum(pmap < _P4) / total),
        "mean_priority": float(np.mean(pmap)),
    }


def estimated_bitrate_savings(qp_matrix: QPMatrix, uniform_qp: int = settings.QP_UNIFORM) -> float:
    """Estimate percentage bitrate reduction vs. uniform ABR baseline.

    Uses the empirical rule-of-thumb that each QP step increase reduces
    bitrate by ~10 % (H.264/H.265 standard approximation).

    Returns
    -------
    Estimated bitrate reduction as a fraction (0–1).
    """
    delta_qp = qp_matrix.astype(float) - uniform_qp
    # Each +1 QP ≈ 10 % bitrate reduction; negative delta = more bits
    savings_per_pixel = 1.0 - (0.9 ** delta_qp)
    return float(np.mean(savings_per_pixel))


# ── FFmpeg qpfile helpers ─────────────────────────────────────────────────────

def qp_matrix_to_ffmpeg_qpfile(
    mb_qp: np.ndarray,
    frame_type: str = "P",
) -> str:
    """Serialise a macroblock QP matrix as an FFmpeg ``-qpfile`` entry.

    Format per line: ``<mb_row> <mb_col> <qp> <frame_type>``
    where frame_type is ``I``, ``P``, or ``B``.

    Returns a multiline string ready to append to the qpfile.
    """
    lines: List[str] = []
    for r in range(mb_qp.shape[0]):
        for c in range(mb_qp.shape[1]):
            lines.append(f"{r} {c} {int(mb_qp[r, c])} {frame_type}")
    return "\n".join(lines)
