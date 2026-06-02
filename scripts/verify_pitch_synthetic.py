"""Deterministic F0-extraction check using synthetic tones.

Generates sine waves at known frequencies and confirms ``extract_f0`` recovers
them within tolerance. No microphone needed — this proves the analysis path
works on its own.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_pitch_synthetic.py
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import numpy as np

from xvalite.analysis.pitch import latest_f0

SAMPLERATE = 44100
DURATION = 0.5  # seconds
TOLERANCE_HZ = 5.0


def make_tone(freq: float, samplerate: int, duration: float) -> np.ndarray:
    t = np.arange(int(samplerate * duration)) / samplerate
    return (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def main() -> int:
    test_freqs = [110.0, 220.0, 330.0, 440.0]
    print(f"samplerate={SAMPLERATE} Hz, window={DURATION}s, tolerance=+/-{TOLERANCE_HZ} Hz\n")

    all_ok = True
    for expected in test_freqs:
        tone = make_tone(expected, SAMPLERATE, DURATION)
        measured = latest_f0(tone, SAMPLERATE)
        err = abs(measured - expected)
        ok = err <= TOLERANCE_HZ
        all_ok = all_ok and ok
        mark = "OK " if ok else "FAIL"
        print(f"[{mark}] expected {expected:6.1f} Hz  ->  measured {measured:6.1f} Hz  (err {err:.2f})")

    # Sanity: silence must read as unvoiced (NaN).
    silence = np.zeros(int(SAMPLERATE * DURATION), dtype=np.float32)
    silent_f0 = latest_f0(silence, SAMPLERATE)
    silence_ok = np.isnan(silent_f0)
    all_ok = all_ok and silence_ok
    print(f"[{'OK ' if silence_ok else 'FAIL'}] silence -> {'NaN (unvoiced)' if silence_ok else silent_f0}")

    print("\nRESULT:", "ALL PASS" if all_ok else "FAILURES PRESENT")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
