"""Measure per-analysis cost vs the real-time budget.

The worker runs pitch + formants every chunk (~46 ms at blocksize 2048) and
voice quality once per second. If pitch+formant time stays well under the chunk
duration, analysis keeps up with real time on this machine.

Run:
    .venv/bin/python scripts/bench_analysis.py [path.wav]

If no path is given (and testdata/test.wav is absent), a 5 s voiced signal is
synthesized in memory instead -- see ``make_testdata.synth`` for the technique
(pulse-train source through a resonator-cascade vowel filter).
"""

import os
import sys
import time

import _bootstrap  # noqa: F401

import numpy as np
import soundfile as sf

from xvalite.analysis.formant import latest_formants
from xvalite.analysis.pitch import latest_f0
from xvalite.analysis.voice_quality import measure_voice_quality

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "testdata", "test.wav")
SR = 44100
CHUNK_MS = 2048 / SR * 1000  # ~46 ms
N = 200


def bench(fn, window) -> float:
    fn(window, SR)  # warm up
    start = time.perf_counter()
    for _ in range(N):
        fn(window, SR)
    return (time.perf_counter() - start) / N * 1000  # ms/call


def _synthetic_signal(duration_sec: float = 5.0) -> np.ndarray:
    """In-memory fallback when no test WAV is available: reuse make_testdata's
    pulse-train-through-resonators technique so all analysis stages see
    voice-like content (harmonics + formant structure), not a plain tone."""
    import make_testdata as mt

    n = int(SR * duration_sec)
    t = np.arange(n) / SR
    f0 = mt.F0_LOW + (mt.F0_HIGH - mt.F0_LOW) * (t / duration_sec)
    source = mt.glottal_pulse_train(f0, SR)
    sig = mt.apply_vowel(source, *mt.VOWEL_A, SR)
    rms = float(np.sqrt(np.mean(sig ** 2)))
    target_rms = 10 ** (mt.TARGET_RMS_DBFS / 20.0)
    if rms > 0:
        sig *= target_rms / rms
    return sig.astype(np.float32)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    if os.path.isfile(path):
        x, sr = sf.read(path, dtype="float32", always_2d=True)
        x = x.mean(axis=1)
    else:
        print(f"no WAV at {path!r} -- synthesizing a 5 s voiced signal in memory instead")
        x = _synthetic_signal()
        sr = SR
    # Pick a voiced 1 s region near the middle.
    mid = x.size // 2
    win1s = x[mid : mid + sr]
    pitch_win = win1s[: int(sr * 0.12)]
    formant_win = win1s[: int(sr * 0.1)]

    t_pitch = bench(lambda w, s: latest_f0(w, s, pitch_ceiling=2100.0), pitch_win)
    t_formant = bench(latest_formants, formant_win)
    t_vq = bench(measure_voice_quality, win1s)

    per_chunk = t_pitch + t_formant
    print(f"chunk budget:        {CHUNK_MS:.1f} ms")
    print(f"pitch (0.12 s win):  {t_pitch:.2f} ms/call")
    print(f"formant (0.10 s win):{t_formant:.2f} ms/call")
    print(f"voice quality (1 s): {t_vq:.2f} ms/call (once per second)")
    print(f"per-chunk (pitch+formant): {per_chunk:.2f} ms  "
          f"({per_chunk / CHUNK_MS * 100:.0f}% of budget)")
    headroom_ok = per_chunk < CHUNK_MS * 0.5
    print("REALTIME HEADROOM OK" if headroom_ok else "WARNING: little headroom")
    return 0 if headroom_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
