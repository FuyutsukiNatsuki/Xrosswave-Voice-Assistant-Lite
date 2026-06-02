"""Live microphone F0 readout.

Captures from the default input device for a fixed duration, maintains a short
rolling analysis window, and prints the current F0 a few times per second.
Speak or sing into the mic to see values; silence reads as '---'.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_pitch_mic.py
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import argparse
import queue
import time

import numpy as np

from xvalite.audio.input import AudioInput
from xvalite.analysis.pitch import latest_f0

SAMPLERATE = 44100
WINDOW_SEC = 0.12  # rolling window fed to the analyzer


def main() -> int:
    parser = argparse.ArgumentParser(description="Live mic F0 readout")
    parser.add_argument("--seconds", type=float, default=10.0, help="capture duration")
    parser.add_argument("--device", type=int, default=None, help="input device index")
    args = parser.parse_args()

    window_len = int(SAMPLERATE * WINDOW_SEC)
    buffer = np.zeros(0, dtype=np.float32)

    audio = AudioInput(samplerate=SAMPLERATE, device=args.device)
    audio.start()
    print(f"Recording for {args.seconds:.0f}s — speak or sing into the mic...\n")
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.seconds:
            try:
                chunk = audio.read(timeout=1.0)
            except queue.Empty:
                print("(no audio — check the input device)")
                continue
            buffer = np.concatenate([buffer, chunk])[-window_len:]
            if len(buffer) < window_len:
                continue
            f0 = latest_f0(buffer, SAMPLERATE)
            if np.isnan(f0):
                print("F0:    --- (unvoiced)")
            else:
                print(f"F0: {f0:6.1f} Hz")
    finally:
        audio.stop()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
