"""Verify pipeline recording writes a valid 24-bit/44.1k/mono WAV.

Drives a file source through the pipeline with recording armed, then checks the
output file's format and length. (The GUI records the mic; the mechanism is the
same — this exercises it deterministically without a microphone.)

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\verify_recording.py [path.wav]
"""

import _bootstrap  # noqa: F401

import os
import sys
import tempfile
import time

import soundfile as sf

from xvalite.audio.file_input import FileInput
from xvalite.audio.input import DEFAULT_SAMPLERATE
from xvalite.pipeline import AnalysisPipeline

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\XVALite\testdata\test.wav"
OUT = os.path.join(tempfile.gettempdir(), "xvalite_rec_test.wav")


def main() -> int:
    if os.path.exists(OUT):
        os.remove(OUT)
    src_frames = sf.info(SRC).frames

    source = FileInput(SRC, samplerate=DEFAULT_SAMPLERATE, realtime=False)
    pipe = AnalysisPipeline(source, samplerate=DEFAULT_SAMPLERATE)
    pipe.start()
    pipe.start_recording(OUT)
    while not pipe.is_finished:
        pipe.drain()
        time.sleep(0.02)
    pipe.drain()
    pipe.stop_recording()
    pipe.stop()

    info = sf.info(OUT)
    print(f"source frames={src_frames}, recorded frames={info.frames}")
    print(f"samplerate={info.samplerate}  channels={info.channels}  subtype={info.subtype}")

    checks = {
        "file created": os.path.exists(OUT) and info.frames > 0,
        "samplerate 44100": info.samplerate == 44100,
        "mono": info.channels == 1,
        "24-bit PCM": info.subtype == "PCM_24",
        "length ~= source": abs(info.frames - src_frames) <= DEFAULT_SAMPLERATE,  # ≤1 s slack
    }
    ok = True
    for name, passed in checks.items():
        ok = ok and passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}")
    print("\nRESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
