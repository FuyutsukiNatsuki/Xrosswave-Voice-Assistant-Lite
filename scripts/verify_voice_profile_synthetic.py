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

from xvalite.analysis.voice_profile import estimate_vowel, measure_voice_profile

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


def voiced_vowel(f0_hz, formants, bandwidths, seed=0):
    """A voiced vowel: sawtooth + high-passed aspiration noise through a
    resonator cascade, with the fundamental reinstated.

    Design notes (each element earned by a failure mode):
    * five formants below 5 kHz — matches the production analyzer's pole
      budget, otherwise a spare pole lands between F1 and F2;
    * high-passed noise — fills the spectrum between harmonics so Burg samples
      formant peaks continuously, without breaking low-band periodicity;
    * reinstated fundamental — the cascade all but removes it, which makes the
      pitch tracker octave-jump. Callers should also pick an F0 whose period
      is an integer number of samples (e.g. 175 Hz → 252 samples).
    """
    n = int(SR * DUR)
    phase = np.cumsum(np.full(n, f0_hz)) / SR
    saw = 2.0 * (phase - np.floor(phase)) - 1.0
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n)
    k = max(3, SR // 700)
    hp_noise = noise - np.convolve(noise, np.ones(k) / k, mode="same")
    sig = saw + 0.5 * hp_noise
    for f, b in zip(formants, bandwidths):
        sig = _resonator(sig, f, b)
    sig = sig / (np.max(np.abs(sig)) + 1e-9)
    t = np.arange(n) / SR
    sig = 0.85 * sig + 0.15 * np.sin(2 * np.pi * f0_hz * t)
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
    va_v, _, va_f1, va_f2 = estimate_vowel(vowel_sound(800.0, 1200.0), SR)
    vi_v, _, vi_f1, vi_f2 = estimate_vowel(vowel_sound(300.0, 2300.0), SR)
    print(f"/a/ -> vowel={va_v}  (F1={va_f1:.0f} F2={va_f2:.0f})")
    print(f"/i/ -> vowel={vi_v}  (F1={vi_f1:.0f} F2={vi_f2:.0f})")

    # Formant-decided tendency: SAME F0 (175 Hz = an exact 252-sample period,
    # inside the male/female overlap zone where the F0 term is 0) but
    # male-reference vs female-reference /a/ formants incl. F3. The formant
    # group alone must separate them.
    male_v = measure_voice_profile(
        voiced_vowel(175.0, [700.0, 1200.0, 2500.0, 3400.0, 4400.0],
                     [70.0, 80.0, 100.0, 130.0, 160.0]), SR
    )
    female_v = measure_voice_profile(
        voiced_vowel(175.0, [850.0, 1300.0, 2950.0, 4100.0, 4500.0],
                     [70.0, 80.0, 100.0, 130.0, 160.0]), SR
    )
    print(f"175Hz + male formants   -> tendency={male_v.tendency}  (F0={male_v.mean_f0:.0f})")
    print(f"175Hz + female formants -> tendency={female_v.tendency}  (F0={female_v.mean_f0:.0f})")

    checks = {
        # Direction-level checks on plain buzz tones (their "formants" are just
        # harmonics, so exact labels aren't meaningful — only the F0 direction).
        "low tone not classified high": low.tendency != "high",
        "high tone not classified low": high.tendency != "low",
        # The new formant-aware behavior: identical F0 in the overlap zone,
        # resonances alone must decide.
        "175Hz + male formants -> 男声寄り": male_v.tendency == "low",
        "175Hz + female formants -> 女声寄り": female_v.tendency == "high",
        "clean HNR > breathy HNR": np.isfinite(clean.hnr)
        and np.isfinite(breathy.hnr)
        and clean.hnr > breathy.hnr,
        "voiced tones classified (not Unknown)": low.register != "Unknown"
        and high.register != "Unknown",
        "/a/ vowel estimated as a": va_v == "a",
        "/i/ vowel estimated as i": vi_v == "i",
    }
    ok = True
    for name, passed in checks.items():
        ok = ok and passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}")
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
