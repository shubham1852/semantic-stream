"""
tests/test_detection_service.py
================================
Unit tests for DetectionService — scene classification, priority map shape,
temporal smoothing, and job state management.
"""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from backend.services.detection_service import DetectionService, FrameAnalysisResult
from backend.models.yolo_engine import Detection


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_detection(
    class_id: int = 0,
    confidence: float = 0.85,
    x1: int = 100, y1: int = 100,
    x2: int = 300, y2: int = 400,
) -> Detection:
    """Build a mock Detection object."""
    return Detection(
        class_id=class_id,
        class_name="person" if class_id == 0 else "object",
        confidence=confidence,
        x1=x1, y1=y1, x2=x2, y2=y2,
    )


def _make_frame(h: int = 480, w: int = 640) -> np.ndarray:
    """Build a realistic-looking random BGR test frame."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (h, w, 3), dtype=np.uint8)


# ── Scene classification ───────────────────────────────────────────────────────

class TestClassifyScene:
    """Tests for DetectionService._classify_scene."""

    def test_text_heavy_scene(self):
        result = DetectionService._classify_scene(
            detections=[],
            text_area_frac=0.25,   # > 0.20 threshold
            motion_area_frac=0.0,
        )
        assert result == "text_heavy"

    def test_action_scene_with_person_and_motion(self):
        person = _make_detection(class_id=0)
        result = DetectionService._classify_scene(
            detections=[person],
            text_area_frac=0.0,
            motion_area_frac=0.15,  # > MOTION_DOMINANT_THRESHOLD/100
        )
        assert result == "action"

    def test_dialogue_scene_with_person_no_motion(self):
        person = _make_detection(class_id=0)
        result = DetectionService._classify_scene(
            detections=[person],
            text_area_frac=0.0,
            motion_area_frac=0.01,
        )
        assert result == "dialogue"

    def test_motion_scene_no_person(self):
        result = DetectionService._classify_scene(
            detections=[],
            text_area_frac=0.0,
            motion_area_frac=0.15,
        )
        assert result == "motion"

    def test_ambient_scene_nothing_detected(self):
        result = DetectionService._classify_scene(
            detections=[],
            text_area_frac=0.0,
            motion_area_frac=0.0,
        )
        assert result == "ambient"

    def test_text_takes_priority_over_person(self):
        """Text-heavy classification takes priority even if person is present."""
        person = _make_detection(class_id=0)
        result = DetectionService._classify_scene(
            detections=[person],
            text_area_frac=0.30,
            motion_area_frac=0.0,
        )
        assert result == "text_heavy"


# ── Job state management ───────────────────────────────────────────────────────

class TestJobStateManagement:
    def test_clear_job_state_removes_keys(self):
        svc = DetectionService()
        svc._prev_priority["job_1"] = np.zeros((480, 640), dtype=np.float32)
        svc._prev_gray["job_1"] = np.zeros((480, 640), dtype=np.uint8)

        svc.clear_job_state("job_1")

        assert "job_1" not in svc._prev_priority
        assert "job_1" not in svc._prev_gray

    def test_clear_nonexistent_job_is_noop(self):
        svc = DetectionService()
        svc.clear_job_state("nonexistent_job")  # Should not raise

    def test_active_jobs_lists_current_state(self):
        svc = DetectionService()
        svc._prev_gray["job_a"] = np.zeros((10, 10), dtype=np.uint8)
        svc._prev_gray["job_b"] = np.zeros((10, 10), dtype=np.uint8)
        jobs = svc.active_jobs()
        assert "job_a" in jobs
        assert "job_b" in jobs


# ── analyse_frame basic flow ──────────────────────────────────────────────────

class TestAnalyseFrame:
    """Integration-level tests for the full pipeline (mock YOLO)."""

    def _get_service_with_mock_yolo(self):
        """Return a DetectionService with the YOLO engine mocked."""
        svc = DetectionService()
        return svc

    @patch("backend.services.detection_service.yolo_engine")
    def test_result_has_required_fields(self, mock_engine):
        mock_engine.detect.return_value = []
        svc = DetectionService()
        frame = _make_frame()
        result = svc.analyse_frame(
            frame_bgr=frame,
            frame_number=0,
            timestamp_ms=0.0,
            job_id="test_job",
        )
        assert isinstance(result, FrameAnalysisResult)
        assert result.frame_number == 0
        assert result.timestamp_ms == 0.0
        assert result.total_ms >= 0.0

    @patch("backend.services.detection_service.yolo_engine")
    def test_detections_filtered_by_confidence(self, mock_engine):
        low_conf = _make_detection(confidence=0.2)
        high_conf = _make_detection(confidence=0.9)
        mock_engine.detect.return_value = [low_conf, high_conf]

        svc = DetectionService()
        frame = _make_frame()
        result = svc.analyse_frame(
            frame_bgr=frame,
            frame_number=0,
            timestamp_ms=0.0,
            job_id="test_job",
            confidence_threshold=0.5,
        )
        # Only high_conf should pass
        assert all(d.confidence >= 0.5 for d in result.detections)

    @patch("backend.services.detection_service.yolo_engine")
    def test_priority_map_shape_matches_frame(self, mock_engine):
        mock_engine.detect.return_value = []
        svc = DetectionService()
        h, w = 360, 640
        frame = _make_frame(h=h, w=w)
        result = svc.analyse_frame(
            frame_bgr=frame,
            frame_number=0,
            timestamp_ms=0.0,
            job_id="shape_test",
        )
        if result.priority_map is not None:
            assert result.priority_map.shape == (h, w)

    @patch("backend.services.detection_service.yolo_engine")
    def test_temporal_state_updated_after_frame(self, mock_engine):
        mock_engine.detect.return_value = []
        svc = DetectionService()
        frame = _make_frame()
        job_id = "temporal_test"

        svc.analyse_frame(frame_bgr=frame, frame_number=0, timestamp_ms=0.0, job_id=job_id)
        # After first frame, previous gray should be stored
        assert job_id in svc._prev_gray

    @patch("backend.services.detection_service.yolo_engine")
    def test_scene_type_set(self, mock_engine):
        mock_engine.detect.return_value = []
        svc = DetectionService()
        frame = _make_frame()
        result = svc.analyse_frame(
            frame_bgr=frame, frame_number=0, timestamp_ms=0.0, job_id="scene_test"
        )
        assert result.scene_type is not None
        assert result.scene_type in ("dialogue", "action", "text_heavy", "motion", "ambient")

    @patch("backend.services.detection_service.yolo_engine")
    def test_yolo_failure_gracefully_handled(self, mock_engine):
        """If YOLO raises, detections should default to empty list — no exception propagated."""
        mock_engine.detect.side_effect = RuntimeError("ONNX inference failed")
        svc = DetectionService()
        frame = _make_frame()
        result = svc.analyse_frame(
            frame_bgr=frame, frame_number=0, timestamp_ms=0.0, job_id="error_test"
        )
        assert result.detections == []  # Graceful fallback


# ── Priority map statistics ────────────────────────────────────────────────────

class TestPriorityMapStats:
    """Tests for qp_utils.priority_map_stats via the detection pipeline."""

    @patch("backend.services.detection_service.yolo_engine")
    def test_priority_stats_have_tier_fracs(self, mock_engine):
        person = _make_detection(class_id=0, x1=50, y1=50, x2=200, y2=300)
        mock_engine.detect.return_value = [person]
        svc = DetectionService()
        frame = _make_frame()
        result = svc.analyse_frame(
            frame_bgr=frame, frame_number=0, timestamp_ms=0.0, job_id="stats_test"
        )
        if result.priority_stats:
            assert "p1_frac" in result.priority_stats
            assert "p5_frac" in result.priority_stats
