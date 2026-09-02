"""
services/scene_service.py
==========================
Scene-cut detection and scene classification for SemanticStream.

Responsibilities
----------------
* Detect hard scene cuts using frame-to-frame histogram distance
  (Bhattacharyya distance > ``settings.SCENE_CUT_THRESHOLD``).
* Classify each frame into one of five semantic scene types:
    - ``dialogue``   — person(s) present, low motion, possible text
    - ``action``     — high motion with persons
    - ``motion``     — high motion without persons
    - ``text_heavy`` — large text-overlay area
    - ``ambient``    — background / B-roll / static shot
* Apply a *freshness* guard: the first ``settings.SCENE_FRESH_FRAMES``
  frames after a cut are exempt from reclassification so the scene label
  stabilises.
* Persist detected transitions to the database via
  ``crud.bulk_create_scene_events``.

The service is designed to be called frame-by-frame during the main
analysis loop via :meth:`SceneService.process_frame`, which maintains
all internal state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from backend.core.config import settings
from backend.core.logging_config import get_logger
from backend.utils.frame_utils import (
    compute_histogram,
    histogram_distance,
    detect_text_regions,
    high_motion_mask,
    compute_optical_flow,
    to_grayscale,
    mask_area_fraction,
)

log = get_logger(__name__)


# ── Scene type constants ──────────────────────────────────────────────────────

class SceneType:
    DIALOGUE   = "dialogue"
    ACTION     = "action"
    MOTION     = "motion"
    TEXT_HEAVY = "text_heavy"
    AMBIENT    = "ambient"

ALL_SCENE_TYPES = [
    SceneType.DIALOGUE,
    SceneType.ACTION,
    SceneType.MOTION,
    SceneType.TEXT_HEAVY,
    SceneType.AMBIENT,
]


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class SceneFrameResult:
    """Scene analysis result for a single frame."""

    frame_number: int
    timestamp_ms: float
    scene_type: str
    is_scene_cut: bool
    histogram_distance: Optional[float] = None
    text_area_frac: float = 0.0
    motion_area_frac: float = 0.0
    has_person: bool = False


@dataclass
class SceneTransition:
    """A detected scene cut / transition event."""

    frame_number: int
    timestamp_ms: float
    previous_scene: str
    new_scene: str
    histogram_score: float


@dataclass
class SceneJobResult:
    """Aggregate scene analysis result for a full video job."""

    job_id: str
    transitions: List[SceneTransition] = field(default_factory=list)
    scene_distribution: Dict[str, int] = field(default_factory=dict)
    total_frames: int = 0
    dominant_scene: Optional[str] = None


# ── Per-job state ─────────────────────────────────────────────────────────────

@dataclass
class _JobState:
    """Internal per-job state maintained by SceneService."""

    prev_histogram: Optional[np.ndarray] = None
    prev_gray: Optional[np.ndarray] = None
    current_scene: str = SceneType.AMBIENT
    frames_since_cut: int = 999   # starts high so first frame is classifiable
    transitions: List[SceneTransition] = field(default_factory=list)
    scene_counts: Dict[str, int] = field(default_factory=dict)
    frame_count: int = 0


# ── Scene service ─────────────────────────────────────────────────────────────

class SceneService:
    """Frame-by-frame scene detection and classification.

    Usage
    -----
    .. code-block:: python

        svc = SceneService()
        for frame_num, ts_ms, frame in extract_frames(video_path):
            result = svc.process_frame(
                frame_bgr=frame,
                frame_number=frame_num,
                timestamp_ms=ts_ms,
                job_id=job_id,
                detections=detections,   # from DetectionService
            )
        job_result = svc.finalise_job(job_id)
        svc.clear_job(job_id)
    """

    def __init__(self) -> None:
        self._jobs: Dict[str, _JobState] = {}

    # ── Frame-level processing ────────────────────────────────────────────────

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        frame_number: int,
        timestamp_ms: float,
        job_id: str,
        detections: Optional[list] = None,
    ) -> SceneFrameResult:
        """Analyse a single frame for scene cuts and classify its scene type.

        Parameters
        ----------
        frame_bgr:
            Current frame as BGR uint8 numpy array.
        frame_number:
            Sequential frame index.
        timestamp_ms:
            Frame timestamp in milliseconds.
        job_id:
            Unique analysis job identifier (for state isolation).
        detections:
            Optional list of :class:`~backend.models.yolo_engine.Detection`
            objects from the detection service.  Used for scene classification.

        Returns
        -------
        :class:`SceneFrameResult`
        """
        state = self._get_or_create(job_id)
        state.frame_count += 1

        # ── 1. Histogram computation ──────────────────────────────────────
        curr_hist = compute_histogram(frame_bgr)

        # ── 2. Scene-cut detection ────────────────────────────────────────
        hist_dist: Optional[float] = None
        is_cut = False

        if state.prev_histogram is not None:
            hist_dist = histogram_distance(state.prev_histogram, curr_hist)
            if hist_dist > settings.SCENE_CUT_THRESHOLD:
                is_cut = True
                state.frames_since_cut = 0
                log.debug(
                    "scene.cut_detected",
                    job=job_id,
                    frame=frame_number,
                    dist=round(hist_dist, 3),
                )
            else:
                state.frames_since_cut += 1
        else:
            state.frames_since_cut = settings.SCENE_FRESH_FRAMES + 1

        state.prev_histogram = curr_hist

        # ── 3. Signal extraction ──────────────────────────────────────────
        text_frac = 0.0
        motion_frac = 0.0

        try:
            text_mask = detect_text_regions(frame_bgr)
            text_frac = mask_area_fraction(text_mask)
        except Exception:
            pass

        curr_gray = to_grayscale(frame_bgr)
        if state.prev_gray is not None and state.prev_gray.shape == curr_gray.shape:
            try:
                flow = compute_optical_flow(state.prev_gray, curr_gray)
                motion_mask = high_motion_mask(flow)
                motion_frac = mask_area_fraction(motion_mask.astype(np.uint8) * 255)
            except Exception:
                pass
        state.prev_gray = curr_gray

        has_person = any(d.is_person for d in (detections or []))

        # ── 4. Scene classification ───────────────────────────────────────
        # Freshness guard: don't reclassify immediately after a cut
        if state.frames_since_cut <= settings.SCENE_FRESH_FRAMES and not is_cut:
            new_scene = state.current_scene
        else:
            new_scene = self._classify(
                has_person=has_person,
                text_frac=text_frac,
                motion_frac=motion_frac,
            )

        # ── 5. Record transition ──────────────────────────────────────────
        if (is_cut or new_scene != state.current_scene) and state.frame_count > 1:
            transition = SceneTransition(
                frame_number=frame_number,
                timestamp_ms=timestamp_ms,
                previous_scene=state.current_scene,
                new_scene=new_scene,
                histogram_score=hist_dist or 0.0,
            )
            state.transitions.append(transition)
            log.info(
                "scene.transition",
                job=job_id,
                frame=frame_number,
                prev=state.current_scene,
                new=new_scene,
            )

        state.current_scene = new_scene
        state.scene_counts[new_scene] = state.scene_counts.get(new_scene, 0) + 1

        return SceneFrameResult(
            frame_number=frame_number,
            timestamp_ms=timestamp_ms,
            scene_type=new_scene,
            is_scene_cut=is_cut,
            histogram_distance=hist_dist,
            text_area_frac=round(text_frac, 4),
            motion_area_frac=round(motion_frac, 4),
            has_person=has_person,
        )

    # ── Job finalisation ──────────────────────────────────────────────────────

    def finalise_job(self, job_id: str) -> SceneJobResult:
        """Compute aggregate scene statistics for a completed job.

        Returns
        -------
        :class:`SceneJobResult` with transitions list, distribution, and
        dominant scene type.
        """
        state = self._jobs.get(job_id)
        if state is None:
            return SceneJobResult(job_id=job_id)

        dominant = (
            max(state.scene_counts, key=lambda k: state.scene_counts[k])
            if state.scene_counts else SceneType.AMBIENT
        )

        return SceneJobResult(
            job_id=job_id,
            transitions=list(state.transitions),
            scene_distribution=dict(state.scene_counts),
            total_frames=state.frame_count,
            dominant_scene=dominant,
        )

    async def persist_transitions(
        self,
        job_id: str,
        db,
    ) -> None:
        """Write detected scene transitions to the database.

        Parameters
        ----------
        job_id:
            UUID of the parent analysis job.
        db:
            Active ``AsyncSession``.
        """
        state = self._jobs.get(job_id)
        if state is None or not state.transitions:
            return

        from backend.database import crud

        events = [
            {
                "job_id": job_id,
                "frame_number": t.frame_number,
                "timestamp_ms": t.timestamp_ms,
                "previous_scene_type": t.previous_scene,
                "new_scene_type": t.new_scene,
                "histogram_score": t.histogram_score,
            }
            for t in state.transitions
        ]
        await crud.bulk_create_scene_events(db, events)
        log.info(
            "scene.transitions_persisted",
            job=job_id,
            count=len(events),
        )

    def clear_job(self, job_id: str) -> None:
        """Release all per-job state (call after job completes)."""
        self._jobs.pop(job_id, None)

    # ── Scene classifier ──────────────────────────────────────────────────────

    @staticmethod
    def _classify(
        has_person: bool,
        text_frac: float,
        motion_frac: float,
    ) -> str:
        """Map signal fractions to a scene-type label.

        Decision tree
        -------------
        text_frac ≥ TEXT_AREA_THRESHOLD            → text_heavy
        has_person AND motion_frac ≥ motion_thresh  → action
        has_person AND motion_frac < motion_thresh  → dialogue
        motion_frac ≥ motion_thresh (no person)     → motion
        else                                        → ambient
        """
        motion_thresh = settings.MOTION_DOMINANT_THRESHOLD / 100.0  # convert % → frac

        if text_frac >= settings.TEXT_AREA_THRESHOLD:
            return SceneType.TEXT_HEAVY
        if has_person and motion_frac >= motion_thresh:
            return SceneType.ACTION
        if has_person:
            return SceneType.DIALOGUE
        if motion_frac >= motion_thresh:
            return SceneType.MOTION
        return SceneType.AMBIENT

    # ── Utility helpers ───────────────────────────────────────────────────────

    def current_scene(self, job_id: str) -> str:
        """Return the current scene label for a running job."""
        state = self._jobs.get(job_id)
        return state.current_scene if state else SceneType.AMBIENT

    def transition_count(self, job_id: str) -> int:
        """Number of scene transitions recorded so far."""
        state = self._jobs.get(job_id)
        return len(state.transitions) if state else 0

    def scene_distribution(self, job_id: str) -> Dict[str, int]:
        """Per-scene-type frame count for a running job."""
        state = self._jobs.get(job_id)
        return dict(state.scene_counts) if state else {}

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_or_create(self, job_id: str) -> _JobState:
        if job_id not in self._jobs:
            self._jobs[job_id] = _JobState()
        return self._jobs[job_id]


# ── Module-level singleton ────────────────────────────────────────────────────

scene_service = SceneService()
