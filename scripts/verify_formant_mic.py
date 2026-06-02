"""Live microphone formant (F1-F4) readout.

Captures from the default input device and prints F1-F4 about once per second,
matching the quasi-realtime cadence the app will use. Sustain a vowel (e.g.
"ah", "ee", "oo") to see stable values; silence reads as '---'.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_formant_mic.py
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import argparse
import queue
import time

import numpy as np

from xvalite.audio.input import AudioInput
from xvalite.analysis.formant import latest_formants

SAMPLERATE = 44100
WINDOW_SEC = 1.0  # 1-second analysis window (quasi-realtime cadence)


def main() -> int:
    parser = argparse.ArgumentParser(description="Live mic formant readout")
    parser.add_argument("--seconds", type=float, default=10.0, help="capture duration")
    parser.add_argument("--device", type=int, default=None, help="input device index")
    args = parser.parse_args()

    window_len = int(SAMPLERATE * WINDOW_SEC)
    buffer = np.zeros(0, dtype=np.float32)

    audio = AudioInput(samplerate=SAMPLERATE, device=args.device)
    audio.start()
    print(f"Recording for {args.seconds:.0f}s — sustain a vowel into the mic...\n")
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
            f = latest_formants(buffer, SAMPLERATE)
            if np.all(np.isnan(f)):
                print("F1-F4:    --- (no clear formants)")
            else:
                vals = "  ".join(
                    f"F{i + 1}={f[i]:6.1f}" if not np.isnan(f[i]) else f"F{i + 1}=  ---"
                    for i in range(4)
                )
                print(vals + "  Hz")
    finally:
        audio.stop()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
