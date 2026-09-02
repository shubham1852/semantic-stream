"""
tests/test_analytics_service.py
================================
Unit tests for AnalyticsService metric helpers and DB persistence methods.

Tests cover:
- SPQI computation via _scene_breakdown
- _estimate_bitrate_reduction logic
- _build_metrics_payload structure
- _pick_winner logic
- summarise_frame serialisation
"""

from __future__ import annotations

from unittest.mock import MagicMock, AsyncMock
import numpy as np
import pytest

from backend.services.analytics_service import AnalyticsService, _round
from backend.services.detection_service import FrameAnalysisResult, VideoAnalysisResult


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_frame(
    frame_number: int = 0,
    spqi: float | None = 0.9,
    ssim: float | None = 0.88,
    psnr: float | None = 38.0,
    scene_type: str = "dialogue",
    total_ms: float = 30.0,
) -> FrameAnalysisResult:
    """Build a minimal FrameAnalysisResult for testing."""
    fr = FrameAnalysisResult(frame_number=frame_number, timestamp_ms=frame_number * 33.3)
    fr.spqi_score = spqi
    fr.ssim_score = ssim
    fr.psnr_score = psnr
    fr.scene_type = scene_type
    fr.total_ms = total_ms
    fr.detections = []
    fr.priority_stats = {"p1_frac": 0.1, "p2_frac": 0.05, "p3_frac": 0.15, "p4_frac": 0.2, "p5_frac": 0.5}
    return fr


# ── _round helper ──────────────────────────────────────────────────────────────

class TestRound:
    def test_rounds_float(self):
        assert _round(0.123456, 4) == 0.1235

    def test_returns_none_for_none(self):
        assert _round(None) is None

    def test_zero(self):
        assert _round(0.0) == 0.0


# ── _scene_breakdown ───────────────────────────────────────────────────────────

class TestSceneBreakdown:
    def test_groups_by_scene_type(self):
        frames = [
            _make_frame(0, spqi=0.9, scene_type="dialogue"),
            _make_frame(1, spqi=0.85, scene_type="dialogue"),
            _make_frame(2, spqi=0.7, scene_type="action"),
        ]
        result = AnalyticsService._scene_breakdown(frames)
        assert "dialogue" in result
        assert "action" in result
        assert result["dialogue"]["frame_count"] == 2
        assert result["action"]["frame_count"] == 1

    def test_avg_spqi_computed(self):
        frames = [
            _make_frame(0, spqi=0.8, scene_type="ambient"),
            _make_frame(1, spqi=1.0, scene_type="ambient"),
        ]
        result = AnalyticsService._scene_breakdown(frames)
        assert abs(result["ambient"]["avg_spqi"] - 0.9) < 0.001

    def test_none_spqi_excluded(self):
        frames = [
            _make_frame(0, spqi=None, scene_type="dialogue"),
            _make_frame(1, spqi=0.9, scene_type="dialogue"),
        ]
        result = AnalyticsService._scene_breakdown(frames)
        assert result["dialogue"]["avg_spqi"] == pytest.approx(0.9, abs=0.001)

    def test_empty_frames(self):
        result = AnalyticsService._scene_breakdown([])
        assert result == {}

    def test_null_scene_defaults_to_ambient(self):
        frames = [_make_frame(0, spqi=0.8, scene_type=None)]
        result = AnalyticsService._scene_breakdown(frames)
        assert "ambient" in result


# ── _estimate_bitrate_reduction ────────────────────────────────────────────────

class TestEstimateBitrateReduction:
    def test_returns_none_when_no_qp_matrix(self):
        fr = _make_frame(0)
        fr.qp_matrix = None
        video_result = VideoAnalysisResult(
            job_id="j1", video_id="v1", frame_results=[fr]
        )
        assert AnalyticsService._estimate_bitrate_reduction(video_result) is None

    def test_positive_qp_delta_gives_reduction(self):
        """QP higher than uniform (28) means bitrate saved."""
        fr = _make_frame(0)
        fr.qp_matrix = np.full((9, 16), 34, dtype=np.int32)  # QP=34 > QP_UNIFORM=28
        video_result = VideoAnalysisResult(
            job_id="j1", video_id="v1", frame_results=[fr]
        )
        pct = AnalyticsService._estimate_bitrate_reduction(video_result)
        assert pct is not None
        assert pct > 0  # Higher QP → lower bitrate → positive savings

    def test_multiple_frames_averaged(self):
        fr1 = _make_frame(0)
        fr1.qp_matrix = np.full((9, 16), 30, dtype=np.int32)
        fr2 = _make_frame(1)
        fr2.qp_matrix = np.full((9, 16), 34, dtype=np.int32)
        video_result = VideoAnalysisResult(
            job_id="j1", video_id="v1", frame_results=[fr1, fr2]
        )
        pct = AnalyticsService._estimate_bitrate_reduction(video_result)
        assert pct is not None
        assert isinstance(pct, float)


# ── _build_metrics_payload ────────────────────────────────────────────────────

class TestBuildMetricsPayload:
    def _mock_job(self):
        job = MagicMock()
        job.avg_ssim = 0.93
        job.avg_spqi = 0.91
        job.avg_bitrate_kbps = 1620.0
        job.sees_score = 0.67
        job.bitrate_reduction_pct = 42.3
        return job

    def _mock_frame_metric(self, frame_number: int):
        fm = MagicMock()
        fm.frame_number = frame_number
        fm.timestamp_ms = frame_number * 33.3
        fm.psnr_score = 38.0
        fm.ssim_score = 0.93
        fm.spqi_score = 0.91
        fm.bitrate_kbps = 1620.0
        fm.detection_confidence = 0.85
        fm.scene_type = "dialogue"
        fm.sees_contribution_ms = 30.0
        return fm

    def _mock_scene_event(self):
        se = MagicMock()
        se.frame_number = 50
        se.timestamp_ms = 1666.5
        se.previous_scene_type = "dialogue"
        se.new_scene_type = "action"
        se.histogram_score = 0.45
        return se

    def test_structure(self):
        job = self._mock_job()
        frames = [self._mock_frame_metric(i) for i in range(3)]
        events = [self._mock_scene_event()]
        payload = AnalyticsService._build_metrics_payload(job, frames, events)
        assert "per_frame_metrics" in payload
        assert "summary" in payload
        assert "scene_events" in payload

    def test_frame_count(self):
        job = self._mock_job()
        frames = [self._mock_frame_metric(i) for i in range(5)]
        payload = AnalyticsService._build_metrics_payload(job, frames, [])
        assert len(payload["per_frame_metrics"]) == 5
        assert payload["summary"]["total_frames"] == 5

    def test_scene_events_serialised(self):
        job = self._mock_job()
        events = [self._mock_scene_event()]
        payload = AnalyticsService._build_metrics_payload(job, [], events)
        assert len(payload["scene_events"]) == 1
        assert payload["scene_events"][0]["new_scene_type"] == "action"


# ── _pick_winner ───────────────────────────────────────────────────────────────

class TestPickWinner:
    def test_picks_highest_spqi(self):
        strategies = {
            "uniform_abr": {"avg_spqi": 0.72},
            "static_roi": {"avg_spqi": 0.81},
            "semanticstream": {"avg_spqi": 0.91},
        }
        assert AnalyticsService._pick_winner(strategies) == "semanticstream"

    def test_handles_none_spqi(self):
        strategies = {
            "uniform_abr": {"avg_spqi": None},
            "static_roi": {"avg_spqi": 0.81},
        }
        assert AnalyticsService._pick_winner(strategies) == "static_roi"

    def test_empty_strategies_returns_none(self):
        assert AnalyticsService._pick_winner({}) is None

    def test_single_strategy(self):
        strategies = {"semanticstream": {"avg_spqi": 0.91}}
        assert AnalyticsService._pick_winner(strategies) == "semanticstream"


# ── summarise_frame ────────────────────────────────────────────────────────────

class TestSummariseFrame:
    def test_keys_present(self):
        service = AnalyticsService(db=None)
        fr = _make_frame(frame_number=5, spqi=0.9, ssim=0.88, psnr=38.0)
        fr.priority_map = np.full((480, 640), 0.5, dtype=np.float32)
        payload = service.summarise_frame(fr)
        assert "frame_number" in payload
        assert "spqi" in payload
        assert "ssim" in payload
        assert "detections" in payload
        assert "current_qp_assignments" in payload
        assert "priority_map_base64" in payload

    def test_frame_number_matches(self):
        service = AnalyticsService(db=None)
        fr = _make_frame(frame_number=42)
        payload = service.summarise_frame(fr)
        assert payload["frame_number"] == 42

    def test_spqi_value(self):
        service = AnalyticsService(db=None)
        fr = _make_frame(spqi=0.91)
        payload = service.summarise_frame(fr)
        assert payload["spqi"] == 0.91
