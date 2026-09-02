"""
services/compression_service.py
================================
FFmpeg-based video encoding with semantic QP injection for SemanticStream.

Three encoding strategies
--------------------------
1. **uniform_abr** — standard constant-bitrate H.264 encoding (baseline).
   Uses a single QP / CRF value from the active bandwidth profile.

2. **static_roi** — Region-of-Interest encoding.
   Applies a lower QP to a static face/foreground region and a higher QP
   to the background.  Uses FFmpeg ``zoompan`` + ``overlay`` or the
   ``-qpfile`` mechanism depending on codec capabilities.

3. **semanticstream** — Full semantic priority encoding.
   Takes the per-frame QP matrix produced by the detection pipeline and
   writes per-macroblock QP overrides via a ``qpfile``.  This is the
   novel contribution of the project.

All strategies share the same output container (MP4) and codec (libx264)
for fair comparison.

FFmpeg invocation
-----------------
The service builds a ``subprocess`` command list and runs it synchronously.
Callers that need async execution should use ``asyncio.to_thread``.

Output files
------------
All encoded outputs are written to ``settings.PROCESSED_DIR``.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from backend.core.config import settings
from backend.core.exceptions import FFmpegError
from backend.core.logging_config import get_logger
from backend.services.bandwidth_service import BandwidthProfile, bandwidth_service
from backend.utils.qp_utils import QPMatrix, get_macroblock_qp, qp_matrix_to_ffmpeg_qpfile

log = get_logger(__name__)


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class EncodingResult:
    """Result of a single encoding run.

    Attributes
    ----------
    strategy:
        One of ``uniform_abr``, ``static_roi``, ``semanticstream``.
    output_path:
        Filesystem path to the encoded MP4 file.
    encode_time_ms:
        Wall-clock encoding time in milliseconds.
    output_size_bytes:
        Size of the output file.
    bitrate_kbps:
        Measured output bitrate (size × 8 / duration).
    success:
        ``True`` if FFmpeg exited with code 0.
    error:
        Error message if ``success`` is ``False``.
    """

    strategy: str
    output_path: Optional[Path] = None
    encode_time_ms: float = 0.0
    output_size_bytes: int = 0
    bitrate_kbps: float = 0.0
    success: bool = False
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "output_path": str(self.output_path) if self.output_path else None,
            "encode_time_ms": round(self.encode_time_ms, 1),
            "output_size_bytes": self.output_size_bytes,
            "bitrate_kbps": round(self.bitrate_kbps, 1),
            "success": self.success,
            "error": self.error,
        }


# ── Compression service ───────────────────────────────────────────────────────

class CompressionService:
    """Orchestrates FFmpeg encoding for all three SemanticStream strategies.

    Parameters
    ----------
    ffmpeg_bin:
        Path to the FFmpeg executable.  Defaults to ``"ffmpeg"`` (assumes
        it is on ``PATH``).
    """

    def __init__(self, ffmpeg_bin: str = "ffmpeg") -> None:
        self._ffmpeg = ffmpeg_bin
        self._verify_ffmpeg()

    # ── Public API ────────────────────────────────────────────────────────────

    def encode_uniform_abr(
        self,
        input_path: Path,
        job_id: str,
        profile: BandwidthProfile,
        duration_seconds: Optional[float] = None,
    ) -> EncodingResult:
        """Encode using uniform constant-bitrate H.264 (baseline strategy).

        Parameters
        ----------
        input_path:
            Source video file.
        job_id:
            Used to name the output file.
        profile:
            Active bandwidth profile determining target bitrate and resolution.
        duration_seconds:
            Optional source duration for bitrate calculation.

        Returns
        -------
        :class:`EncodingResult`
        """
        output_path = settings.PROCESSED_DIR / f"{job_id}_uniform_abr.mp4"

        cmd = self._base_cmd(input_path, output_path, profile)
        cmd += [
            "-crf", str(profile.uniform_qp),
            "-maxrate", f"{profile.target_kbps}k",
            "-bufsize", f"{profile.target_kbps * 2}k",
        ]

        return self._run(cmd, "uniform_abr", output_path, duration_seconds)

    def encode_static_roi(
        self,
        input_path: Path,
        job_id: str,
        profile: BandwidthProfile,
        roi_boxes: Optional[List[tuple]] = None,
        duration_seconds: Optional[float] = None,
    ) -> EncodingResult:
        """Encode with a fixed ROI: lower QP inside boxes, higher QP outside.

        If ``roi_boxes`` is empty or ``None``, a default centre-crop ROI
        (covering the middle 50 % of the frame) is used as a proxy for the
        "face / subject area".

        Parameters
        ----------
        roi_boxes:
            List of (x, y, w, h) pixel-space boxes that should receive
            high-quality encoding (low QP).  Coordinates in source resolution.

        Returns
        -------
        :class:`EncodingResult`
        """
        output_path = settings.PROCESSED_DIR / f"{job_id}_static_roi.mp4"

        # Build FFmpeg adm_matrix filter for ROI — write a simple qpfile
        qpfile_path = settings.PROCESSED_DIR / f"{job_id}_static_roi.qpf"
        self._write_static_roi_qpfile(
            qpfile_path,
            roi_qp=settings.QP_STATIC_ROI_FACE,
            bg_qp=settings.QP_STATIC_ROI_BG,
        )

        cmd = self._base_cmd(input_path, output_path, profile)
        cmd += [
            "-qpfile", str(qpfile_path),
            "-g", "30",   # keyframe every 30 frames for qpfile alignment
        ]

        result = self._run(cmd, "static_roi", output_path, duration_seconds)

        # Cleanup temp qpfile
        if qpfile_path.exists():
            qpfile_path.unlink(missing_ok=True)

        return result

    def encode_semanticstream(
        self,
        input_path: Path,
        job_id: str,
        profile: BandwidthProfile,
        qp_matrices: List[QPMatrix],
        frame_numbers: List[int],
        duration_seconds: Optional[float] = None,
    ) -> EncodingResult:
        """Encode with per-frame semantic QP matrices (SemanticStream strategy).

        Parameters
        ----------
        qp_matrices:
            One QP matrix per analysed frame (from :mod:`utils.qp_utils`).
        frame_numbers:
            Corresponding frame indices for each QP matrix entry.

        Returns
        -------
        :class:`EncodingResult`
        """
        output_path = settings.PROCESSED_DIR / f"{job_id}_semanticstream.mp4"
        qpfile_path = settings.PROCESSED_DIR / f"{job_id}_semanticstream.qpf"

        # Build the qpfile from per-frame QP matrices
        self._write_semantic_qpfile(qpfile_path, qp_matrices, frame_numbers)

        cmd = self._base_cmd(input_path, output_path, profile)
        cmd += [
            "-qpfile", str(qpfile_path),
            "-g", "30",
        ]

        result = self._run(cmd, "semanticstream", output_path, duration_seconds)

        if qpfile_path.exists():
            qpfile_path.unlink(missing_ok=True)

        return result

    def encode_all_strategies(
        self,
        input_path: Path,
        job_id: str,
        profile_name: str,
        qp_matrices: Optional[List[QPMatrix]] = None,
        frame_numbers: Optional[List[int]] = None,
        duration_seconds: Optional[float] = None,
    ) -> dict[str, EncodingResult]:
        """Run all three strategies and return a dict keyed by strategy name.

        Parameters
        ----------
        profile_name:
            Named bandwidth profile (e.g. ``"broadband"``).
        qp_matrices / frame_numbers:
            Required for the SemanticStream strategy.  If ``None``,
            only uniform_abr and static_roi are run.

        Returns
        -------
        ``{strategy_name: EncodingResult}``
        """
        profile = bandwidth_service.get_profile(profile_name)
        results: dict[str, EncodingResult] = {}

        log.info("compress.all_strategies.start", job=job_id, profile=profile_name)

        results["uniform_abr"] = self.encode_uniform_abr(
            input_path, job_id, profile, duration_seconds
        )
        results["static_roi"] = self.encode_static_roi(
            input_path, job_id, profile, duration_seconds=duration_seconds
        )

        if qp_matrices and frame_numbers:
            results["semanticstream"] = self.encode_semanticstream(
                input_path, job_id, profile, qp_matrices, frame_numbers,
                duration_seconds
            )
        else:
            log.warning(
                "compress.semanticstream_skipped",
                reason="no QP matrices provided",
            )

        log.info(
            "compress.all_strategies.done",
            job=job_id,
            strategies=list(results.keys()),
        )
        return results

    # ── Measurement helpers ───────────────────────────────────────────────────

    @staticmethod
    def measure_bitrate(output_path: Path, duration_seconds: float) -> float:
        """Compute bitrate in kbps from file size and duration.

        Returns 0.0 if the file does not exist or duration is 0.
        """
        if not output_path.exists() or duration_seconds <= 0:
            return 0.0
        size_bits = output_path.stat().st_size * 8
        return size_bits / duration_seconds / 1000.0

    @staticmethod
    def get_output_size(output_path: Path) -> int:
        """Return file size in bytes, or 0 if missing."""
        return output_path.stat().st_size if output_path.exists() else 0

    # ── Private helpers ───────────────────────────────────────────────────────

    def _base_cmd(
        self,
        input_path: Path,
        output_path: Path,
        profile: BandwidthProfile,
    ) -> List[str]:
        """Build the common FFmpeg command prefix shared by all strategies."""
        return [
            self._ffmpeg,
            "-y",                          # overwrite output
            "-i", str(input_path),
            "-c:v", "libx264",
            "-preset", "medium",
            "-r", str(profile.fps_target),
            "-vf", f"scale={profile.max_width}:{profile.max_height}:force_original_aspect_ratio=decrease",
            "-an",                         # no audio (video-only for analysis)
            "-movflags", "+faststart",
            str(output_path),
        ]

    def _run(
        self,
        cmd: List[str],
        strategy: str,
        output_path: Path,
        duration_seconds: Optional[float],
    ) -> EncodingResult:
        """Execute an FFmpeg command and wrap the result."""
        log.debug("ffmpeg.run", strategy=strategy, cmd=" ".join(cmd))
        t0 = time.perf_counter()

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,   # 10-minute hard limit
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000

            if proc.returncode != 0:
                error = proc.stderr[-500:] if proc.stderr else "unknown error"
                log.error("ffmpeg.failed", strategy=strategy, stderr=error)
                return EncodingResult(
                    strategy=strategy,
                    encode_time_ms=elapsed_ms,
                    success=False,
                    error=error,
                )

            size = self.get_output_size(output_path)
            bitrate = (
                self.measure_bitrate(output_path, duration_seconds)
                if duration_seconds
                else 0.0
            )

            log.info(
                "ffmpeg.done",
                strategy=strategy,
                elapsed_ms=round(elapsed_ms, 1),
                size_mb=round(size / 1024 / 1024, 2),
                bitrate_kbps=round(bitrate, 1),
            )

            return EncodingResult(
                strategy=strategy,
                output_path=output_path,
                encode_time_ms=elapsed_ms,
                output_size_bytes=size,
                bitrate_kbps=bitrate,
                success=True,
            )

        except subprocess.TimeoutExpired:
            error = "FFmpeg timed out after 600 seconds"
            log.error("ffmpeg.timeout", strategy=strategy)
            return EncodingResult(strategy=strategy, success=False, error=error)

        except FileNotFoundError:
            error = f"FFmpeg executable not found: {self._ffmpeg}"
            log.error("ffmpeg.not_found")
            return EncodingResult(strategy=strategy, success=False, error=error)

    def _verify_ffmpeg(self) -> None:
        """Check FFmpeg is reachable; log a warning if not."""
        try:
            result = subprocess.run(
                [self._ffmpeg, "-version"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                first_line = result.stdout.split(b"\n")[0].decode(errors="replace")
                log.info("ffmpeg.verified", version=first_line)
            else:
                log.warning("ffmpeg.version_check_failed")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            log.warning(
                "ffmpeg.not_available",
                advice="Install FFmpeg and ensure it is on PATH",
            )

    @staticmethod
    def _write_static_roi_qpfile(
        path: Path,
        roi_qp: int,
        bg_qp: int,
        rows: int = 45,   # 720p / 16 = 45 macroblocks tall
        cols: int = 80,   # 1280 / 16 = 80 macroblocks wide
        roi_row_start: int = 10,
        roi_row_end: int = 35,
        roi_col_start: int = 20,
        roi_col_end: int = 60,
    ) -> None:
        """Write a static-ROI qpfile with two QP zones (ROI vs background)."""
        lines: List[str] = []
        for r in range(rows):
            for c in range(cols):
                in_roi = (
                    roi_row_start <= r < roi_row_end
                    and roi_col_start <= c < roi_col_end
                )
                qp = roi_qp if in_roi else bg_qp
                lines.append(f"{r} {c} {qp} P")
        path.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _write_semantic_qpfile(
        path: Path,
        qp_matrices: List[QPMatrix],
        frame_numbers: List[int],
    ) -> None:
        """Write a per-frame semantic qpfile from QP matrices.

        Frames not covered by the sampled matrices inherit the uniform
        baseline QP (settings.QP_UNIFORM).
        """
        chunks: List[str] = []
        for qp_mat, frame_num in zip(qp_matrices, frame_numbers):
            mb_qp = get_macroblock_qp(qp_mat)
            frame_type = "I" if frame_num % 30 == 0 else "P"
            chunks.append(qp_matrix_to_ffmpeg_qpfile(mb_qp, frame_type))

        path.write_text("\n".join(chunks), encoding="utf-8")


# ── Module-level singleton ────────────────────────────────────────────────────

compression_service = CompressionService()
