"""Voice register + voice-tendency estimation.

Combines features XVALite already has (F0, F1, spectrum) with HNR (added via
Parselmouth) to estimate, on a ~1 s voiced window:

* **register** — Chest (地声寄り) / Mix / Head·Falsetto (裏声寄り), and
* **tendency** — a low/mid/high "voice tendency" (we deliberately report the
  acoustic tendency rather than a literal gender, which voice alone can't
  determine).

These are *estimates with a confidence*, not verdicts: thresholds vary with mic
and speaker, the Mix region is genuinely fuzzy, and results are only meaningful
on sustained phonation. Deliberately avoids heavy deps (librosa/pyworld); HNR
stands in for the aperiodicity/breathiness cue.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import parselmouth
from parselmouth.praat import call

from .formant import latest_formants
from .pitch import extract_f0

PROFILE_PITCH_CEILING = 1000.0  # high enough to catch head/falsetto F0

# --- register thresholds (tunable; starting points, calibrate on real voice) ---
CHEST_F0_MAX = 280.0
CHEST_F1_MIN = 520.0
CHEST_HNR_MIN = 14.0
CHEST_CENTROID_MAX = 1900.0
HEAD_F0_MIN = 520.0
HEAD_F1_MAX = 480.0
HEAD_HNR_MAX = 12.0  # low HNR ≈ breathy (stand-in for aperiodicity)

# --- tendency (low/high voice) scoring thresholds ---
F0_HIGH = 210.0
F0_LOW = 165.0
F1_LOW = 480.0
CENTROID_HIGH = 1850.0

# --- vowel reference formants (F1, F2) in Hz: male/female averages and their
# mean (used for classification). Values from cited Japanese-vowel averages. ---
VOWEL_REF_MALE = {
    "a": (700.0, 1200.0),
    "i": (300.0, 2200.0),
    "u": (400.0, 1300.0),
    "e": (500.0, 1700.0),
    "o": (500.0, 900.0),
}
VOWEL_REF_FEMALE = {
    "a": (850.0, 1300.0),
    "i": (350.0, 2400.0),
    "u": (450.0, 1500.0),
    "e": (600.0, 1900.0),
    "o": (600.0, 1000.0),
}
_VOWEL_REF = {
    v: ((VOWEL_REF_MALE[v][0] + VOWEL_REF_FEMALE[v][0]) / 2,
        (VOWEL_REF_MALE[v][1] + VOWEL_REF_FEMALE[v][1]) / 2)
    for v in VOWEL_REF_MALE
}
# Vowel estimation uses a formant ceiling tuned for F1/F2 (more accurate than
# the 6400 Hz display ceiling), a log-frequency distance metric, and an
# "unknown" gate so noisy/intermediate formants aren't forced onto central /e/.
VOWEL_FORMANT_CEILING = 5000.0
VOWEL_MAX_LOGDIST = 0.55


@dataclass(frozen=True)
class VoiceProfile:
    # Language-neutral keys; the GUI translates them via i18n.
    register: str          # Chest | Mix | Head | Unknown
    register_conf: str     # high | medium | low | --
    tendency: str          # low | mid | high | unknown
    tendency_conf: str
    mean_f0: float
    mean_f1: float
    hnr: float
    centroid: float


def _spectral_centroid(samples: np.ndarray, samplerate: int) -> float:
    n = samples.size
    if n == 0:
        return float("nan")
    windowed = samples.astype(np.float64) * np.hanning(n)
    power = np.abs(np.fft.rfft(windowed)) ** 2
    freqs = np.fft.rfftfreq(n, 1.0 / samplerate)
    total = power.sum()
    return float((freqs * power).sum() / total) if total > 0 else float("nan")


def _hnr(samples: np.ndarray, samplerate: int, floor: float) -> float:
    try:
        sound = parselmouth.Sound(
            np.ascontiguousarray(samples, dtype=np.float64), sampling_frequency=samplerate
        )
        harmonicity = call(sound, "To Harmonicity (cc)", 0.01, max(50.0, floor), 0.1, 1.0)
        values = np.asarray(harmonicity.values).ravel()
        valid = values[values > -200.0]  # Praat marks undefined frames as -200
        return float(np.mean(valid)) if valid.size else float("nan")
    except parselmouth.PraatError:
        return float("nan")


def _estimate_register(f0: float, f1: float, hnr: float, centroid: float):
    chest = f0 < CHEST_F0_MAX and f1 > CHEST_F1_MIN and hnr > CHEST_HNR_MIN and centroid < CHEST_CENTROID_MAX
    head = f0 > HEAD_F0_MIN or (f1 < HEAD_F1_MAX and hnr < HEAD_HNR_MAX)
    if chest:
        conf = "high" if (f0 < 230 and hnr > 16 and centroid < 1700) else "medium"
        return "Chest", conf
    if head:
        conf = "high" if f0 > 560 else "medium"
        return "Head", conf
    return "Mix", "low"  # the genuinely fuzzy middle


def _vowel_from_formants(f1: float, f2: float):
    """Nearest Japanese vowel by log-frequency distance in (F1, F2) space.

    Returns ``(vowel, conf)``; ``unknown`` if no reference is close enough
    (so noisy/intermediate formants aren't forced onto the central /e/).
    """
    if not (np.isfinite(f1) and np.isfinite(f2) and f1 > 0 and f2 > 0):
        return "unknown", "--"
    dists = {
        v: math.hypot(math.log(f1 / rf1), math.log(f2 / rf2))
        for v, (rf1, rf2) in _VOWEL_REF.items()
    }
    ordered = sorted(dists.values())
    best = min(dists, key=dists.get)
    if ordered[0] > VOWEL_MAX_LOGDIST:
        return "unknown", "low"
    ratio = ordered[0] / ordered[1] if ordered[1] > 0 else 1.0
    conf = "high" if ratio < 0.55 else ("medium" if ratio < 0.8 else "low")
    return best, conf


def estimate_vowel(samples: np.ndarray, samplerate: int):
    """Estimate the vowel from a short window. Returns ``(vowel, conf, f1, f2)``.

    Uses a formant ceiling tuned for F1/F2 accuracy (not the display ceiling).
    """
    formants = latest_formants(samples, samplerate, max_formant=VOWEL_FORMANT_CEILING)
    f1 = float(formants[0])
    f2 = float(formants[1])
    vowel, conf = _vowel_from_formants(f1, f2)
    return vowel, conf, f1, f2


def _estimate_tendency(f0: float, f1: float, centroid: float):
    score = 0.0
    if f0 > F0_HIGH:
        score += 2.8
    elif f0 < F0_LOW:
        score -= 2.3
    if f1 < F1_LOW:
        score += 0.8
    if centroid > CENTROID_HIGH:
        score += 0.6
    if score >= 2.2:
        return "high", ("high" if score >= 3.0 else "medium")
    if score <= -1.8:
        return "low", ("high" if score <= -2.5 else "medium")
    return "mid", "medium"


def measure_voice_profile(
    samples: np.ndarray,
    samplerate: int,
    pitch_floor: float = 75.0,
    pitch_ceiling: float = PROFILE_PITCH_CEILING,
) -> VoiceProfile:
    """Estimate register + voice tendency over a window of samples."""
    _, f0arr = extract_f0(samples, samplerate, pitch_floor, pitch_ceiling)
    voiced = f0arr[np.isfinite(f0arr)]
    mean_f0 = float(np.mean(voiced)) if voiced.size else float("nan")
    mean_f1 = float(latest_formants(samples, samplerate)[0])
    hnr = _hnr(samples, samplerate, pitch_floor)
    centroid = _spectral_centroid(samples, samplerate)

    if not (np.isfinite(mean_f0) and np.isfinite(mean_f1)):
        return VoiceProfile("Unknown", "--", "unknown", "--", mean_f0, mean_f1, hnr, centroid)

    register, rconf = _estimate_register(mean_f0, mean_f1, hnr, centroid)
    tendency, tconf = _estimate_tendency(mean_f0, mean_f1, centroid)
    return VoiceProfile(register, rconf, tendency, tconf, mean_f0, mean_f1, hnr, centroid)
