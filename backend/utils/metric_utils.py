"""
utils/metric_utils.py
=====================
Perceptual and compression quality metric formulae for SemanticStream.

Metrics implemented
-------------------
SPQI  — Semantic Perceptual Quality Index
        Weighted-SSIM using per-tier priority weights derived from the
        priority map.  Higher = better quality.

SSIM  — Structural Similarity Index Measure (windowed, luminance-based)
        Classic Wang et al. 2004 implementation using a 11×11 Gaussian
        window.

PSNR  — Peak Signal-to-Noise Ratio
        Standard dB metric; ∞ for identical frames (clamped to 60 dB).

SEES  — Semantic Efficiency–Experience Score
        Novel metric: quality-per-bit normalised against a uniform-ABR
        baseline.  Positive = SemanticStream outperforms baseline.

All functions accept NumPy arrays (uint8 or float32) and are designed to
be called frame-by-frame in the analysis pipeline.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.utils.qp_utils import PriorityMap

log = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
_SSIM_K1 = 0.01
_SSIM_K2 = 0.03
_SSIM_L = 255           # dynamic range for uint8
_SSIM_C1 = (_SSIM_K1 * _SSIM_L) ** 2
_SSIM_C2 = (_SSIM_K2 * _SSIM_L) ** 2
_PSNR_MAX_DB = 60.0     # cap for identical frames


# ── SSIM ──────────────────────────────────────────────────────────────────────

def compute_ssim(
    img_ref: np.ndarray,
    img_dist: np.ndarray,
    window_size: int = 11,
    sigma: float = 1.5,
) -> float:
    """Compute the mean Structural Similarity Index between two images.

    Parameters
    ----------
    img_ref:
        Reference (uncompressed / higher-quality) frame.  Accepts uint8
        BGR or grayscale arrays; colour frames are converted to luminance.
    img_dist:
        Distorted (compressed) frame, same shape as ``img_ref``.
    window_size:
        Size of the Gaussian sliding window (must be odd, default 11).
    sigma:
        Standard deviation for the Gaussian window.

    Returns
    -------
    Float in [−1, 1]; 1.0 = perfect similarity.
    """
    ref_gray = _to_float_gray(img_ref)
    dist_gray = _to_float_gray(img_dist)

    if ref_gray.shape != dist_gray.shape:
        raise ValueError(
            f"SSIM input shapes differ: {ref_gray.shape} vs {dist_gray.shape}"
        )

    kernel = _gaussian_kernel(window_size, sigma)

    mu1 = _conv2d(ref_gray, kernel)
    mu2 = _conv2d(dist_gray, kernel)

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = _conv2d(ref_gray ** 2, kernel) - mu1_sq
    sigma2_sq = _conv2d(dist_gray ** 2, kernel) - mu2_sq
    sigma12   = _conv2d(ref_gray * dist_gray, kernel) - mu1_mu2

    numerator   = (2 * mu1_mu2 + _SSIM_C1) * (2 * sigma12 + _SSIM_C2)
    denominator = (mu1_sq + mu2_sq + _SSIM_C1) * (sigma1_sq + sigma2_sq + _SSIM_C2)

    ssim_map = np.where(denominator > 0, numerator / denominator, 1.0)
    return float(np.mean(ssim_map))


def compute_regional_ssim(
    img_ref: np.ndarray,
    img_dist: np.ndarray,
    mask: np.ndarray,
) -> float:
    """Compute mean SSIM restricted to pixels where *mask* is non-zero.

    Useful for computing per-tier quality (e.g., face SSIM vs background SSIM).
    """
    ref_gray = _to_float_gray(img_ref)
    dist_gray = _to_float_gray(img_dist)
    mask_bool = mask.astype(bool)

    if not np.any(mask_bool):
        return float("nan")

    ref_region = ref_gray[mask_bool]
    dist_region = dist_gray[mask_bool]

    # Simplified pixel-wise SSIM for masked regions (no windowing)
    mu1 = np.mean(ref_region)
    mu2 = np.mean(dist_region)
    sigma1_sq = np.var(ref_region)
    sigma2_sq = np.var(dist_region)
    sigma12 = np.cov(ref_region, dist_region)[0, 1]

    numerator   = (2 * mu1 * mu2 + _SSIM_C1) * (2 * sigma12 + _SSIM_C2)
    denominator = (mu1**2 + mu2**2 + _SSIM_C1) * (sigma1_sq + sigma2_sq + _SSIM_C2)
    return float(numerator / denominator) if denominator > 0 else 1.0


# ── PSNR ──────────────────────────────────────────────────────────────────────

def compute_psnr(
    img_ref: np.ndarray,
    img_dist: np.ndarray,
    max_val: float = 255.0,
) -> float:
    """Compute Peak Signal-to-Noise Ratio in dB.

    Returns
    -------
    Float in (0, _PSNR_MAX_DB].  ``_PSNR_MAX_DB`` is returned for
    identical images (MSE = 0).
    """
    ref = img_ref.astype(np.float64)
    dist = img_dist.astype(np.float64)

    if ref.shape != dist.shape:
        raise ValueError(f"PSNR shapes differ: {ref.shape} vs {dist.shape}")

    mse = np.mean((ref - dist) ** 2)
    if mse == 0.0:
        return _PSNR_MAX_DB

    psnr = 10.0 * np.log10((max_val ** 2) / mse)
    return float(min(psnr, _PSNR_MAX_DB))


# ── SPQI ──────────────────────────────────────────────────────────────────────

def compute_spqi(
    img_ref: np.ndarray,
    img_dist: np.ndarray,
    priority_map: PriorityMap,
) -> float:
    """Compute the Semantic Perceptual Quality Index (SPQI).

    SPQI is a weighted mean SSIM where the weight of each pixel is its
    normalised priority score.  This ensures that degradation in
    semantically important regions (faces, text) penalises the score far
    more than equivalent degradation in the background.

    Formula
    -------
    SPQI = Σ(w_i × ssim_i) / Σ(w_i)

    where ``w_i = priority_map[i]`` and ``ssim_i`` is the local SSIM
    of an 11×11 window centred on pixel *i*.

    Parameters
    ----------
    img_ref:
        Reference frame (uint8 BGR or grayscale).
    img_dist:
        Distorted / compressed frame, same shape.
    priority_map:
        Float32 priority map (H, W) with values in [0, 1].

    Returns
    -------
    Float in [0, 1]; higher is better.
    """
    ref_gray = _to_float_gray(img_ref)
    dist_gray = _to_float_gray(img_dist)

    kernel = _gaussian_kernel(11, 1.5)

    mu1 = _conv2d(ref_gray, kernel)
    mu2 = _conv2d(dist_gray, kernel)

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = _conv2d(ref_gray ** 2, kernel) - mu1_sq
    sigma2_sq = _conv2d(dist_gray ** 2, kernel) - mu2_sq
    sigma12   = _conv2d(ref_gray * dist_gray, kernel) - mu1_mu2

    numerator   = (2 * mu1_mu2 + _SSIM_C1) * (2 * sigma12 + _SSIM_C2)
    denominator = (mu1_sq + mu2_sq + _SSIM_C1) * (sigma1_sq + sigma2_sq + _SSIM_C2)
    ssim_map    = np.where(denominator > 0, numerator / denominator, 1.0)

    # Resize priority map to match ssim_map (may differ by windowing border)
    if priority_map.shape != ssim_map.shape:
        import cv2  # type: ignore
        pmap_resized = cv2.resize(
            priority_map,
            (ssim_map.shape[1], ssim_map.shape[0]),
            interpolation=cv2.INTER_LINEAR,
        )
    else:
        pmap_resized = priority_map

    weights = pmap_resized.astype(np.float64)
    w_sum = weights.sum()
    if w_sum == 0.0:
        return float(np.mean(ssim_map))

    return float(np.sum(ssim_map * weights) / w_sum)


# ── SEES ──────────────────────────────────────────────────────────────────────

def compute_sees(
    spqi_semantic: float,
    bitrate_semantic_kbps: float,
    spqi_baseline: float,
    bitrate_baseline_kbps: float,
) -> float:
    """Compute the Semantic Efficiency–Experience Score (SEES).

    SEES quantifies *how much better* SemanticStream is compared to a
    uniform-ABR baseline at the same or lower bitrate.

    Formula
    -------
    quality_ratio = spqi_semantic / max(spqi_baseline, ε)
    bitrate_ratio = bitrate_baseline_kbps / max(bitrate_semantic_kbps, ε)
    SEES = (quality_ratio × bitrate_ratio − 1) × 100  [percent]

    Interpretation
    ──────────────
    SEES > 0  : SemanticStream provides better quality per bit
    SEES = 0  : Equivalent to baseline
    SEES < 0  : SemanticStream is worse (should not occur in practice)

    Parameters
    ----------
    spqi_semantic:
        SPQI of the SemanticStream-encoded frame.
    bitrate_semantic_kbps:
        Bitrate (kbps) of the SemanticStream-encoded frame.
    spqi_baseline:
        SPQI of the uniform-ABR-encoded frame (same source).
    bitrate_baseline_kbps:
        Bitrate (kbps) of the uniform-ABR-encoded frame.

    Returns
    -------
    SEES score as a percentage (float).  Positive = SemanticStream wins.
    """
    eps = 1e-6
    quality_ratio = spqi_semantic / max(spqi_baseline, eps)
    bitrate_ratio = bitrate_baseline_kbps / max(bitrate_semantic_kbps, eps)
    sees = (quality_ratio * bitrate_ratio - 1.0) * 100.0
    return float(sees)


def compute_sees_from_qp(
    qp_semantic: float,
    qp_baseline: float,
    spqi_semantic: float,
    spqi_baseline: float,
) -> float:
    """Simplified SEES using QP values as a bitrate proxy.

    Useful when exact bitrate measurements are unavailable.
    QP → bitrate approximation: bitrate ∝ 0.9^QP (empirical).
    """
    bw_semantic = 0.9 ** qp_semantic
    bw_baseline = 0.9 ** qp_baseline
    return compute_sees(spqi_semantic, bw_semantic, spqi_baseline, bw_baseline)


# ── Aggregate helpers ─────────────────────────────────────────────────────────

def aggregate_metrics(metrics: list[dict]) -> dict:
    """Compute mean/min/max for a list of per-frame metric dicts.

    Each dict must have numeric values; missing keys are skipped.

    Returns
    -------
    Dict with ``{key}_mean``, ``{key}_min``, ``{key}_max`` for each key
    present in at least one input dict.
    """
    if not metrics:
        return {}

    all_keys = {k for m in metrics for k in m}
    result: dict = {}

    for key in all_keys:
        values = [m[key] for m in metrics if key in m and m[key] is not None]
        if not values:
            continue
        arr = np.array(values, dtype=float)
        result[f"{key}_mean"] = float(np.mean(arr))
        result[f"{key}_min"]  = float(np.min(arr))
        result[f"{key}_max"]  = float(np.max(arr))

    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _to_float_gray(img: np.ndarray) -> np.ndarray:
    """Convert a BGR or grayscale uint8 image to float64 luminance."""
    try:
        import cv2  # type: ignore
    except ImportError as exc:
        raise RuntimeError("opencv-python is required") from exc

    if img.dtype != np.uint8:
        img = (img * 255).clip(0, 255).astype(np.uint8)

    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    return img.astype(np.float64)


def _gaussian_kernel(size: int, sigma: float) -> np.ndarray:
    """Create a 2-D normalised Gaussian kernel using pure NumPy.

    Uses numpy to compute the 1-D Gaussian window (replaces the removed
    ``scipy.signal.gaussian`` function in newer SciPy versions).
    """
    x = np.arange(size) - (size - 1) / 2.0
    g = np.exp(-(x ** 2) / (2.0 * sigma ** 2))
    g /= g.sum()
    kernel = np.outer(g, g)
    return (kernel / kernel.sum()).astype(np.float64)


def _conv2d(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """2-D convolution using scipy's ndimage correlate (uniform mode)."""
    from scipy.ndimage import correlate  # type: ignore

    return correlate(img, kernel, mode="reflect")
