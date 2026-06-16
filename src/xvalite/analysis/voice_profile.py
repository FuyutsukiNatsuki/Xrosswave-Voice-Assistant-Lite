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

_REGISTER_JA = {
    "Chest": "地声寄り",
    "Mix": "ミックス",
    "Head": "裏声寄り",
    "Unknown": "--",
}
_TENDENCY_JA = {"low": "低声寄り", "mid": "中間", "high": "高声寄り", "unknown": "--"}


@dataclass(frozen=True)
class VoiceProfile:
    register: str          # Chest | Mix | Head | Unknown
    register_conf: str     # 高 | 中 | 低 | --
    tendency: str          # low | mid | high | unknown
    tendency_conf: str
    mean_f0: float
    mean_f1: float
    hnr: float
    centroid: float

    @property
    def register_ja(self) -> str:
        return _REGISTER_JA.get(self.register, "--")

    @property
    def tendency_ja(self) -> str:
        return _TENDENCY_JA.get(self.tendency, "--")


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
        conf = "高" if (f0 < 230 and hnr > 16 and centroid < 1700) else "中"
        return "Chest", conf
    if head:
        conf = "高" if f0 > 560 else "中"
        return "Head", conf
    return "Mix", "低"  # the genuinely fuzzy middle


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
        return "high", ("高" if score >= 3.0 else "中")
    if score <= -1.8:
        return "low", ("高" if score <= -2.5 else "中")
    return "mid", "中"


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
