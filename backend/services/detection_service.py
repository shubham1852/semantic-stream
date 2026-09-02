"""
services/detection_service.py
==============================
Full 5-tier semantic priority pipeline for SemanticStream.

This service is the heart of the AI processing pipeline.  It orchestrates
the YOLO engine, frame utilities, and QP utilities to produce:

  1. A per-frame :class:`FrameAnalysisResult` containing:
     - YOLO detections (persons, objects)
     - Text-region coverage fraction
     - Motion coverage fraction and flow field
     - Priority map + QP matrix
     - SPQI, SSIM, PSNR scores (when a reference frame is available)

  2. A :class:`VideoAnalysisResult` — aggregate statistics and per-frame
     records suitable for persisting to the database via CRUD.

Usage
-----
The service is intentionally *synchronous* internally (OpenCV and ONNX are
blocking) but wrapped for async execution via ``asyncio.to_thread`` in the
API route handlers.

    from backend.services.detection_service import detection_service
    result = await asyncio.to_thread(detection_service.analyse_frame, frame, ...)

Design notes
------------
* Temporal EMA smoothing of the priority map is maintained via an internal
  ``_prev_priority_map`` cache keyed by ``job_id``.
* A ``_prev_gray`` cache per job enables optical-flow computation.
* Both caches are cleared when a job completes via :meth:`clear_job_state`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from backend.core.config import settings
from backend.core.exceptions import VideoNotFoundError
from backend.core.logging_config import get_logger
from backend.models.yolo_engine import Detection, yolo_engine
from backend.utils.frame_utils import (
    compute_histogram,
    compute_optical_flow,
    detect_text_regions,
    extract_frames,
    get_video_metadata,
    high_motion_mask,
    to_grayscale,
    text_area_fraction,
    mask_area_fraction,
)
from backend.utils.metric_utils import (
    compute_psnr,
    compute_spqi,
    compute_ssim,
)
from backend.utils.qp_utils import (
    PriorityMap,
    QPMatrix,
    build_priority_map,
    priority_map_stats,
    priority_to_qp,
    smooth_priority_map,
)

log = get_logger(__name__)


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class FrameAnalysisResult:
    """Results for a single analysed frame."""

    frame_number: int
    timestamp_ms: float

    # Detection
    detections: List[Detection] = field(default_factory=list)
    detection_confidence: float = 0.0   # mean confidence of all detections

    # Priority
    priority_map: Optional[PriorityMap] = None
    qp_matrix: Optional[QPMatrix] = None
    priority_stats: dict = field(default_factory=dict)

    # Text / motion coverage
    text_area_frac: float = 0.0
    motion_area_frac: float = 0.0

    # Quality metrics (None when no reference frame is available)
    spqi_score: Optional[float] = None
    ssim_score: Optional[float] = None
    psnr_score: Optional[float] = None

    # Histogram (for scene-cut detection)
    histogram: Optional[np.ndarray] = None

    # Scene classification
    scene_type: Optional[str] = None

    # Timing
    inference_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class VideoAnalysisResult:
    """Aggregate results for a full video analysis job."""

    job_id: str
    video_id: str
    total_frames_analysed: int = 0
    frame_results: List[FrameAnalysisResult] = field(default_factory=list)

    # Aggregate metrics
    avg_spqi: Optional[float] = None
    avg_ssim: Optional[float] = None
    avg_psnr: Optional[float] = None
    avg_motion_frac: float = 0.0
    avg_text_frac: float = 0.0

    # Timing
    total_processing_ms: float = 0.0
    fps_processed: float = 0.0

    # Error info
    error: Optional[str] = None


# ── Detection service ─────────────────────────────────────────────────────────

class DetectionService:
    """Orchestrates the 5-tier semantic priority pipeline.

    Thread safety
    -------------
    A single ``DetectionService`` instance is safe to share across async
    tasks as long as each *job* uses a unique ``job_id``.  The per-job
    state (previous priority map, previous grayscale frame) is stored in
    separate dicts keyed by ``job_id`` and never shared.
    """

    def __init__(self) -> None:
        self._prev_priority: Dict[str, PriorityMap] = {}
        self._prev_gray: Dict[str, np.ndarray] = {}

    # ── Frame-level analysis ──────────────────────────────────────────────────

    def analyse_frame(
        self,
        frame_bgr: np.ndarray,
        frame_number: int,
        timestamp_ms: float,
        job_id: str = "default",
        reference_frame: Optional[np.ndarray] = None,
        confidence_threshold: Optional[float] = None,
    ) -> FrameAnalysisResult:
        """Run the full 5-tier pipeline on a single frame.

        Parameters
        ----------
        frame_bgr:
            The source frame as a BGR uint8 NumPy array.
        frame_number:
            Sequential frame index within the video.
        timestamp_ms:
            Frame timestamp in milliseconds.
        job_id:
            Unique identifier for this analysis job (used to maintain
            per-job temporal state).
        reference_frame:
            An optional uncompressed reference frame for computing SSIM /
            SPQI.  If ``None``, those metrics are skipped.
        confidence_threshold:
            Override detection confidence threshold.  Defaults to
            ``settings.CONFIDENCE_THRESHOLD``.

        Returns
        -------
        :class:`FrameAnalysisResult`
        """
        t_start = time.perf_counter()
        result = FrameAnalysisResult(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
        )

        h, w = frame_bgr.shape[:2]

        # ── 1. YOLO detection ──────────────────────────────────────────────
        t_inf = time.perf_counter()
        try:
            detections = yolo_engine.detect(frame_bgr)
            if confidence_threshold is not None:
                detections = [
                    d for d in detections
                    if d.confidence >= confidence_threshold
                ]
        except Exception as exc:
            log.warning("detection_failed", frame=frame_number, error=str(exc))
            detections = []

        result.detections = detections
        result.detection_confidence = (
            float(np.mean([d.confidence for d in detections]))
            if detections else 0.0
        )
        result.inference_ms = (time.perf_counter() - t_inf) * 1000

        # ── 2. Text region detection ───────────────────────────────────────
        try:
            text_mask = detect_text_regions(frame_bgr)
            result.text_area_frac = mask_area_fraction(text_mask)
        except Exception as exc:
            log.debug("text_detection_failed", error=str(exc))
            text_mask = None
            result.text_area_frac = 0.0

        # ── 3. Optical flow (motion) ───────────────────────────────────────
        flow_mask: Optional[np.ndarray] = None
        curr_gray = to_grayscale(frame_bgr)
        prev_gray = self._prev_gray.get(job_id)

        if prev_gray is not None and prev_gray.shape == curr_gray.shape:
            try:
                flow = compute_optical_flow(prev_gray, curr_gray)
                flow_mask = high_motion_mask(flow).astype(np.uint8) * 255
                result.motion_area_frac = mask_area_fraction(flow_mask)
            except Exception as exc:
                log.debug("optical_flow_failed", error=str(exc))

        self._prev_gray[job_id] = curr_gray

        # ── 4. Priority map ────────────────────────────────────────────────
        try:
            raw_pmap = build_priority_map(
                frame_shape=(h, w),
                detections=detections,
                text_mask=text_mask,
                flow_mask=flow_mask,
            )
            smoothed_pmap = smooth_priority_map(
                current=raw_pmap,
                previous=self._prev_priority.get(job_id),
            )
            self._prev_priority[job_id] = smoothed_pmap
            result.priority_map = smoothed_pmap
            result.priority_stats = priority_map_stats(smoothed_pmap)
        except Exception as exc:
            log.warning("priority_map_failed", frame=frame_number, error=str(exc))

        # ── 5. QP matrix ───────────────────────────────────────────────────
        if result.priority_map is not None:
            try:
                result.qp_matrix = priority_to_qp(result.priority_map)
            except Exception as exc:
                log.warning("qp_matrix_failed", error=str(exc))

        # ── 6. Quality metrics ─────────────────────────────────────────────
        if reference_frame is not None and result.priority_map is not None:
            try:
                result.ssim_score = compute_ssim(reference_frame, frame_bgr)
                result.psnr_score = compute_psnr(reference_frame, frame_bgr)
                result.spqi_score = compute_spqi(
                    reference_frame, frame_bgr, result.priority_map
                )
            except Exception as exc:
                log.debug("quality_metrics_failed", error=str(exc))

        # ── 7. Histogram ───────────────────────────────────────────────────
        try:
            result.histogram = compute_histogram(frame_bgr)
        except Exception:
            pass

        # ── 8. Scene classification ────────────────────────────────────────
        result.scene_type = self._classify_scene(
            detections=detections,
            text_area_frac=result.text_area_frac,
            motion_area_frac=result.motion_area_frac,
        )

        result.total_ms = (time.perf_counter() - t_start) * 1000
        return result

    # ── Video-level analysis ──────────────────────────────────────────────────

    def analyse_video(
        self,
        video_path: str | Path,
        job_id: str,
        video_id: str,
        sample_rate: int = settings.DEFAULT_FRAME_SAMPLE_RATE,
        confidence_threshold: float = settings.CONFIDENCE_THRESHOLD,
        progress_callback=None,
    ) -> VideoAnalysisResult:
        """Analyse an entire video file and return aggregate results.

        Parameters
        ----------
        video_path:
            Filesystem path to the source video.
        job_id / video_id:
            Database identifiers for progress tracking and storage.
        sample_rate:
            Analyse every *N*-th frame.
        confidence_threshold:
            YOLO confidence filter.
        progress_callback:
            Optional ``callable(progress_pct: float)`` called after each
            frame to report progress (0–100).

        Returns
        -------
        :class:`VideoAnalysisResult`
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise VideoNotFoundError(str(video_path))

        try:
            meta = get_video_metadata(video_path)
        except Exception as exc:
            return VideoAnalysisResult(
                job_id=job_id,
                video_id=video_id,
                error=f"Failed to read video metadata: {exc}",
            )

        total_frames = meta["total_frames"]
        expected_analysed = max(1, total_frames // max(1, sample_rate))

        t_start = time.perf_counter()
        frame_results: List[FrameAnalysisResult] = []
        analysed = 0

        log.info(
            "video_analysis_start",
            job_id=job_id,
            video=str(video_path),
            total_frames=total_frames,
            sample_rate=sample_rate,
        )

        try:
            for frame_num, ts_ms, frame in extract_frames(
                video_path, sample_rate=sample_rate
            ):
                fr = self.analyse_frame(
                    frame_bgr=frame,
                    frame_number=frame_num,
                    timestamp_ms=ts_ms,
                    job_id=job_id,
                    confidence_threshold=confidence_threshold,
                )
                frame_results.append(fr)
                analysed += 1

                if progress_callback is not None:
                    pct = min(100.0, analysed / expected_analysed * 100.0)
                    try:
                        progress_callback(pct)
                    except Exception:
                        pass

        except Exception as exc:
            log.error("video_analysis_error", job_id=job_id, error=str(exc))
            return VideoAnalysisResult(
                job_id=job_id,
                video_id=video_id,
                total_frames_analysed=analysed,
                frame_results=frame_results,
                error=str(exc),
            )
        finally:
            self.clear_job_state(job_id)

        elapsed_s = time.perf_counter() - t_start

        # Aggregate metrics
        spqi_vals = [r.spqi_score for r in frame_results if r.spqi_score is not None]
        ssim_vals = [r.ssim_score for r in frame_results if r.ssim_score is not None]
        psnr_vals = [r.psnr_score for r in frame_results if r.psnr_score is not None]

        result = VideoAnalysisResult(
            job_id=job_id,
            video_id=video_id,
            total_frames_analysed=analysed,
            frame_results=frame_results,
            avg_spqi=float(np.mean(spqi_vals)) if spqi_vals else None,
            avg_ssim=float(np.mean(ssim_vals)) if ssim_vals else None,
            avg_psnr=float(np.mean(psnr_vals)) if psnr_vals else None,
            avg_motion_frac=float(
                np.mean([r.motion_area_frac for r in frame_results])
            ) if frame_results else 0.0,
            avg_text_frac=float(
                np.mean([r.text_area_frac for r in frame_results])
            ) if frame_results else 0.0,
            total_processing_ms=elapsed_s * 1000,
            fps_processed=analysed / elapsed_s if elapsed_s > 0 else 0.0,
        )

        log.info(
            "video_analysis_complete",
            job_id=job_id,
            frames=analysed,
            elapsed_s=round(elapsed_s, 2),
            fps=round(result.fps_processed, 1),
            avg_spqi=result.avg_spqi,
        )
        return result

    # ── Scene classification ──────────────────────────────────────────────────

    @staticmethod
    def _classify_scene(
        detections: List[Detection],
        text_area_frac: float,
        motion_area_frac: float,
    ) -> str:
        """Classify the scene into one of the SemanticStream scene types.

        Scene types
        -----------
        * ``dialogue``    — persons present, little motion, possibly text
        * ``action``      — high motion, persons present
        * ``text_heavy``  — large text region dominates the frame
        * ``ambient``     — background / static / b-roll
        * ``mixed``       — multiple tiers active
        """
        has_person = any(d.is_person for d in detections)
        text_heavy = text_area_frac >= settings.TEXT_AREA_THRESHOLD
        high_motion = motion_area_frac >= settings.MOTION_DOMINANT_THRESHOLD / 100.0

        if text_heavy:
            return "text_heavy"
        if has_person and high_motion:
            return "action"
        if has_person and not high_motion:
            return "dialogue"
        if high_motion:
            return "motion"
        return "ambient"

    # ── State management ──────────────────────────────────────────────────────

    def clear_job_state(self, job_id: str) -> None:
        """Remove per-job temporal caches (call after a job finishes)."""
        self._prev_priority.pop(job_id, None)
        self._prev_gray.pop(job_id, None)
        log.debug("job_state_cleared", job_id=job_id)

    def active_jobs(self) -> List[str]:
        """Return job IDs with active temporal state."""
        return list(self._prev_gray.keys())


# ── Module-level singleton ────────────────────────────────────────────────────

detection_service = DetectionService()
