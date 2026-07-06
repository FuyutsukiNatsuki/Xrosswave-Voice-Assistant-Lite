"""Verify the file-input module and run full analysis on a real recording.

Three parts:
  1. Integrity   — drain FileInput (non-realtime) and confirm the reassembled
                   signal matches a direct soundfile read exactly.
  2. Pacing      — with realtime=True, ~1 s of audio should take ~1 s to arrive.
  3. Analysis    — slide a 1 s window over the file and print F0, formants, and
                   jitter/shimmer. Qualitative check on real voice.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_file_input.py [path]
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import os
import sys
import time

import numpy as np
import soundfile as sf

from xvalite.audio.file_input import FileInput
from xvalite.audio.input import DEFAULT_SAMPLERATE
from xvalite.analysis.pitch import latest_f0
from xvalite.analysis.formant import latest_formants
from xvalite.analysis.voice_quality import measure_voice_quality

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "testdata", "test.wav")
WINDOW_SEC = 1.0
HOP_SEC = 0.5


def drain(src: FileInput) -> np.ndarray:
    chunks = []
    while True:
        chunk = src.read(timeout=5.0)
        if chunk is None:  # end-of-stream sentinel
            break
        chunks.append(chunk)
    return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def part_integrity(path: str) -> bool:
    print("== 1. Integrity ==")
    expected, sr = sf.read(path, dtype="float32", always_2d=True)
    expected = expected.mean(axis=1)
    src = FileInput(path, samplerate=DEFAULT_SAMPLERATE, realtime=False)
    src.start()
    got = drain(src)
    src.stop()

    same_len = got.size == expected.size
    # Only directly comparable when no resample happened.
    exact = same_len and sr == DEFAULT_SAMPLERATE and np.allclose(got, expected, atol=1e-6)
    print(f"file samplerate={sr}, frames expected={expected.size}, got={got.size}")
    ok = same_len and (exact or sr != DEFAULT_SAMPLERATE)
    print(f"[{'OK ' if ok else 'FAIL'}] reassembled length matches"
          + ("" if sr != DEFAULT_SAMPLERATE else f", samples exact={exact}"))
    return ok


def part_pacing(path: str) -> bool:
    print("\n== 2. Real-time pacing ==")
    src = FileInput(path, samplerate=DEFAULT_SAMPLERATE, realtime=True)
    src.start()
    target = DEFAULT_SAMPLERATE * 1.0  # ~1 second of samples
    got = 0
    start = time.monotonic()
    while got < target:
        chunk = src.read(timeout=5.0)
        if chunk is None:
            break
        got += chunk.size
    elapsed = time.monotonic() - start
    src.stop()
    ok = 0.7 <= elapsed <= 1.6  # generous bounds for scheduler jitter
    print(f"delivered ~1 s of audio in {elapsed:.2f} s")
    print(f"[{'OK ' if ok else 'FAIL'}] pacing within expected bounds")
    return ok


def part_analysis(path: str) -> None:
    print("\n== 3. Analysis over the recording (1 s window, 0.5 s hop) ==")
    samples, sr = sf.read(path, dtype="float32", always_2d=True)
    samples = samples.mean(axis=1)
    win = int(sr * WINDOW_SEC)
    hop = int(sr * HOP_SEC)
    print(f"{'t(s)':>5}  {'F0(Hz)':>7}  {'F1':>5} {'F2':>5} {'F3':>5} {'F4':>5}  "
          f"{'jit%':>6} {'shim%':>6}")
    for start in range(0, max(1, samples.size - win + 1), hop):
        seg = samples[start : start + win]
        t = start / sr
        f0 = latest_f0(seg, sr)
        fmt = latest_formants(seg, sr)
        vq = measure_voice_quality(seg, sr)

        def fmt_hz(x):
            return f"{x:5.0f}" if np.isfinite(x) else "  ---"

        f0s = f"{f0:7.1f}" if np.isfinite(f0) else "    ---"
        jit = f"{vq.jitter_local * 100:6.2f}" if np.isfinite(vq.jitter_local) else "   ---"
        shim = f"{vq.shimmer_local * 100:6.2f}" if np.isfinite(vq.shimmer_local) else "   ---"
        flags = ("J" if vq.jitter_warning else " ") + ("S" if vq.shimmer_warning else " ")
        print(f"{t:5.1f}  {f0s}  {fmt_hz(fmt[0])} {fmt_hz(fmt[1])} {fmt_hz(fmt[2])} "
              f"{fmt_hz(fmt[3])}  {jit} {shim}  {flags}")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    ok1 = part_integrity(path)
    ok2 = part_pacing(path)
    part_analysis(path)
    print("\nRESULT:", "MODULE CHECKS PASS" if (ok1 and ok2) else "MODULE CHECK FAILURES")
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
