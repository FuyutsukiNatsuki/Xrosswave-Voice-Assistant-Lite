"""Formant extraction (F1-F4) via Parselmouth (Burg method).

Per the requirements, formants are analyzed on ~1-second windows at a 1 Hz
cadence (quasi-realtime), unlike pitch which updates continuously. This module
provides the per-window analysis; the scheduling lives in the pipeline layer.

Frames where a formant is undefined are returned as NaN.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import parselmouth

# Praat defaults tuned for voice. ``maximum_formant`` ~5500 Hz suits most adult
# voices; lower (~5000) for typically male tracts if needed later.
DEFAULT_MAX_FORMANT = 6400.0  # raised so high formants of some voices are found
DEFAULT_NUM_FORMANTS = 5.0    # track 5, report the first 4
NUM_REPORTED = 4


def extract_formants(
    samples: np.ndarray,
    samplerate: int,
    max_formant: float = DEFAULT_MAX_FORMANT,
    num_formants: float = DEFAULT_NUM_FORMANTS,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract F1-F4 over a window of samples.

    Returns:
        ``(times, formants)`` where ``times`` is shape ``(n_frames,)`` and
        ``formants`` is shape ``(n_frames, 4)`` in Hz, NaN where undefined.
    """
    sound = parselmouth.Sound(
        np.ascontiguousarray(samples, dtype=np.float64),
        sampling_frequency=samplerate,
    )
    formant = sound.to_formant_burg(
        max_number_of_formants=num_formants,
        maximum_formant=max_formant,
    )
    times = np.asarray(formant.ts())
    out = np.full((times.size, NUM_REPORTED), np.nan)
    for i, t in enumerate(times):
        for f in range(NUM_REPORTED):
            value = formant.get_value_at_time(f + 1, t)  # formants are 1-indexed
            out[i, f] = value  # already NaN when undefined
    return times, out


def latest_formants(
    samples: np.ndarray,
    samplerate: int,
    max_formant: float = DEFAULT_MAX_FORMANT,
    num_formants: float = DEFAULT_NUM_FORMANTS,
) -> np.ndarray:
    """Representative F1-F4 for a window: per-formant median over frames.

    Returns a length-4 array (Hz); entries are NaN if that formant was never
    defined in the window.
    """
    _, formants = extract_formants(samples, samplerate, max_formant, num_formants)
    if formants.shape[0] == 0:
        return np.full(NUM_REPORTED, np.nan)
    return np.nanmedian(formants, axis=0)
