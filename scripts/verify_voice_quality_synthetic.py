"""Deterministic jitter/shimmer check using synthetic voiced tones.

Synthesizes a quasi-periodic glottal-ish tone (sum of harmonics) cycle by
cycle, with controllable period perturbation (jitter) and amplitude
perturbation (shimmer). Confirms:

  * a CLEAN tone reads near-zero and stays BELOW the warning thresholds, and
  * a PERTURBED tone reads elevated and crosses ABOVE the thresholds.

The RNG is seeded for reproducibility. No microphone needed.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_voice_quality_synthetic.py
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import numpy as np

from xvalite.analysis.voice_quality import (
    JITTER_LOCAL_WARN,
    SHIMMER_LOCAL_WARN,
    measure_voice_quality,
)

SAMPLERATE = 44100
DURATION = 1.0   # 1-second window (matches app cadence)
F0 = 150.0       # 44100 / 150 = 294 samples exactly -> no rounding jitter when clean
N_HARMONICS = 8


def synth_voice(jitter: float, shimmer: float, seed: int) -> np.ndarray:
    """Build a quasi-periodic tone with given period/amplitude perturbation.

    jitter/shimmer are the std-dev of the relative per-cycle perturbation.
    """
    rng = np.random.default_rng(seed)
    nominal_period = SAMPLERATE / F0
    n_target = int(SAMPLERATE * DURATION)
    cycles = []
    total = 0
    while total < n_target:
        period = int(round(nominal_period * (1.0 + jitter * rng.standard_normal())))
        period = max(2, period)
        amp = 1.0 + shimmer * rng.standard_normal()
        phase = np.arange(period) / period
        cycle = sum((1.0 / k) * np.sin(2 * np.pi * k * phase) for k in range(1, N_HARMONICS + 1))
        cycles.append(amp * cycle)
        total += period
    sig = np.concatenate(cycles)[:n_target]
    sig /= np.max(np.abs(sig)) + 1e-12
    return sig.astype(np.float32)


def main() -> int:
    print(f"samplerate={SAMPLERATE} Hz, window={DURATION}s, F0={F0} Hz")
    print(
        f"thresholds: jitter > {JITTER_LOCAL_WARN:.2%}, shimmer > {SHIMMER_LOCAL_WARN:.2%}\n"
    )

    clean = synth_voice(jitter=0.0, shimmer=0.0, seed=1)
    # Inject enough perturbation to clear the (raised) warning thresholds.
    perturbed = synth_voice(jitter=0.12, shimmer=0.28, seed=2)

    vq_clean = measure_voice_quality(clean, SAMPLERATE)
    vq_pert = measure_voice_quality(perturbed, SAMPLERATE)

    print(
        f"clean    : jitter={vq_clean.jitter_local:.3%}  shimmer={vq_clean.shimmer_local:.3%}"
        f"  warnings(j/s)={vq_clean.jitter_warning}/{vq_clean.shimmer_warning}"
    )
    print(
        f"perturbed: jitter={vq_pert.jitter_local:.3%}  shimmer={vq_pert.shimmer_local:.3%}"
        f"  warnings(j/s)={vq_pert.jitter_warning}/{vq_pert.shimmer_warning}"
    )

    checks = {
        "clean below jitter threshold": not vq_clean.jitter_warning,
        "clean below shimmer threshold": not vq_clean.shimmer_warning,
        "perturbed above jitter threshold": vq_pert.jitter_warning,
        "perturbed above shimmer threshold": vq_pert.shimmer_warning,
    }
    print()
    all_ok = True
    for name, ok in checks.items():
        all_ok = all_ok and ok
        print(f"[{'OK ' if ok else 'FAIL'}] {name}")

    print("\nRESULT:", "ALL PASS" if all_ok else "FAILURES PRESENT")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
