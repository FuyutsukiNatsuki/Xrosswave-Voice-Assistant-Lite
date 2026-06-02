"""Measure per-analysis cost vs the real-time budget.

The worker runs pitch + formants every chunk (~46 ms at blocksize 2048) and
voice quality once per second. If pitch+formant time stays well under the chunk
duration, analysis keeps up with real time on this machine.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\bench_analysis.py
"""

import time

import _bootstrap  # noqa: F401

import numpy as np
import soundfile as sf

from xvalite.analysis.formant import latest_formants
from xvalite.analysis.pitch import latest_f0
from xvalite.analysis.voice_quality import measure_voice_quality

PATH = r"C:\XVALite\testdata\test.wav"
SR = 44100
CHUNK_MS = 2048 / SR * 1000  # ~46 ms
N = 200


def bench(fn, window) -> float:
    fn(window, SR)  # warm up
    start = time.perf_counter()
    for _ in range(N):
        fn(window, SR)
    return (time.perf_counter() - start) / N * 1000  # ms/call


def main() -> int:
    x, sr = sf.read(PATH, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
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
