"""Deterministic sanity check for register / voice-tendency estimation.

Register classification leans on formant/spectral shape that pure synthetic
tones don't really have, so here we validate the robust, direction-level
behavior of the feature extraction:

  * voice tendency follows F0 (low tone → 低声寄り, high tone → 高声寄り), and
  * HNR is higher for a clean tone than for a breathy (noise-added) one.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_voice_profile_synthetic.py
"""

import _bootstrap  # noqa: F401

import numpy as np

from xvalite.analysis.voice_profile import measure_voice_profile

SR = 44100
DUR = 1.0


def tone(f0, n_harmonics, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(SR * DUR)) / SR
    sig = sum((1.0 / k) * np.sin(2 * np.pi * k * f0 * t) for k in range(1, n_harmonics + 1))
    sig = sig / np.max(np.abs(sig))
    if noise:
        sig = (1 - noise) * sig + noise * rng.standard_normal(sig.size)
    return (0.3 * sig / np.max(np.abs(sig))).astype(np.float32)


def _resonator(x, freq, bw):
    r = np.exp(-np.pi * bw / SR)
    a1 = 2 * r * np.cos(2 * np.pi * freq / SR)
    a2 = -(r ** 2)
    y = np.zeros_like(x)
    y1 = y2 = 0.0
    for n in range(x.size):
        y0 = x[n] + a1 * y1 + a2 * y2
        y[n] = y0
        y2, y1 = y1, y0
    return y


def vowel_sound(f1, f2, seed=0):
    """A whispered-vowel analogue: noise through two formant resonators."""
    rng = np.random.default_rng(seed)
    src = rng.standard_normal(int(SR * DUR))
    sig = _resonator(src, f1, 80.0) / 1.0 + _resonator(src, f2, 100.0)
    return (0.3 * sig / (np.max(np.abs(sig)) + 1e-9)).astype(np.float32)


def main() -> int:
    low = measure_voice_profile(tone(150.0, 10), SR)
    high = measure_voice_profile(tone(600.0, 4), SR)
    clean = measure_voice_profile(tone(150.0, 8, noise=0.0), SR)
    breathy = measure_voice_profile(tone(150.0, 8, noise=0.6, seed=1), SR)

    print(f"low  tone:  F0={low.mean_f0:6.1f}  tendency={low.tendency}  "
          f"register={low.register}  HNR={low.hnr:.1f}")
    print(f"high tone:  F0={high.mean_f0:6.1f}  tendency={high.tendency}  "
          f"register={high.register}  HNR={high.hnr:.1f}")
    print(f"clean:   HNR={clean.hnr:.1f}    breathy: HNR={breathy.hnr:.1f}")

    # Vowel estimation on formant-filtered noise (/a/: F1 800/F2 1200, /i/: 300/2300).
    va = measure_voice_profile(vowel_sound(800.0, 1200.0), SR)
    vi = measure_voice_profile(vowel_sound(300.0, 2300.0), SR)
    print(f"/a/ -> vowel={va.vowel}  (F1={va.mean_f1:.0f} F2={va.mean_f2:.0f})")
    print(f"/i/ -> vowel={vi.vowel}  (F1={vi.mean_f1:.0f} F2={vi.mean_f2:.0f})")

    checks = {
        # The real-voice tendency thresholds shouldn't read a 150 Hz tone as a
        # high voice; exact low/mid on a synthetic buzz isn't meaningful.
        "low tone not classified high": low.tendency != "high",
        "high tone -> 高声寄り": high.tendency == "high",
        "clean HNR > breathy HNR": np.isfinite(clean.hnr)
        and np.isfinite(breathy.hnr)
        and clean.hnr > breathy.hnr,
        "voiced tones classified (not Unknown)": low.register != "Unknown"
        and high.register != "Unknown",
        "/a/ vowel estimated as a": va.vowel == "a",
        "/i/ vowel estimated as i": vi.vowel == "i",
    }
    ok = True
    for name, passed in checks.items():
        ok = ok and passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}")
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
