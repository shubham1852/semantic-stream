# FILE: backend/services/detection_service.py
"""
services/detection_service.py
==============================
Full 5-tier semantic priority pipeline for SemanticStream.

This service is the heart of the AI processing pipeline. It orchestrates
the YOLO engine, frame utilities, and QP utilities to produce:

  1. A per-frame :class:`FrameAnalysisResult` containing:
     - YOLO detections (persons, animals, vehicles, objects)
     - Text-region coverage fraction
     - Motion coverage fraction and flow field
     - Priority map + QP matrix
     - SPQI, SSIM, PSNR scores (when a reference frame is available)

  2. A :class:`VideoAnalysisResult` — aggregate statistics and per-frame
     records suitable for persisting to the database via CRUD.

Phase 10 — Priority Classification System:
  - PRIORITY_MAP: 40+ COCO classes mapped into priority tiers 1 through 5.
  - PRIORITY_COLORS_BGR / PRIORITY_COLORS_HEX: Canonical color palettes.
  - assign_priority(class_name): Standardized priority resolver function.
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
    compute_regional_ssim,
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


# ── Canonical Priority Classification (Phase 10) ─────────────────────────────

PRIORITY_MAP = {
    "person": 1, "face": 1,
    "cat": 2, "dog": 2, "bird": 2, "horse": 2, "cow": 2,
    "sheep": 2, "elephant": 2, "bear": 2, "zebra": 2, "giraffe": 2,
    "car": 3, "truck": 3, "bus": 3, "motorcycle": 3, "bicycle": 3,
    "traffic light": 3, "stop sign": 3, "laptop": 3, "cell phone": 3,
    "tv": 3, "book": 3,
    "chair": 4, "couch": 4, "bed": 4, "dining table": 4,
    "bottle": 4, "cup": 4, "bowl": 4, "backpack": 4,
}

PRIORITY_COLORS_BGR = {
    1: (80, 255, 0),    # Bright green — P1 humans/faces
    2: (255, 200, 0),   # Cyan — P2 animals
    3: (255, 140, 0),   # Orange — P3 vehicles/objects
    4: (255, 60, 0),    # Red-orange — P4 low priority
    5: (80, 80, 80),    # Dark gray — P5 background
}

PRIORITY_COLORS_HEX = {
    1: "#00FF50", 2: "#00C8FF", 3: "#008CFF", 4: "#003CFF", 5: "#505050"
}


def assign_priority(class_name: str) -> int:
    """Resolve COCO object class name to priority tier (1=highest, 5=background)."""
    return PRIORITY_MAP.get(str(class_name).lower().strip(), 5)


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
    p1_ssim: Optional[float] = None
    p5_ssim: Optional[float] = None

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
    avg_face_ssim: Optional[float] = None
    avg_bg_ssim: Optional[float] = None
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
    tasks as long as each *job* uses a unique ``job_id``. The per-job
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
            SPQI. If ``None``, those metrics are skipped.
        confidence_threshold:
            Override detection confidence threshold. Defaults to
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
            for d in detections:
                # Synchronize priority tier with assign_priority
                p = assign_priority(d.class_name)
                d.priority_tier = f"P{p}"
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

        # ── 6. Quality metrics ─────────────────────────────────────────
        # reference_frame here is the JPEG-compressed "distorted" signal that
        # simulates uniform-ABR output. frame_bgr is the original (reference).
        if reference_frame is not None and result.priority_map is not None:
            try:
                result.ssim_score = compute_ssim(frame_bgr, reference_frame)
                result.psnr_score = compute_psnr(frame_bgr, reference_frame)
                result.spqi_score = compute_spqi(
                    frame_bgr, reference_frame, result.priority_map
                )

                # Regional SSIM: P1 (faces/persons)
                person_dets = [d for d in detections if d.is_person or assign_priority(d.class_name) == 1]
                if person_dets:
                    p1_mask = np.zeros((h, w), dtype=bool)
                    for d in person_dets:
                        px1, py1, px2, py2 = d.x1, d.y1, d.x2, d.y2
                        p1_mask[max(0, py1):min(h, py2), max(0, px1):min(w, px2)] = True
                    if np.any(p1_mask):
                        s1 = compute_regional_ssim(frame_bgr, reference_frame, p1_mask)
                        if not np.isnan(s1):
                            result.p1_ssim = float(s1)

                # Regional SSIM: P5 (background regions with lowest priority)
                p5_mask = (result.priority_map <= settings.PRIORITY_P5 + 0.05)
                if np.any(p5_mask):
                    s5 = compute_regional_ssim(frame_bgr, reference_frame, p5_mask)
                    if not np.isnan(s5):
                        result.p5_ssim = float(s5)
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
        max_frames: int | None = None,
    ) -> VideoAnalysisResult:
        """Analyse an entire video file and return aggregate results."""
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

        # Auto-raise sample_rate to respect max_frames cap
        if max_frames is not None and max_frames > 0:
            min_rate = max(1, total_frames // max_frames)
            if min_rate > sample_rate:
                sample_rate = min_rate
                log.info(
                    "video_analysis_sample_rate_adjusted",
                    job_id=job_id,
                    new_rate=sample_rate,
                    reason=f"max_frames cap of {max_frames}",
                )

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
            max_frames=max_frames,
        )

        try:
            import cv2
            for frame_num, ts_ms, frame in extract_frames(
                video_path, sample_rate=sample_rate
            ):
                try:
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 85]
                    _, jpeg_buf = cv2.imencode(".jpg", frame, encode_params)
                    compressed_ref = cv2.imdecode(
                        np.frombuffer(jpeg_buf, dtype=np.uint8), cv2.IMREAD_COLOR
                    )
                except Exception:
                    compressed_ref = None

                fr = self.analyse_frame(
                    frame_bgr=frame,
                    frame_number=frame_num,
                    timestamp_ms=ts_ms,
                    job_id=job_id,
                    reference_frame=compressed_ref,
                    confidence_threshold=confidence_threshold,
                )
                frame_results.append(fr)
                analysed += 1

                if progress_callback is not None:
                    pct = min(99.0, analysed / expected_analysed * 100.0)
                    try:
                        progress_callback(pct)
                    except Exception:
                        pass

                if max_frames is not None and analysed >= max_frames:
                    log.info("video_analysis_capped", job_id=job_id, frames=analysed)
                    break

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

        if progress_callback is not None:
            try:
                progress_callback(100.0)
            except Exception:
                pass

        elapsed_s = time.perf_counter() - t_start

        # Aggregate metrics
        spqi_vals = [r.spqi_score for r in frame_results if r.spqi_score is not None]
        ssim_vals = [r.ssim_score for r in frame_results if r.ssim_score is not None]
        psnr_vals = [r.psnr_score for r in frame_results if r.psnr_score is not None]
        face_vals = [r.p1_ssim for r in frame_results if r.p1_ssim is not None]
        bg_vals = [r.p5_ssim for r in frame_results if r.p5_ssim is not None]

        result = VideoAnalysisResult(
            job_id=job_id,
            video_id=video_id,
            total_frames_analysed=analysed,
            frame_results=frame_results,
            avg_spqi=float(np.mean(spqi_vals)) if spqi_vals else None,
            avg_ssim=float(np.mean(ssim_vals)) if ssim_vals else None,
            avg_psnr=float(np.mean(psnr_vals)) if psnr_vals else None,
            avg_face_ssim=float(np.mean(face_vals)) if face_vals else None,
            avg_bg_ssim=float(np.mean(bg_vals)) if bg_vals else None,
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
        """Classify scene into dialogue, action, text_heavy, motion, or ambient."""
        has_person = any(d.is_person or assign_priority(d.class_name) == 1 for d in detections)
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
