"""Generate testdata/test.wav: a synthetic voice-like signal for verification.

Not a real recording -- an all-pole (cascade resonator) source-filter model,
the same technique as ``verify_formant_synthetic.py``, but driven by a glottal
pulse train (sawtooth-ish) instead of white noise so F0 is also well-defined
(``verify_pitch_synthetic.py`` uses plain sine tones; a pulse train is closer
to a real glottal source and gives the formant filters real harmonic content
to shape). F0 glides 120 -> 400 -> 120 Hz across the clip, and the vowel
filter switches between two formant sets partway through so downstream vowel
estimation sees more than one target. Two ~0.5 s silent gaps exercise the
pipeline's silence dead zone.

Run:
    .venv/bin/python scripts/make_testdata.py [out_path]
"""

import os
import sys

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import numpy as np
import soundfile as sf

SAMPLERATE = 44100
DURATION = 30.0  # seconds
SEED = 0
TARGET_RMS_DBFS = -20.0

# F0 glide: low -> high -> low, so the pitch tracker sees real movement.
F0_LOW = 120.0
F0_HIGH = 400.0

# Two vowel-ish formant sets (F1-F4, Hz) with bandwidths (Hz), applied as a
# cascade of 2nd-order resonators -- an all-pole filter whose poles sit
# exactly at these formants (matches the model verify_formant_synthetic.py
# checks against).
VOWEL_A = ([800.0, 1200.0, 2500.0, 3500.0], [80.0, 90.0, 110.0, 130.0])
VOWEL_I = ([300.0, 2300.0, 3000.0, 3800.0], [60.0, 100.0, 120.0, 140.0])

# Silent gaps (start_sec, duration_sec) carved out of the voiced signal, to
# exercise the pipeline's silence dead zone (see pipeline.DEFAULT_SILENCE_DB).
SILENT_GAPS = [(9.0, 0.5), (20.0, 0.5)]


def resonator(x: np.ndarray, freq: float, bw: float, samplerate: int) -> np.ndarray:
    """Apply a 2nd-order resonator at (freq, bandwidth). Same as the formant verifier."""
    r = np.exp(-np.pi * bw / samplerate)
    theta = 2 * np.pi * freq / samplerate
    a1 = 2 * r * np.cos(theta)
    a2 = -(r ** 2)
    y = np.zeros_like(x)
    y1 = y2 = 0.0
    for n in range(x.size):
        y0 = x[n] + a1 * y1 + a2 * y2
        y[n] = y0
        y2 = y1
        y1 = y0
    return y


def glottal_pulse_train(f0: np.ndarray, samplerate: int) -> np.ndarray:
    """Band-limited-ish sawtooth glottal source at a time-varying F0.

    Phase is the running integral of instantaneous frequency so the glide is
    continuous (no clicks). A plain sawtooth (not full harmonic synthesis) —
    the resonator cascade below does the real spectral shaping.
    """
    phase = np.cumsum(f0) / samplerate
    frac = phase - np.floor(phase)
    return (2.0 * frac - 1.0).astype(np.float64)


def apply_vowel(sig: np.ndarray, formants, bandwidths, samplerate: int) -> np.ndarray:
    out = sig.copy()
    for freq, bw in zip(formants, bandwidths):
        out = resonator(out, freq, bw, samplerate)
    return out


def synth() -> np.ndarray:
    n = int(SAMPLERATE * DURATION)
    t = np.arange(n) / SAMPLERATE

    # F0 glide: low -> high over the first half, high -> low over the second.
    half = DURATION / 2.0
    up = t < half
    f0 = np.where(
        up,
        F0_LOW + (F0_HIGH - F0_LOW) * (t / half),
        F0_HIGH - (F0_HIGH - F0_LOW) * ((t - half) / half),
    )
    source = glottal_pulse_train(f0, SAMPLERATE)

    # Vowel switches once at the midpoint (VOWEL_A -> VOWEL_I), each rendered
    # over the whole signal then cross-faded at the boundary so the switch
    # itself doesn't inject a transient.
    sig_a = apply_vowel(source, *VOWEL_A, SAMPLERATE)
    sig_i = apply_vowel(source, *VOWEL_I, SAMPLERATE)
    fade_n = int(SAMPLERATE * 0.05)
    mix = np.zeros(n)
    mid_n = n // 2
    mix[:mid_n] = 1.0
    ramp = np.linspace(1.0, 0.0, fade_n)
    mix[mid_n : mid_n + fade_n] = ramp
    sig = sig_a * mix + sig_i * (1.0 - mix)

    # Normalize to the target RMS (voiced-region level).
    rms = float(np.sqrt(np.mean(sig ** 2)))
    target_rms = 10 ** (TARGET_RMS_DBFS / 20.0)
    if rms > 0:
        sig *= target_rms / rms

    # Carve silent gaps, with a short raised-cosine taper so they don't click.
    taper_n = int(SAMPLERATE * 0.02)
    taper = 0.5 * (1 - np.cos(np.linspace(0, np.pi, taper_n)))
    for start_sec, dur_sec in SILENT_GAPS:
        start = int(SAMPLERATE * start_sec)
        end = start + int(SAMPLERATE * dur_sec)
        sig[start:end] = 0.0
        sig[start - taper_n : start] *= (1 - taper)
        sig[end : end + taper_n] *= taper

    peak = np.max(np.abs(sig)) + 1e-12
    if peak > 0.99:
        sig *= 0.99 / peak  # headroom guard, only if the taper/mix pushed a peak over
    return sig.astype(np.float32)


def main() -> int:
    rng = np.random.default_rng(SEED)  # reserved for future noise-mixing; unused for now
    del rng

    out_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(__file__), "..", "testdata", "test.wav"
    )
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    sig = synth()
    sf.write(out_path, sig, SAMPLERATE, subtype="PCM_16")

    rms_dbfs = 20.0 * np.log10(np.sqrt(np.mean(sig[sig != 0.0] ** 2)) + 1e-12)
    print(f"wrote {out_path}")
    print(f"duration={sig.size / SAMPLERATE:.1f}s  samplerate={SAMPLERATE} Hz")
    print(f"F0 glide: {F0_LOW:.0f} -> {F0_HIGH:.0f} -> {F0_LOW:.0f} Hz")
    print(f"vowel switch at {DURATION / 2:.1f}s (formants {VOWEL_A[0]} -> {VOWEL_I[0]})")
    print(f"silent gaps: {SILENT_GAPS}")
    print(f"voiced RMS level: {rms_dbfs:.1f} dBFS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
