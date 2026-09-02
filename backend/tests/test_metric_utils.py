"""
tests/test_metric_utils.py
==========================
Unit tests for SPQI, SSIM, PSNR, and SEES metric formulas.

Tests are written with pytest and use only NumPy arrays — no
database, no FastAPI, no FFmpeg required.

Fixed to match actual function signatures in metric_utils.py:
- PriorityMap is a numpy.ndarray type alias (not a class with constructor kwargs)
- compute_sees() takes 4 positional args: spqi_semantic, bitrate_semantic_kbps,
  spqi_baseline, bitrate_baseline_kbps
- aggregate_metrics() returns {key_mean, key_min, key_max} not {avg_key}
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.utils.metric_utils import (
    compute_ssim,
    compute_psnr,
    compute_spqi,
    compute_sees,
    aggregate_metrics,
)
# PriorityMap is a type alias for np.ndarray — not a class with a constructor
from backend.utils.qp_utils import PriorityMap


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def identical_frames_gray() -> tuple[np.ndarray, np.ndarray]:
    """Two identical 64×64 greyscale frames."""
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 256, (64, 64), dtype=np.uint8)
    return frame, frame.copy()


@pytest.fixture
def noisy_frames_gray() -> tuple[np.ndarray, np.ndarray]:
    """Reference frame and a noisy distorted frame."""
    rng = np.random.default_rng(7)
    ref = rng.integers(50, 200, (64, 64), dtype=np.uint8)
    noise = rng.integers(-30, 30, (64, 64))
    dist = np.clip(ref.astype(np.int32) + noise, 0, 255).astype(np.uint8)
    return ref, dist


@pytest.fixture
def blank_priority_map() -> PriorityMap:
    """64×64 priority map (np.ndarray) with all pixels at P5 level = 0.1."""
    return np.full((64, 64), 0.1, dtype=np.float32)


@pytest.fixture
def mixed_priority_map() -> PriorityMap:
    """64×64 priority map (np.ndarray) with a P1 face region in top-left."""
    data = np.full((64, 64), 0.1, dtype=np.float32)
    data[:32, :32] = 1.0   # P1 face region
    data[32:, 32:] = 0.4   # P4 object region
    return data


# ── SSIM tests ─────────────────────────────────────────────────────────────────

class TestComputeSsim:
    def test_identical_frames_ssim_is_one(self, identical_frames_gray):
        ref, dist = identical_frames_gray
        score = compute_ssim(ref, dist)
        assert score == pytest.approx(1.0, abs=1e-3), (
            "SSIM of identical frames must be ~1.0"
        )

    def test_ssim_in_range(self, noisy_frames_gray):
        ref, dist = noisy_frames_gray
        score = compute_ssim(ref, dist)
        assert 0.0 <= score <= 1.0, f"SSIM must be in [0,1], got {score}"

    def test_noisy_ssim_less_than_identical(self, identical_frames_gray, noisy_frames_gray):
        ref_id, dist_id = identical_frames_gray
        ref_noisy, dist_noisy = noisy_frames_gray
        ssim_perfect = compute_ssim(ref_id, dist_id)
        ssim_noisy   = compute_ssim(ref_noisy, dist_noisy)
        assert ssim_noisy < ssim_perfect, (
            "SSIM of noisy pair must be below perfect SSIM"
        )

    def test_accepts_bgr_frames(self):
        rng = np.random.default_rng(0)
        ref  = rng.integers(0, 256, (32, 32, 3), dtype=np.uint8)
        dist = ref.copy()
        score = compute_ssim(ref, dist)
        assert score == pytest.approx(1.0, abs=1e-3)

    def test_mismatched_shapes_raises(self):
        with pytest.raises((ValueError, AssertionError)):
            compute_ssim(
                np.zeros((32, 32), dtype=np.uint8),
                np.zeros((64, 64), dtype=np.uint8),
            )


# ── PSNR tests ─────────────────────────────────────────────────────────────────

class TestComputePsnr:
    def test_identical_frames_psnr_is_capped(self, identical_frames_gray):
        ref, dist = identical_frames_gray
        score = compute_psnr(ref, dist)
        assert score == pytest.approx(60.0, abs=1e-6), (
            "PSNR for identical frames must return the cap value (60 dB)"
        )

    def test_psnr_positive(self, noisy_frames_gray):
        ref, dist = noisy_frames_gray
        score = compute_psnr(ref, dist)
        assert score > 0.0

    def test_higher_noise_lower_psnr(self):
        ref = np.full((64, 64), 128, dtype=np.uint8)
        light_noise = np.clip(ref.astype(np.int32) + 5,  0, 255).astype(np.uint8)
        heavy_noise = np.clip(ref.astype(np.int32) + 50, 0, 255).astype(np.uint8)
        assert compute_psnr(ref, light_noise) > compute_psnr(ref, heavy_noise)


# ── SPQI tests ─────────────────────────────────────────────────────────────────

class TestComputeSpqi:
    def test_identical_frames_spqi_is_one(self, identical_frames_gray, mixed_priority_map):
        ref, dist = identical_frames_gray
        score = compute_spqi(ref, dist, mixed_priority_map)
        assert score == pytest.approx(1.0, abs=0.01), (
            "SPQI of identical frames must be ~1.0 regardless of priority map"
        )

    def test_spqi_in_range(self, noisy_frames_gray, mixed_priority_map):
        ref, dist = noisy_frames_gray
        score = compute_spqi(ref, dist, mixed_priority_map)
        assert 0.0 <= score <= 1.0, f"SPQI must be in [0,1], got {score}"

    def test_spqi_weights_high_priority_regions(self):
        """SPQI should be higher when the high-quality region is high-priority."""
        rng = np.random.default_rng(1)
        ref = rng.integers(50, 200, (64, 64), dtype=np.uint8)

        # Distorted: perfect in top-left, noisy elsewhere
        dist_good_face = ref.copy()
        dist_good_face[32:, 32:] = np.clip(
            ref[32:, 32:].astype(np.int32) + 60, 0, 255
        ).astype(np.uint8)

        # Distorted: noisy in top-left (face), perfect elsewhere
        dist_bad_face = ref.copy()
        dist_bad_face[:32, :32] = np.clip(
            ref[:32, :32].astype(np.int32) + 60, 0, 255
        ).astype(np.uint8)

        # PriorityMap is just an np.ndarray
        pmap = np.block([
            [np.full((32, 32), 1.0, dtype=np.float32), np.full((32, 32), 0.1, dtype=np.float32)],
            [np.full((32, 32), 0.1, dtype=np.float32), np.full((32, 32), 0.1, dtype=np.float32)],
        ])
        spqi_good_face = compute_spqi(ref, dist_good_face, pmap)
        spqi_bad_face  = compute_spqi(ref, dist_bad_face,  pmap)

        assert spqi_good_face > spqi_bad_face, (
            "SPQI must be higher when the P1 (face) region is better preserved"
        )

    def test_all_background_map_matches_ssim(self, noisy_frames_gray, blank_priority_map):
        """With a uniform-weight map, SPQI ≈ SSIM."""
        ref, dist = noisy_frames_gray
        spqi = compute_spqi(ref, dist, blank_priority_map)
        ssim = compute_ssim(ref, dist)
        # Allow 5% tolerance — small differences due to windowing
        assert abs(spqi - ssim) < 0.05, (
            f"Uniform-weight SPQI ({spqi:.4f}) should approximate SSIM ({ssim:.4f})"
        )


# ── SEES tests ─────────────────────────────────────────────────────────────────
# compute_sees(spqi_semantic, bitrate_semantic_kbps, spqi_baseline, bitrate_baseline_kbps)
# Returns a float percentage: positive = SemanticStream wins

class TestComputeSees:
    def test_sees_positive_when_semantic_wins(self):
        """SemanticStream higher quality at lower bitrate → positive SEES."""
        score = compute_sees(
            spqi_semantic=0.91,
            bitrate_semantic_kbps=1620.0,
            spqi_baseline=0.72,
            bitrate_baseline_kbps=2800.0,
        )
        assert score > 0, f"SEES must be positive when SemanticStream wins, got {score}"

    def test_sees_zero_when_equal(self):
        """Same SPQI and same bitrate → SEES = 0%."""
        score = compute_sees(
            spqi_semantic=0.80,
            bitrate_semantic_kbps=2000.0,
            spqi_baseline=0.80,
            bitrate_baseline_kbps=2000.0,
        )
        assert score == pytest.approx(0.0, abs=1e-4)

    def test_sees_negative_when_baseline_wins(self):
        """Baseline higher quality at lower bitrate → negative SEES."""
        score = compute_sees(
            spqi_semantic=0.5,
            bitrate_semantic_kbps=3000.0,
            spqi_baseline=0.9,
            bitrate_baseline_kbps=1000.0,
        )
        assert score < 0

    def test_sees_zero_baseline_handled(self):
        """Zero baseline bitrate should not raise ZeroDivisionError."""
        score = compute_sees(
            spqi_semantic=0.9,
            bitrate_semantic_kbps=0.0,
            spqi_baseline=0.7,
            bitrate_baseline_kbps=0.0,
        )
        assert isinstance(score, float)

    def test_sees_returns_float(self):
        score = compute_sees(0.91, 1620.0, 0.72, 2800.0)
        assert isinstance(score, float)


# ── aggregate_metrics tests ────────────────────────────────────────────────────
# aggregate_metrics returns {key_mean, key_min, key_max} for each key

class TestAggregateMetrics:
    def test_empty_list_returns_empty_dict(self):
        result = aggregate_metrics([])
        assert result == {}

    def test_single_frame_passthrough(self):
        frames = [{"spqi": 0.9, "ssim": 0.88, "psnr": 38.2, "bitrate_kbps": 1500.0}]
        result = aggregate_metrics(frames)
        assert result["spqi_mean"] == pytest.approx(0.9, abs=1e-6)
        assert result["ssim_mean"] == pytest.approx(0.88, abs=1e-6)

    def test_averages_multiple_frames(self):
        frames = [
            {"spqi": 0.8, "ssim": 0.82, "psnr": 36.0, "bitrate_kbps": 1200.0},
            {"spqi": 0.9, "ssim": 0.92, "psnr": 40.0, "bitrate_kbps": 1600.0},
        ]
        result = aggregate_metrics(frames)
        assert result["spqi_mean"] == pytest.approx(0.85, abs=1e-6)
        assert result["ssim_mean"] == pytest.approx(0.87, abs=1e-6)
        assert result["psnr_mean"] == pytest.approx(38.0, abs=1e-6)

    def test_min_max_present(self):
        frames = [
            {"spqi": 0.8, "ssim": 0.82},
            {"spqi": 0.9, "ssim": 0.92},
        ]
        result = aggregate_metrics(frames)
        assert result["spqi_min"] == pytest.approx(0.8, abs=1e-6)
        assert result["spqi_max"] == pytest.approx(0.9, abs=1e-6)

    def test_skips_none_values(self):
        frames = [
            {"spqi": None, "ssim": 0.85},
            {"spqi": 0.9, "ssim": None},
        ]
        result = aggregate_metrics(frames)
        assert result["spqi_mean"] == pytest.approx(0.9, abs=1e-6)
        assert result["ssim_mean"] == pytest.approx(0.85, abs=1e-6)
