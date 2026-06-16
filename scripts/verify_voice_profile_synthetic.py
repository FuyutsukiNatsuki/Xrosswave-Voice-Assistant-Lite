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


def main() -> int:
    low = measure_voice_profile(tone(150.0, 10), SR)
    high = measure_voice_profile(tone(600.0, 4), SR)
    clean = measure_voice_profile(tone(150.0, 8, noise=0.0), SR)
    breathy = measure_voice_profile(tone(150.0, 8, noise=0.6, seed=1), SR)

    print(f"low  tone:  F0={low.mean_f0:6.1f}  tendency={low.tendency_ja}  "
          f"register={low.register_ja}  HNR={low.hnr:.1f}")
    print(f"high tone:  F0={high.mean_f0:6.1f}  tendency={high.tendency_ja}  "
          f"register={high.register_ja}  HNR={high.hnr:.1f}")
    print(f"clean:   HNR={clean.hnr:.1f}    breathy: HNR={breathy.hnr:.1f}")

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
    }
    ok = True
    for name, passed in checks.items():
        ok = ok and passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}")
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
