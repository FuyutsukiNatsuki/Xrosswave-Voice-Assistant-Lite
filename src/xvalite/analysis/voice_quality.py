"""Voice-quality metrics: Jitter and Shimmer via Parselmouth/Praat.

Jitter measures cycle-to-cycle variation in *period* (frequency stability);
shimmer measures cycle-to-cycle variation in *amplitude*. Both are computed on
~1-second windows at a 1 Hz cadence (see Handoff.md) from a periodic
PointProcess extracted by Praat.

Per the requirements, warning thresholds are fixed (not user-configurable). The
defaults below are the common Praat/MDVP-style norms for "local" jitter/shimmer;
they are tunable here in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import parselmouth
from parselmouth.praat import call

from .pitch import DEFAULT_PITCH_CEILING, DEFAULT_PITCH_FLOOR

# Fixed warning thresholds (fractions, not percent).
JITTER_LOCAL_WARN = 0.0104   # 1.04 %
SHIMMER_LOCAL_WARN = 0.0381  # 3.81 %


@dataclass(frozen=True)
class VoiceQuality:
    """Local jitter and shimmer as fractions (e.g. 0.01 == 1 %). NaN if undefined."""

    jitter_local: float
    shimmer_local: float

    @property
    def jitter_warning(self) -> bool:
        return np.isfinite(self.jitter_local) and self.jitter_local > JITTER_LOCAL_WARN

    @property
    def shimmer_warning(self) -> bool:
        return np.isfinite(self.shimmer_local) and self.shimmer_local > SHIMMER_LOCAL_WARN


def measure_voice_quality(
    samples: np.ndarray,
    samplerate: int,
    pitch_floor: float = DEFAULT_PITCH_FLOOR,
    pitch_ceiling: float = DEFAULT_PITCH_CEILING,
) -> VoiceQuality:
    """Compute local jitter and shimmer over a window of samples.

    Returns NaN metrics if the window is not periodic enough for Praat to form
    a usable PointProcess (e.g. unvoiced or silent).
    """
    sound = parselmouth.Sound(
        np.ascontiguousarray(samples, dtype=np.float64),
        sampling_frequency=samplerate,
    )
    try:
        point_process = call(
            sound, "To PointProcess (periodic, cc)", pitch_floor, pitch_ceiling
        )
        # Args: tmin, tmax, shortest period, longest period, max period factor.
        jitter = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        # Shimmer additionally needs the sound and a max amplitude factor.
        shimmer = call(
            [sound, point_process],
            "Get shimmer (local)",
            0, 0, 0.0001, 0.02, 1.3, 1.6,
        )
    except parselmouth.PraatError:
        return VoiceQuality(float("nan"), float("nan"))

    return VoiceQuality(float(jitter), float(shimmer))
