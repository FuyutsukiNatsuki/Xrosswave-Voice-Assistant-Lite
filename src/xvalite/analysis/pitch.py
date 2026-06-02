"""Pitch (F0) extraction via Parselmouth.

Given a window of mono samples, returns per-frame F0 estimates. Unvoiced
frames (Parselmouth reports 0 Hz) are converted to NaN so downstream plotting
can leave gaps in the trajectory.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import parselmouth

# Reasonable defaults for human voice. Tunable later / per user.
DEFAULT_PITCH_FLOOR = 75.0
DEFAULT_PITCH_CEILING = 600.0


def extract_f0(
    samples: np.ndarray,
    samplerate: int,
    pitch_floor: float = DEFAULT_PITCH_FLOOR,
    pitch_ceiling: float = DEFAULT_PITCH_CEILING,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract F0 over a window of samples.

    Args:
        samples: 1-D mono signal.
        samplerate: sampling rate in Hz.
        pitch_floor: lowest F0 to track (Hz). The analysis window length is
            ``3 / pitch_floor`` seconds, so ``samples`` must be at least that long.
        pitch_ceiling: highest F0 to track (Hz).

    Returns:
        ``(times, f0)`` — frame center times (s) and F0 values (Hz), with NaN
        for unvoiced frames. Both arrays share the same length.
    """
    sound = parselmouth.Sound(
        np.ascontiguousarray(samples, dtype=np.float64),
        sampling_frequency=samplerate,
    )
    pitch = sound.to_pitch(pitch_floor=pitch_floor, pitch_ceiling=pitch_ceiling)
    freqs = pitch.selected_array["frequency"]
    freqs = np.where(freqs == 0.0, np.nan, freqs)
    return pitch.xs(), freqs


def latest_f0(
    samples: np.ndarray,
    samplerate: int,
    pitch_floor: float = DEFAULT_PITCH_FLOOR,
    pitch_ceiling: float = DEFAULT_PITCH_CEILING,
) -> float:
    """Single representative F0 for a window: median of voiced frames.

    Returns NaN if the window is entirely unvoiced.
    """
    _, f0 = extract_f0(samples, samplerate, pitch_floor, pitch_ceiling)
    voiced = f0[~np.isnan(f0)]
    return float(np.median(voiced)) if voiced.size else float("nan")
