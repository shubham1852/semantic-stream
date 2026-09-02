"""
services/bandwidth_service.py
==============================
Bandwidth profile management and BOLA-inspired adaptive bitrate selection.

Five named profiles
-------------------
Profile          Target bitrate    Typical scenario
────────────────────────────────────────────────────────────────────────────
mobile_lte       800 kbps          4G LTE constrained link
mobile_wifi      2 000 kbps        Wi-Fi / 5G mid-tier
broadband        5 000 kbps        Home broadband (720p/1080p)
high_quality    12 000 kbps        Office / campus network (1080p+)
ultra           25 000 kbps        4K fibre / local network

Each profile exposes:
  - A per-tier bitrate allocation (P1–P5) based on the configured budget
    fractions in ``settings``
  - A FFmpeg ``-b:v`` target and CRF/QP operating point
  - BOLA buffer-health thresholds for emergency degradation

Adaptive selection
------------------
The :meth:`BandwidthService.select_profile` method implements a simplified
BOLA-style policy:

  1. Measure the rolling-average download bandwidth (last N samples).
  2. Scale by ``settings.BANDWIDTH_SAFETY_MARGIN`` (default 0.85).
  3. Pick the highest profile whose target bitrate fits under the budget.
  4. If the buffer is below the emergency threshold, drop one profile tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional
from collections import deque

from backend.core.config import settings
from backend.core.exceptions import BandwidthProfileError
from backend.core.logging_config import get_logger

log = get_logger(__name__)


# ── Profile dataclass ─────────────────────────────────────────────────────────

@dataclass
class BandwidthProfile:
    """A named bandwidth operating point for SemanticStream encoding.

    Attributes
    ----------
    name:
        Unique identifier (e.g. ``"mobile_lte"``).
    target_kbps:
        Total target video bitrate in kbps.
    label:
        Human-readable label for the UI.
    description:
        Short explanation for the API response.
    max_width / max_height:
        Maximum encoded resolution for this profile.
    fps_target:
        Target output frame rate.
    uniform_qp:
        QP value to use for the uniform-ABR baseline experiment strategy.
    tier_kbps:
        Per-tier bitrate allocation in kbps (P1–P5), derived from budget
        fractions in ``settings``.
    emergency_qp:
        Fallback QP used when buffer drops below emergency threshold.
    """

    name: str
    target_kbps: int
    label: str
    description: str
    max_width: int
    max_height: int
    fps_target: int
    uniform_qp: int
    tier_kbps: Dict[str, int] = field(default_factory=dict)
    emergency_qp: int = 40

    def __post_init__(self) -> None:
        if not self.tier_kbps:
            self.tier_kbps = _allocate_tier_bitrates(self.target_kbps)

    def to_dict(self) -> dict:
        """Return a JSON-serialisable representation."""
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "target_kbps": self.target_kbps,
            "max_resolution": f"{self.max_width}x{self.max_height}",
            "fps_target": self.fps_target,
            "uniform_qp": self.uniform_qp,
            "tier_kbps": self.tier_kbps,
            "emergency_qp": self.emergency_qp,
        }


# ── Tier bitrate allocator ────────────────────────────────────────────────────

def _allocate_tier_bitrates(total_kbps: int) -> Dict[str, int]:
    """Split *total_kbps* across 5 tiers using settings budget fractions."""
    return {
        "P1": int(total_kbps * settings.BUDGET_P1),
        "P2": int(total_kbps * settings.BUDGET_P2),
        "P3": int(total_kbps * settings.BUDGET_P3),
        "P4": int(total_kbps * settings.BUDGET_P4),
        "P5": int(total_kbps * settings.BUDGET_P5),
    }


def _emergency_tier_bitrates(total_kbps: int) -> Dict[str, int]:
    """Emergency budget fractions — P5 aggressively reduced."""
    return {
        "P1": int(total_kbps * settings.EMERGENCY_BUDGET_P1),
        "P2": int(total_kbps * settings.EMERGENCY_BUDGET_P2),
        "P3": int(total_kbps * settings.EMERGENCY_BUDGET_P3),
        "P4": int(total_kbps * settings.EMERGENCY_BUDGET_P4),
        "P5": int(total_kbps * settings.EMERGENCY_BUDGET_P5),
    }


# ── Built-in profile catalogue ────────────────────────────────────────────────

_CATALOGUE: List[BandwidthProfile] = [
    BandwidthProfile(
        name="mobile_lte",
        target_kbps=800,
        label="Mobile LTE",
        description="Constrained 4G LTE link — 480p, aggressive background compression",
        max_width=854,
        max_height=480,
        fps_target=24,
        uniform_qp=34,
        emergency_qp=42,
    ),
    BandwidthProfile(
        name="mobile_wifi",
        target_kbps=2_000,
        label="Mobile Wi-Fi / 5G",
        description="Mid-tier wireless — 720p at 30 fps",
        max_width=1280,
        max_height=720,
        fps_target=30,
        uniform_qp=30,
        emergency_qp=38,
    ),
    BandwidthProfile(
        name="broadband",
        target_kbps=5_000,
        label="Home Broadband",
        description="Standard home broadband — 1080p at 30 fps",
        max_width=1920,
        max_height=1080,
        fps_target=30,
        uniform_qp=26,
        emergency_qp=34,
    ),
    BandwidthProfile(
        name="high_quality",
        target_kbps=12_000,
        label="High Quality",
        description="Office / campus network — 1080p at 60 fps",
        max_width=1920,
        max_height=1080,
        fps_target=60,
        uniform_qp=22,
        emergency_qp=30,
    ),
    BandwidthProfile(
        name="ultra",
        target_kbps=25_000,
        label="Ultra / 4K",
        description="Fibre / local network — 4K at 60 fps",
        max_width=3840,
        max_height=2160,
        fps_target=60,
        uniform_qp=18,
        emergency_qp=26,
    ),
]

# Index by name for O(1) lookup
_PROFILE_INDEX: Dict[str, BandwidthProfile] = {p.name: p for p in _CATALOGUE}

# Ordered by target_kbps ascending (used by adaptive selection)
_PROFILES_ASCENDING: List[BandwidthProfile] = sorted(
    _CATALOGUE, key=lambda p: p.target_kbps
)


# ── Buffer health state ───────────────────────────────────────────────────────

class BufferHealthState:
    """Sliding-window buffer health tracker for BOLA-style decisions.

    Parameters
    ----------
    window_size:
        Number of recent bandwidth samples to retain.
    """

    def __init__(self, window_size: int = settings.BW_WINDOW_SIZE) -> None:
        self._bw_samples: Deque[float] = deque(maxlen=window_size)
        self._buffer_seconds: float = settings.BUFFER_TARGET_SECONDS

    def add_bandwidth_sample(self, kbps: float) -> None:
        """Record a measured bandwidth sample (kbps)."""
        self._bw_samples.append(kbps)

    def update_buffer(self, buffer_seconds: float) -> None:
        """Update the current playback buffer level."""
        self._buffer_seconds = buffer_seconds

    @property
    def avg_bandwidth_kbps(self) -> Optional[float]:
        """Rolling average bandwidth, or ``None`` if no samples yet."""
        if not self._bw_samples:
            return None
        return sum(self._bw_samples) / len(self._bw_samples)

    @property
    def safe_bandwidth_kbps(self) -> Optional[float]:
        """Bandwidth budget after applying the safety margin."""
        avg = self.avg_bandwidth_kbps
        return avg * settings.BANDWIDTH_SAFETY_MARGIN if avg is not None else None

    @property
    def is_emergency(self) -> bool:
        """True when the buffer is below the emergency threshold."""
        return self._buffer_seconds < settings.BUFFER_EMERGENCY_SECONDS

    @property
    def is_low(self) -> bool:
        """True when the buffer is below the target threshold."""
        return self._buffer_seconds < settings.BUFFER_TARGET_SECONDS

    def to_dict(self) -> dict:
        return {
            "avg_bandwidth_kbps": self.avg_bandwidth_kbps,
            "safe_bandwidth_kbps": self.safe_bandwidth_kbps,
            "buffer_seconds": self._buffer_seconds,
            "is_emergency": self.is_emergency,
            "is_low": self.is_low,
        }


# ── Bandwidth service ─────────────────────────────────────────────────────────

class BandwidthService:
    """Manages bandwidth profiles and adaptive ABR selection.

    One instance per analysis session is sufficient.  The service is
    stateless for profile queries and maintains a :class:`BufferHealthState`
    per logical stream session via a ``session_id`` key.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, BufferHealthState] = {}

    # ── Profile catalogue ─────────────────────────────────────────────────────

    @staticmethod
    def list_profiles() -> List[dict]:
        """Return all profiles as JSON-serialisable dicts, ordered by bitrate."""
        return [p.to_dict() for p in _PROFILES_ASCENDING]

    @staticmethod
    def get_profile(name: str) -> BandwidthProfile:
        """Fetch a profile by name.

        Raises
        ------
        BandwidthProfileError
            If *name* is not in the catalogue.
        """
        profile = _PROFILE_INDEX.get(name)
        if profile is None:
            valid = list(_PROFILE_INDEX)
            raise BandwidthProfileError(
                f"Unknown bandwidth profile '{name}'. "
                f"Valid options: {valid}"
            )
        return profile

    @staticmethod
    def get_profile_names() -> List[str]:
        """Return list of valid profile name strings."""
        return [p.name for p in _PROFILES_ASCENDING]

    # ── Adaptive selection ────────────────────────────────────────────────────

    def select_profile(
        self,
        session_id: str,
        measured_kbps: Optional[float] = None,
        buffer_seconds: Optional[float] = None,
        force_name: Optional[str] = None,
    ) -> BandwidthProfile:
        """Choose the best profile for current network conditions.

        Parameters
        ----------
        session_id:
            Unique stream session identifier.
        measured_kbps:
            Latest bandwidth measurement to add to the rolling window.
        buffer_seconds:
            Current playback buffer level in seconds.
        force_name:
            If provided, skip adaptive logic and return this profile directly.

        Returns
        -------
        The selected :class:`BandwidthProfile`.
        """
        if force_name:
            return self.get_profile(force_name)

        state = self._get_or_create_session(session_id)

        if measured_kbps is not None:
            state.add_bandwidth_sample(measured_kbps)
        if buffer_seconds is not None:
            state.update_buffer(buffer_seconds)

        safe_bw = state.safe_bandwidth_kbps
        if safe_bw is None:
            # No measurements yet — use broadband as a safe default
            selected = _PROFILE_INDEX["broadband"]
            log.debug("bw.select.default", session=session_id, profile=selected.name)
            return selected

        # Pick highest profile that fits under the safe budget
        selected = _PROFILES_ASCENDING[0]  # floor = mobile_lte
        for profile in _PROFILES_ASCENDING:
            if profile.target_kbps <= safe_bw:
                selected = profile

        # Emergency downgrade: if buffer is critical, drop one tier
        if state.is_emergency:
            idx = _PROFILES_ASCENDING.index(selected)
            if idx > 0:
                selected = _PROFILES_ASCENDING[idx - 1]
                log.warning(
                    "bw.emergency_downgrade",
                    session=session_id,
                    profile=selected.name,
                    buffer_s=buffer_seconds,
                )

        log.debug(
            "bw.selected",
            session=session_id,
            profile=selected.name,
            safe_kbps=round(safe_bw),
        )
        return selected

    def record_bandwidth(
        self, session_id: str, kbps: float, buffer_seconds: float
    ) -> dict:
        """Record a bandwidth + buffer sample and return current state dict."""
        state = self._get_or_create_session(session_id)
        state.add_bandwidth_sample(kbps)
        state.update_buffer(buffer_seconds)
        return state.to_dict()

    def clear_session(self, session_id: str) -> None:
        """Remove the session state (call on stream end)."""
        self._sessions.pop(session_id, None)

    # ── Tier budget helpers ───────────────────────────────────────────────────

    @staticmethod
    def get_tier_bitrates(
        profile: BandwidthProfile,
        emergency: bool = False,
    ) -> Dict[str, int]:
        """Return per-tier kbps allocation for a profile.

        Parameters
        ----------
        emergency:
            If ``True``, returns the emergency budget fractions instead of
            the normal fractions — P5 is more aggressively reduced.
        """
        if emergency:
            return _emergency_tier_bitrates(profile.target_kbps)
        return profile.tier_kbps

    @staticmethod
    def estimate_qp_for_bitrate(
        target_kbps: int,
        profile: BandwidthProfile,
    ) -> int:
        """Estimate the QP value required to hit a target bitrate.

        Uses the empirical linear approximation from the QP-bitrate table
        in ``settings``.  Returns the closest entry.
        """
        table = settings.QP_BITRATE_TABLE  # {qp: approx_mbps}
        target_mbps = target_kbps / 1000.0
        best_qp = profile.uniform_qp
        best_diff = float("inf")
        for qp, mbps in table.items():
            diff = abs(mbps - target_mbps)
            if diff < best_diff:
                best_diff = diff
                best_qp = qp
        return best_qp

    # ── Private ───────────────────────────────────────────────────────────────

    def _get_or_create_session(self, session_id: str) -> BufferHealthState:
        if session_id not in self._sessions:
            self._sessions[session_id] = BufferHealthState()
        return self._sessions[session_id]


# ── Module-level singleton ────────────────────────────────────────────────────

bandwidth_service = BandwidthService()
