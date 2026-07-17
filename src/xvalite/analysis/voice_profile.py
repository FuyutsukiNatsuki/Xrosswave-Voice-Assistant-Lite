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

# --- tendency (low/high voice) scoring ---
# F0 and the formant group carry EQUAL total weight (±2.2 each), so in the
# F0-overlap zone (165–210 Hz) the resonance evidence decides, and clearly
# contradicting formants can pull an out-of-zone F0 back to neutral.
F0_HIGH = 210.0
F0_LOW = 165.0
F0_WEIGHT = 2.2
VOWEL_TERM_GAIN = 8.0    # log-distance difference (male vs female ref) → score
VOWEL_TERM_CLIP = 1.5    # max contribution of the vowel-relative F1/F2 term
F3_MALE_MAX = 2700.0     # F3 tracks vocal-tract length, nearly vowel-independent
F3_FEMALE_MIN = 2850.0
F3_WEIGHT = 0.8
# F3 is located by SEARCHING the measured formants for the lowest one inside
# this band, not by trusting slot [2] — Burg sometimes inserts a spurious pole
# below F2, shifting every later slot up by one.
F3_BAND = (2300.0, 3400.0)
CENTROID_HIGH = 1850.0
CENTROID_WEIGHT = 0.4
TENDENCY_DECIDE = 1.4    # |score| to leave "mid" (a fully-clipped vowel term suffices)
TENDENCY_STRONG = 3.0    # |score| for high confidence — F0 alone can't reach this;
                         # it needs corroborating formant evidence

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


def _vowel_gender_lean(f1: float, f2: float) -> float:
    """Signed score from vowel-normalized formant position.

    Identifies the vowel first, then asks: is the measured (F1, F2) closer to
    the male or the female reference *for that vowel*? This avoids the classic
    trap of judging raw F1 against a fixed threshold (F1 swings ~300–850 Hz
    with the vowel — far more than the male/female gap). Positive = female-side.
    Returns 0 when the vowel is ambiguous (no reliable normalization).
    """
    vowel, conf = _vowel_from_formants(f1, f2)
    if vowel == "unknown" or conf == "low":
        return 0.0
    m1, m2 = VOWEL_REF_MALE[vowel]
    w1, w2 = VOWEL_REF_FEMALE[vowel]
    d_male = math.hypot(math.log(f1 / m1), math.log(f2 / m2))
    d_female = math.hypot(math.log(f1 / w1), math.log(f2 / w2))
    lean = VOWEL_TERM_GAIN * (d_male - d_female)
    return max(-VOWEL_TERM_CLIP, min(VOWEL_TERM_CLIP, lean))


def _find_f3(formants) -> float:
    """Lowest measured formant inside the F3-plausible band (NaN if none)."""
    for f in formants:  # ascending order, so the first hit is F3
        if np.isfinite(f) and F3_BAND[0] <= f <= F3_BAND[1]:
            return float(f)
    return float("nan")


def _estimate_tendency(f0: float, formants, centroid: float):
    f1 = float(formants[0])
    f2 = float(formants[1])
    score = 0.0
    if f0 > F0_HIGH:
        score += F0_WEIGHT
    elif f0 < F0_LOW:
        score -= F0_WEIGHT

    # Formant group: vowel-relative F1/F2 position + F3 as a tract-length cue.
    score += _vowel_gender_lean(f1, f2)
    f3 = _find_f3(formants)
    if np.isfinite(f3):
        if f3 < F3_MALE_MAX:
            score -= F3_WEIGHT
        elif f3 > F3_FEMALE_MIN:
            score += F3_WEIGHT

    if np.isfinite(centroid) and centroid > CENTROID_HIGH:
        score += CENTROID_WEIGHT

    if score >= TENDENCY_DECIDE:
        return "high", ("high" if score >= TENDENCY_STRONG else "medium")
    if score <= -TENDENCY_DECIDE:
        return "low", ("high" if score <= -TENDENCY_STRONG else "medium")
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
    # Use the vowel-tuned ceiling (5000): more accurate F1–F3 than the display one.
    formants = latest_formants(samples, samplerate, max_formant=VOWEL_FORMANT_CEILING)
    mean_f1 = float(formants[0])
    hnr = _hnr(samples, samplerate, pitch_floor)
    centroid = _spectral_centroid(samples, samplerate)

    if not (np.isfinite(mean_f0) and np.isfinite(mean_f1)):
        return VoiceProfile("Unknown", "--", "unknown", "--", mean_f0, mean_f1, hnr, centroid)

    register, rconf = _estimate_register(mean_f0, mean_f1, hnr, centroid)
    tendency, tconf = _estimate_tendency(mean_f0, formants, centroid)
    return VoiceProfile(register, rconf, tendency, tconf, mean_f0, mean_f1, hnr, centroid)
