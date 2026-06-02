"""Audio file input.

Streams an audio file as mono ``float32`` chunks through the *same queue
contract* as :class:`~xvalite.audio.input.AudioInput`, so the analysis layer is
agnostic to whether audio comes from the mic or a file. Per the design decision
(see Handoff.md), playback is paced in real time by default so the on-screen
behavior matches live input.

End-of-stream is signaled by putting ``None`` on the queue (the mic source never
ends; a file does). Consumers should treat a ``None`` read as "finished".

Stereo files are down-mixed to mono; differing sample rates are linearly
resampled to the target rate.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Optional

import numpy as np
import soundfile as sf

from .input import DEFAULT_BLOCKSIZE, DEFAULT_SAMPLERATE


class FileInput:
    """Stream an audio file as mono float32 chunks via a queue.

    Mirrors ``AudioInput``'s ``start`` / ``read`` / ``stop`` interface. A
    ``None`` sentinel is enqueued once the file is exhausted.
    """

    def __init__(
        self,
        path: str,
        samplerate: int = DEFAULT_SAMPLERATE,
        blocksize: int = DEFAULT_BLOCKSIZE,
        realtime: bool = True,
    ) -> None:
        self.path = path
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.realtime = realtime
        self._queue: "queue.Queue[Optional[np.ndarray]]" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def _load(self) -> np.ndarray:
        """Read the file, down-mix to mono, and resample to the target rate."""
        data, sr = sf.read(self.path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)  # down-mix channels
        if sr != self.samplerate:
            mono = self._resample(mono, sr, self.samplerate)
        return np.ascontiguousarray(mono, dtype=np.float32)

    @staticmethod
    def _resample(x: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
        """Linear-interpolation resample. Adequate for speech-rate analysis."""
        n_out = int(round(x.size * sr_out / sr_in))
        t_in = np.arange(x.size) / sr_in
        t_out = np.arange(n_out) / sr_out
        return np.interp(t_out, t_in, x).astype(np.float32)

    def _worker(self, samples: np.ndarray) -> None:
        period = self.blocksize / self.samplerate
        next_deadline = time.monotonic()
        for start in range(0, samples.size, self.blocksize):
            if self._stop.is_set():
                break
            self._queue.put(samples[start : start + self.blocksize].copy())
            if self.realtime:
                next_deadline += period
                sleep_for = next_deadline - time.monotonic()
                if sleep_for > 0:
                    time.sleep(sleep_for)
        self._queue.put(None)  # end-of-stream sentinel

    def start(self) -> None:
        """Load the file and begin streaming chunks on a background thread."""
        if self._thread is not None:
            return
        samples = self._load()
        self._thread = threading.Thread(
            target=self._worker, args=(samples,), daemon=True
        )
        self._thread.start()

    def read(self, timeout: Optional[float] = None) -> Optional[np.ndarray]:
        """Return the next chunk, or ``None`` at end-of-stream.

        Raises ``queue.Empty`` if ``timeout`` elapses first.
        """
        return self._queue.get(timeout=timeout)

    def stop(self) -> None:
        """Stop streaming. Safe to call more than once."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def __enter__(self) -> "FileInput":
        self.start()
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.stop()
