"""Live microphone jitter/shimmer readout.

Captures from the default input device and prints local jitter/shimmer about
once per second, flagging values above the fixed warning thresholds. Sustain a
steady vowel for stable readings; silence/unvoiced reads as '---'.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_voice_quality_mic.py
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import argparse
import queue
import time

import numpy as np

from xvalite.audio.input import AudioInput
from xvalite.analysis.voice_quality import measure_voice_quality

SAMPLERATE = 44100
WINDOW_SEC = 1.0  # 1-second analysis window (quasi-realtime cadence)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live mic jitter/shimmer readout")
    parser.add_argument("--seconds", type=float, default=10.0, help="capture duration")
    parser.add_argument("--device", type=int, default=None, help="input device index")
    args = parser.parse_args()

    window_len = int(SAMPLERATE * WINDOW_SEC)
    buffer = np.zeros(0, dtype=np.float32)

    audio = AudioInput(samplerate=SAMPLERATE, device=args.device)
    audio.start()
    print(f"Recording for {args.seconds:.0f}s — sustain a steady vowel...\n")
    start = time.monotonic()
    next_report = start + 1.0
    try:
        while time.monotonic() - start < args.seconds:
            try:
                chunk = audio.read(timeout=1.0)
            except queue.Empty:
                print("(no audio — check the input device)")
                continue
            buffer = np.concatenate([buffer, chunk])[-window_len:]
            now = time.monotonic()
            if now < next_report or len(buffer) < window_len:
                continue
            next_report = now + 1.0
            vq = measure_voice_quality(buffer, SAMPLERATE)
            if not np.isfinite(vq.jitter_local) and not np.isfinite(vq.shimmer_local):
                print("jitter/shimmer:    --- (unvoiced)")
                continue
            j_flag = " !WARN" if vq.jitter_warning else ""
            s_flag = " !WARN" if vq.shimmer_warning else ""
            print(
                f"jitter={vq.jitter_local:6.3%}{j_flag:6}   "
                f"shimmer={vq.shimmer_local:6.3%}{s_flag:6}"
            )
    finally:
        audio.stop()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
