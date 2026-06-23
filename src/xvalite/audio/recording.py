"""Recording destination helpers.

Recordings go to a ``rec`` folder next to the executable when frozen, else next
to the repo root in dev. Files are named ``YYYY-MM-DD-nnnn.wav`` where ``nnnn``
is a per-day 4-digit sequence. The pipeline does the actual WAV writing
(44.1 kHz / 24-bit / mono).
"""

from __future__ import annotations

import glob
import os
import sys
from datetime import datetime


def record_dir() -> str:
    if getattr(sys, "frozen", False):  # PyInstaller build
        base = os.path.dirname(sys.executable)
    else:  # dev: repo root (src/xvalite/audio/recording.py -> ../../..)
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    path = os.path.join(base, "rec")
    os.makedirs(path, exist_ok=True)
    return path


def next_record_path(now: datetime | None = None) -> str:
    """Return the next ``YYYY-MM-DD-nnnn.wav`` path (sequence per day)."""
    directory = record_dir()
    today = (now or datetime.now()).strftime("%Y-%m-%d")
    existing = glob.glob(os.path.join(directory, f"{today}-*.wav"))
    seq = 0
    for path in existing:
        tail = os.path.splitext(os.path.basename(path))[0].rsplit("-", 1)[-1]
        if tail.isdigit():
            seq = max(seq, int(tail))
    return os.path.join(directory, f"{today}-{seq + 1:04d}.wav")
