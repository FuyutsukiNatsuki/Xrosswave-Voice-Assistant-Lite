"""Microphone audio input.

A thin wrapper around ``sounddevice.InputStream`` that pushes fixed-size,
mono ``float32`` chunks onto a thread-safe queue. The audio callback runs on
sounddevice's own thread, so consumers (analysis layer) pull from the queue
without blocking capture.

This is phase 1 of the pipeline (see Handoff.md). File input will share the
same queue contract in a later step.
"""

from __future__ import annotations

import queue
from typing import List, Optional, Tuple

import numpy as np
import sounddevice as sd

DEFAULT_SAMPLERATE = 44100
DEFAULT_BLOCKSIZE = 2048  # ~46 ms at 44.1 kHz


def list_input_devices() -> List[Tuple[int, str]]:
    """Return ``(index, name)`` for every input-capable audio device.

    Empty if enumeration fails (e.g. no audio backend). Passing ``device=None``
    to :class:`AudioInput` always uses the system default.
    """
    try:
        devices = sd.query_devices()
    except Exception:  # noqa: BLE001
        return []
    return [
        (idx, d["name"])
        for idx, d in enumerate(devices)
        if d.get("max_input_channels", 0) > 0
    ]


class AudioInput:
    """Capture mono audio from an input device into a queue of numpy chunks."""

    def __init__(
        self,
        samplerate: int = DEFAULT_SAMPLERATE,
        blocksize: int = DEFAULT_BLOCKSIZE,
        device: Optional[int] = None,
    ) -> None:
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.device = device
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream: Optional[sd.InputStream] = None

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            # Over/underflow etc. Print for now; the GUI will surface this later.
            print(f"[AudioInput] stream status: {status}")
        # indata is (frames, channels) float32. Take channel 0, copy out of the
        # callback's reused buffer.
        self._queue.put(indata[:, 0].copy())

    def start(self) -> None:
        """Open and start the input stream."""
        if self._stream is not None:
            return
        self._stream = sd.InputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=1,
            dtype="float32",
            device=self.device,
            callback=self._callback,
        )
        self._stream.start()

    def read(self, timeout: Optional[float] = None) -> np.ndarray:
        """Block until the next chunk is available and return it.

        Raises ``queue.Empty`` if ``timeout`` elapses first.
        """
        return self._queue.get(timeout=timeout)

    def stop(self) -> None:
        """Stop and close the stream. Safe to call more than once."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def __enter__(self) -> "AudioInput":
        self.start()
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.stop()
