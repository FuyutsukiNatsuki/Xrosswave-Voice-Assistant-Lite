"""Verify the analysis pipeline integration layer.

Part 1 — Throughput & sanity (fast):
    Run a file source (non-realtime) through the pipeline, drain the result
    stream, and check we get a continuous F0 stream plus ~1 slow sample per
    second, with sane values on the real recording.

Part 2 — Pause semantics (real time):
    With a real-time file source, confirm that pausing halts the result stream
    and resuming restarts it.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_pipeline.py [path]
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import sys
import time

import numpy as np
import soundfile as sf

from xvalite.audio.file_input import FileInput
from xvalite.audio.input import DEFAULT_SAMPLERATE
from xvalite.pipeline import AnalysisPipeline, PitchSample, SlowSample

DEFAULT_PATH = r"C:\XVALite\testdata\test.wav"


def part_throughput(path: str) -> bool:
    print("== 1. Throughput & sanity (non-realtime) ==")
    duration = sf.info(path).duration
    src = FileInput(path, samplerate=DEFAULT_SAMPLERATE, realtime=False)
    pipe = AnalysisPipeline(src, samplerate=DEFAULT_SAMPLERATE)
    pipe.start()

    events = []
    # Drain until the source is finished and the queue is empty.
    while not pipe.is_finished:
        events.extend(pipe.drain())
        time.sleep(0.02)
    time.sleep(0.1)
    events.extend(pipe.drain())
    pipe.stop()

    pitch = [e for e in events if isinstance(e, PitchSample)]
    slow = [e for e in events if isinstance(e, SlowSample)]
    voiced = [e.f0 for e in pitch if np.isfinite(e.f0)]
    expected_slow = int(duration)  # ~1 per second

    print(f"duration={duration:.2f}s  pitch_samples={len(pitch)}  slow_samples={len(slow)}"
          f"  (expected slow ~{expected_slow})")
    if voiced:
        print(f"F0 voiced: median={np.median(voiced):.1f} Hz  "
              f"range=[{min(voiced):.0f}, {max(voiced):.0f}]")
    if slow:
        last = slow[-1]
        print(f"last slow @ t={last.t:.1f}s  F1-F4={np.round(last.formants).tolist()}  "
              f"jitter={last.voice_quality.jitter_local:.3%}  "
              f"shimmer={last.voice_quality.shimmer_local:.3%}")

    checks = {
        "got pitch samples": len(pitch) > 10,
        "slow count ~ duration": abs(len(slow) - expected_slow) <= 1,
        "F0 in plausible voice range": bool(voiced) and 50 <= np.median(voiced) <= 500,
        "timestamps monotonic": all(
            events[i].t <= events[i + 1].t for i in range(len(events) - 1)
        ),
    }
    ok = True
    for name, passed in checks.items():
        ok = ok and passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}")
    return ok


def part_pause(path: str) -> bool:
    print("\n== 2. Pause semantics (real time) ==")
    src = FileInput(path, samplerate=DEFAULT_SAMPLERATE, realtime=True)
    pipe = AnalysisPipeline(src, samplerate=DEFAULT_SAMPLERATE)
    pipe.start()

    def count_over(seconds: float) -> int:
        end = time.monotonic() + seconds
        n = 0
        while time.monotonic() < end:
            n += len(pipe.drain())
            time.sleep(0.05)
        return n

    running = count_over(1.0)
    pipe.pause()
    pipe.drain()  # clear anything already queued
    time.sleep(0.1)
    paused = count_over(1.0)
    pipe.resume()
    resumed = count_over(1.0)
    pipe.stop()

    print(f"events while running={running}, while paused={paused}, after resume={resumed}")
    checks = {
        "events flow while running": running > 0,
        "no events while paused": paused == 0,
        "events resume after resume()": resumed > 0,
    }
    ok = True
    for name, passed in checks.items():
        ok = ok and passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}")
    return ok


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    ok1 = part_throughput(path)
    ok2 = part_pause(path)
    print("\nRESULT:", "ALL PASS" if (ok1 and ok2) else "FAILURES PRESENT")
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    raise SystemExit(main())
