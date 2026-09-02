"""
services/streaming_service.py
==============================
HLS playlist delivery and annotated frame extraction for SemanticStream.

Responsibilities
----------------
* ``get_playlist_path(video_id)`` — resolve and return the HLS master playlist
  path for a processed video, falling back to the raw upload path if HLS
  segments have not yet been generated.
* ``get_annotated_frame(video_id, frame_number, overlay)`` — extract a single
  frame from the stored video, run the detection pipeline on it, and return
  a base64-encoded PNG with the requested overlay (heatmap / original /
  compressed / sidebyside).

Design notes
------------
* Frame extraction delegates to ``utils.frame_utils.extract_single_frame``.
* Detection delegates to the module-level ``detection_service`` singleton.
* All heavy computation runs in a thread pool via ``asyncio.to_thread``.
* No HLS transcoding is performed here — that is an offline process.  The
  service simply looks for a pre-generated ``master.m3u8`` file.
"""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any

from backend.core.exceptions import VideoNotFoundError, VideoProcessingError
from backend.core.logging_config import get_logger
from backend.database import crud
from backend.utils.file_utils import frame_path, hls_dir, upload_path

log = get_logger(__name__)


class StreamingService:
    """Delivers HLS playlists and annotated frames for a video.

    Parameters
    ----------
    db:
        An ``AsyncSession`` for DB access.
    """

    def __init__(self, db) -> None:
        self._db = db

    # ── HLS Playlist ──────────────────────────────────────────────────────────

    async def get_playlist_path(self, video_id: str) -> str:
        """Return the filesystem path to the HLS master playlist.

        Checks for a pre-generated ``master.m3u8`` in the HLS directory.
        If not found, falls back to the raw upload path so the player can
        still serve *something* (direct MP4 via ``FileResponse``).

        Parameters
        ----------
        video_id:
            UUID of the video.

        Returns
        -------
        str
            Absolute path to the playlist or raw video file.

        Raises
        ------
        VideoNotFoundError
            If the video record does not exist in the database.
        VideoProcessingError
            If neither the HLS playlist nor the upload file can be found on disk.
        """
        video = await crud.get_video(self._db, video_id)
        if video is None:
            raise VideoNotFoundError(
                f"Video '{video_id}' not found.",
                detail="No database record for this video_id.",
            )

        # Prefer HLS playlist
        playlist = hls_dir(video_id) / "master.m3u8"
        if playlist.exists():
            log.info("streaming.hls_playlist_found", video_id=video_id, path=str(playlist))
            return str(playlist)

        # Fall back to raw upload
        raw_path = Path(video.filepath)
        if raw_path.exists():
            log.info("streaming.raw_fallback", video_id=video_id, path=str(raw_path))
            return str(raw_path)

        raise VideoProcessingError(
            f"No playable file found for video '{video_id}'.",
            detail=f"HLS playlist: {playlist} — Raw: {raw_path}",
        )

    # ── Annotated Frame ───────────────────────────────────────────────────────

    async def get_annotated_frame(
        self,
        video_id: str,
        frame_number: int,
        overlay: str = "heatmap",
    ) -> dict[str, Any]:
        """Extract and annotate a single video frame.

        Parameters
        ----------
        video_id:
            UUID of the source video.
        frame_number:
            Zero-indexed frame number to retrieve.
        overlay:
            One of ``heatmap`` | ``original`` | ``compressed`` | ``sidebyside``.

        Returns
        -------
        Dict with ``frame_base64``, ``priority_map_base64``, ``detections``,
        ``scene_type``, ``dominant_tier``, and ``overlay`` keys.

        Raises
        ------
        VideoNotFoundError:
            If the video record is absent.
        VideoProcessingError:
            If frame extraction fails.
        """
        video = await crud.get_video(self._db, video_id)
        if video is None:
            raise VideoNotFoundError(
                f"Video '{video_id}' not found.",
                detail="No database record for this video_id.",
            )

        video_path = Path(video.filepath)
        if not video_path.exists():
            raise VideoProcessingError(
                f"Video file not found on disk.",
                detail=str(video_path),
            )

        # Run blocking frame extraction + detection in thread pool
        result = await asyncio.to_thread(
            self._extract_and_annotate,
            video_path=video_path,
            video_id=video_id,
            frame_number=frame_number,
            overlay=overlay,
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _extract_and_annotate(
        video_path: Path,
        video_id: str,
        frame_number: int,
        overlay: str,
    ) -> dict[str, Any]:
        """Blocking implementation of frame extraction + detection.

        Runs inside ``asyncio.to_thread`` so it never blocks the event loop.
        """
        import cv2

        from backend.services.detection_service import detection_service

        # ── 1. Try cached frame first ──────────────────────────────────────
        cached = frame_path(video_id, frame_number)
        if cached.exists():
            frame_bgr = cv2.imread(str(cached))
        else:
            frame_bgr = StreamingService._read_frame_from_video(video_path, frame_number)

        if frame_bgr is None:
            raise VideoProcessingError(
                f"Frame {frame_number} could not be extracted.",
                detail=str(video_path),
            )

        # ── 2. Run detection pipeline ──────────────────────────────────────
        result = detection_service.analyse_frame(
            frame_bgr=frame_bgr,
            frame_number=frame_number,
            timestamp_ms=0.0,
            job_id=f"frame_{video_id}",
        )

        # ── 3. Encode original frame ───────────────────────────────────────
        _, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 92])
        frame_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

        # ── 4. Encode priority heatmap ─────────────────────────────────────
        pmap_b64 = ""
        if result.priority_map is not None:
            try:
                import numpy as np
                norm = (result.priority_map * 255).clip(0, 255).astype(np.uint8)
                heatmap = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
                if overlay in ("sidebyside",):
                    # Side-by-side: concatenate original and heatmap
                    heatmap_resized = cv2.resize(heatmap, (frame_bgr.shape[1], frame_bgr.shape[0]))
                    combined = cv2.hconcat([frame_bgr, heatmap_resized])
                    _, cbuf = cv2.imencode(".jpg", combined)
                    frame_b64 = base64.b64encode(cbuf.tobytes()).decode("utf-8")
                _, pbuf = cv2.imencode(".png", heatmap)
                pmap_b64 = base64.b64encode(pbuf.tobytes()).decode("utf-8")
            except Exception as exc:
                log.warning("streaming.heatmap_encode_failed", error=str(exc))

        # ── 5. Build detection list ────────────────────────────────────────
        detections = [
            {
                "class_id": d.class_id,
                "class_name": d.class_name,
                "confidence": round(d.confidence, 3),
                "bbox": list(d.bbox),
                "is_person": d.is_person,
            }
            for d in result.detections
        ]

        dominant_tier = "P5"
        if result.priority_stats:
            # Highest-weighted tier is dominant
            stats = result.priority_stats
            tier_order = ["p1_frac", "p2_frac", "p3_frac", "p4_frac", "p5_frac"]
            tier_labels = ["P1", "P2", "P3", "P4", "P5"]
            for key, label in zip(tier_order, tier_labels):
                if stats.get(key, 0.0) > 0.01:
                    dominant_tier = label
                    break

        return {
            "frame_base64": frame_b64,
            "priority_map_base64": pmap_b64,
            "detections": detections,
            "scene_type": result.scene_type or "ambient",
            "dominant_tier": dominant_tier,
            "overlay": overlay,
        }

    @staticmethod
    def _read_frame_from_video(video_path: Path, frame_number: int):
        """Read a specific frame from a video file using OpenCV.

        Parameters
        ----------
        video_path:
            Path to the video file.
        frame_number:
            Zero-indexed frame number.

        Returns
        -------
        numpy.ndarray or None
            BGR frame array, or ``None`` if the frame cannot be read.
        """
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None

        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, float(frame_number))
            ret, frame = cap.read()
            return frame if ret else None
        finally:
            cap.release()
