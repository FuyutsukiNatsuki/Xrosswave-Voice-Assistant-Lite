"""Deterministic formant-extraction check using a synthetic vowel.

Builds a source-filter vowel: a white-noise source (whispered-vowel analogue,
which excites the whole band evenly) passed through a cascade of 2nd-order
resonators at known formant frequencies. Then confirms ``latest_formants``
recovers F1-F4 within tolerance. No microphone needed. The RNG is seeded so the
result is reproducible.

Formant estimation is inherently less exact than F0, so tolerance is wider.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_formant_synthetic.py
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import numpy as np

from xvalite.analysis.formant import latest_formants

SAMPLERATE = 44100
DURATION = 0.6  # seconds
SEED = 0
# Formant estimation error grows with frequency and is typically a few percent,
# so we accept the larger of an absolute floor and a relative bound rather than
# a single Hz figure.
TOLERANCE_FLOOR_HZ = 150.0
TOLERANCE_REL = 0.10

# Target vowel ~ /a/-ish, plus a 4th formant. Narrow bandwidths keep the peaks
# sharp so the tracker localizes them well.
TARGET_FORMANTS = [800.0, 1200.0, 2500.0, 3500.0]
BANDWIDTHS = [60.0, 70.0, 80.0, 90.0]

# Match the analyzer to the synthetic content: exactly 4 formants below a
# ceiling just above F4, so the LPC pole budget has no spare poles to place on
# spurious peaks. (Production defaults differ — 5 formants up to 5500 Hz.)
ANALYZER_MAX_FORMANT = 4500.0
ANALYZER_NUM_FORMANTS = 4.0


def resonator(x: np.ndarray, freq: float, bw: float, samplerate: int) -> np.ndarray:
    """Apply a 2nd-order resonator at (freq, bandwidth)."""
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


def synth_vowel() -> np.ndarray:
    # All-pole (cascade) source-filter model driven by white noise. The cascade
    # of 2nd-order sections is exactly the all-pole vowel filter whose poles sit
    # at the target formants -- i.e. the model LPC/Burg is designed to invert.
    rng = np.random.default_rng(SEED)
    sig = rng.standard_normal(int(SAMPLERATE * DURATION))
    for freq, bw in zip(TARGET_FORMANTS, BANDWIDTHS):
        sig = resonator(sig, freq, bw, SAMPLERATE)
    sig /= np.max(np.abs(sig)) + 1e-12
    return sig.astype(np.float32)


def main() -> int:
    print(f"samplerate={SAMPLERATE} Hz, window={DURATION}s")
    print(f"tolerance: max({TOLERANCE_FLOOR_HZ:.0f} Hz, {TOLERANCE_REL:.0%} of expected)")
    print("source: seeded white noise (whispered-vowel analogue)\n")

    vowel = synth_vowel()
    measured = latest_formants(
        vowel,
        SAMPLERATE,
        max_formant=ANALYZER_MAX_FORMANT,
        num_formants=ANALYZER_NUM_FORMANTS,
    )

    all_ok = True
    for i, expected in enumerate(TARGET_FORMANTS):
        m = measured[i]
        err = abs(m - expected)
        tol = max(TOLERANCE_FLOOR_HZ, TOLERANCE_REL * expected)
        ok = err <= tol
        all_ok = all_ok and ok
        mark = "OK " if ok else "FAIL"
        print(
            f"[{mark}] F{i + 1}: expected {expected:6.1f} Hz  ->  measured {m:6.1f} Hz"
            f"  (err {err:5.1f}, tol {tol:5.1f})"
        )

    print("\nRESULT:", "ALL PASS" if all_ok else "FAILURES PRESENT")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
