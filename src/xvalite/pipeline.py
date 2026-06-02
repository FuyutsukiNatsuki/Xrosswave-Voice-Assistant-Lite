"""Analysis pipeline: input source -> background analysis -> result stream.

Ties an audio source (``AudioInput`` or ``FileInput`` — anything with
``start``/``read``/``stop`` and a ``None`` end-of-stream sentinel) to the
analysis layer and runs it on a background thread. Two cadences:

* **pitch (F0)** — computed on every chunk (high frequency), and
* **slow metrics (F1-F4 + jitter/shimmer)** — computed once per second.

Timestamps are derived from the cumulative sample count (``total / samplerate``),
not wall-clock, so the result stream lines up with audio time whether the source
runs in real time or as fast as possible.

Results are delivered two ways:
* a thread-safe FIFO drained by :meth:`drain` (captures every event — use this
  to feed scrolling graphs), and
* :meth:`latest_pitch` / :meth:`latest_slow` snapshots (for one-shot readouts).

Pause stops analysis *and* discards incoming audio (per the design decision:
audio during pause is not analyzed; resume continues from the stop point with a
cleared buffer).
"""

from __future__ import annotations

import math
import queue
import threading
from dataclasses import dataclass
from typing import List, Optional, Protocol, Union

import numpy as np

from .analysis.formant import latest_formants
from .analysis.pitch import DEFAULT_PITCH_FLOOR, latest_f0
from .analysis.spectrogram import (
    DEFAULT_FFT_SIZE,
    DEFAULT_MAX_FREQ,
    column_frequencies,
    spectrum_column,
)
from .analysis.voice_quality import VoiceQuality, measure_voice_quality
from .audio.input import DEFAULT_SAMPLERATE

# F0 tracking ceiling for the app. Raised well above speech so high singing
# (up to ~C7) is tracked and plottable. Voice-quality periodicity uses its own,
# more conservative ceiling (see analysis.voice_quality) and is unaffected.
DEFAULT_F0_TRACK_CEILING = 2100.0  # ~C7 (2093 Hz)

# Input dead zone: windows quieter than this (RMS, dBFS) are treated as silence
# and emit NaN, instead of letting the tracker invent pitch/formants from the
# noise floor. Measured on real voice: speech sits around -20 dBFS while silent
# gaps fall below -44 dBFS, so -40 cleanly separates them with margin.
DEFAULT_SILENCE_DB = -40.0


def _dbfs(samples: np.ndarray) -> float:
    """RMS level of a window in dBFS (full-scale = 0 dB). -inf for true silence."""
    if samples.size == 0:
        return -math.inf
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    return -math.inf if rms <= 0.0 else 20.0 * math.log10(rms)


class AudioSource(Protocol):
    """Structural type shared by AudioInput and FileInput."""

    def start(self) -> None: ...
    def read(self, timeout: Optional[float] = None) -> Optional[np.ndarray]: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class PitchSample:
    """High-frequency F0 reading. ``f0`` is NaN when unvoiced."""

    t: float
    f0: float


@dataclass(frozen=True)
class FormantSample:
    """Formants F1-F4 at the (fast) formant cadence. NaN where undefined."""

    t: float
    formants: np.ndarray  # length 4, Hz


@dataclass(frozen=True)
class VoiceQualitySample:
    """Jitter/shimmer at the (slow) ~1 Hz cadence (needs many glottal cycles)."""

    t: float
    voice_quality: VoiceQuality


@dataclass(frozen=True)
class SpectrogramColumn:
    """One narrowband spectrogram column (dB per frequency bin) at chunk rate."""

    t: float
    db: np.ndarray  # aligned with AnalysisPipeline.spectrogram_freqs


Event = Union[PitchSample, FormantSample, VoiceQualitySample, SpectrogramColumn]


class AnalysisPipeline:
    """Run analysis on a source in the background; expose a result stream."""

    def __init__(
        self,
        source: AudioSource,
        samplerate: int = DEFAULT_SAMPLERATE,
        pitch_window_sec: float = 0.12,
        formant_window_sec: float = 0.1,
        formant_interval_sec: float = 0.0,  # 0 = every chunk (~21.5 Hz at default blocksize)
        vq_window_sec: float = 1.0,
        vq_interval_sec: float = 1.0,
        pitch_floor: float = DEFAULT_PITCH_FLOOR,
        pitch_ceiling: float = DEFAULT_F0_TRACK_CEILING,
        silence_db: float = DEFAULT_SILENCE_DB,
        spectrogram_fft_size: int = DEFAULT_FFT_SIZE,
        spectrogram_max_freq: float = DEFAULT_MAX_FREQ,
        spectrogram_interval_sec: float = 0.0,  # 0 = every chunk
    ) -> None:
        self.source = source
        self.samplerate = samplerate
        # Public so the GUI can match its F0 axis to the tracked range.
        self.pitch_floor = pitch_floor
        self.pitch_ceiling = pitch_ceiling
        # Public so it can be tuned at runtime (input dead zone, dBFS).
        self.silence_db = silence_db

        # Three cadences. Formants run fast (~20 Hz at the default chunk size) on
        # a short window; voice quality stays at ~1 Hz on a 1 s window because
        # jitter/shimmer need many glottal cycles to be stable.
        self._pitch_win = int(samplerate * pitch_window_sec)
        self._formant_win = int(samplerate * formant_window_sec)
        self._formant_interval = int(samplerate * formant_interval_sec)
        self._vq_win = int(samplerate * vq_window_sec)
        self._vq_interval = int(samplerate * vq_interval_sec)

        # Narrowband spectrogram: long FFT window, emitted at chunk rate.
        self._spec_fft = spectrogram_fft_size
        self._spec_max_freq = spectrogram_max_freq
        self._spec_interval = int(samplerate * spectrogram_interval_sec)
        # Public frequency axis so the GUI can scale the waterfall's Y axis.
        self.spectrogram_freqs = column_frequencies(
            samplerate, spectrogram_fft_size, spectrogram_max_freq
        )

        self._keep = max(self._pitch_win, self._formant_win, self._vq_win, self._spec_fft)

        self._results: "queue.Queue[Event]" = queue.Queue()
        self._lock = threading.Lock()
        self._latest_pitch: Optional[PitchSample] = None
        self._latest_formant: Optional[FormantSample] = None
        self._latest_vq: Optional[VoiceQualitySample] = None
        self._latest_spec: Optional[SpectrogramColumn] = None

        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._finished = threading.Event()
        self._error: Optional[str] = None  # set if the worker dies unexpectedly

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        if self._thread is not None:
            return
        self.source.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.source.stop()

    def pause(self) -> None:
        self._paused.set()
        # If the source can pause itself (e.g. file playback), freeze it too.
        if hasattr(self.source, "pause"):
            self.source.pause()

    def resume(self) -> None:
        self._paused.clear()
        if hasattr(self.source, "resume"):
            self.source.resume()

    # -- state -------------------------------------------------------------
    @property
    def is_paused(self) -> bool:
        return self._paused.is_set()

    @property
    def is_finished(self) -> bool:
        return self._finished.is_set()

    @property
    def error(self) -> Optional[str]:
        """Error message if the worker stopped unexpectedly, else None."""
        return self._error

    # -- results -----------------------------------------------------------
    def drain(self) -> List[Event]:
        """Pop and return all results buffered since the last call."""
        out: List[Event] = []
        while True:
            try:
                out.append(self._results.get_nowait())
            except queue.Empty:
                break
        return out

    def latest_pitch(self) -> Optional[PitchSample]:
        with self._lock:
            return self._latest_pitch

    def latest_formant(self) -> Optional[FormantSample]:
        with self._lock:
            return self._latest_formant

    def latest_voice_quality(self) -> Optional[VoiceQualitySample]:
        with self._lock:
            return self._latest_vq

    def latest_spectrogram(self) -> Optional[SpectrogramColumn]:
        with self._lock:
            return self._latest_spec

    # -- worker ------------------------------------------------------------
    def _run(self) -> None:
        buffer = np.zeros(0, dtype=np.float32)
        total = 0           # cumulative analyzed samples (the analysis clock)
        last_formant = 0    # sample count at last formant analysis
        last_vq = 0         # sample count at last voice-quality analysis
        last_spec = 0       # sample count at last spectrogram column
        while not self._stop.is_set():
            try:
                chunk = self.source.read(timeout=0.2)
            except queue.Empty:
                continue
            except Exception as exc:  # source failed mid-stream
                self._error = f"audio source error: {exc}"
                self._finished.set()
                break
            if chunk is None:  # end of stream (file source)
                self._finished.set()
                break
            if self._paused.is_set():
                # Discard audio while paused and reset the rolling buffer so
                # the next analysis after resume starts clean.
                buffer = np.zeros(0, dtype=np.float32)
                continue

            total += chunk.size
            buffer = np.concatenate([buffer, chunk])[-self._keep :]
            t = total / self.samplerate

            # Analysis errors on a bad window should skip that chunk, not kill
            # the worker. Parselmouth's formant/VQ calls already guard internally.
            try:
                if buffer.size >= self._pitch_win:
                    window = buffer[-self._pitch_win :]
                    if _dbfs(window) < self.silence_db:
                        f0 = float("nan")  # below the dead zone: treat as silence
                    else:
                        f0 = latest_f0(
                            window,
                            self.samplerate,
                            pitch_floor=self.pitch_floor,
                            pitch_ceiling=self.pitch_ceiling,
                        )
                    self._emit(PitchSample(t, f0))

                if buffer.size >= self._formant_win and (total - last_formant) >= self._formant_interval:
                    last_formant = total
                    window = buffer[-self._formant_win :]
                    if _dbfs(window) < self.silence_db:
                        formants = np.full(4, np.nan)
                    else:
                        formants = latest_formants(window, self.samplerate)
                    self._emit(FormantSample(t, formants))

                if buffer.size >= self._vq_win and (total - last_vq) >= self._vq_interval:
                    last_vq = total
                    window = buffer[-self._vq_win :]
                    if _dbfs(window) < self.silence_db:
                        vq = VoiceQuality(float("nan"), float("nan"))
                    else:
                        vq = measure_voice_quality(window, self.samplerate)
                    self._emit(VoiceQualitySample(t, vq))

                if buffer.size >= self._spec_fft and (total - last_spec) >= self._spec_interval:
                    last_spec = total
                    db = spectrum_column(
                        buffer, self.samplerate, self._spec_fft, self._spec_max_freq
                    )
                    self._emit(SpectrogramColumn(t, db))
            except Exception:  # noqa: BLE001 — skip this chunk, keep streaming
                continue

        self.source.stop()

    def _emit(self, event: Event) -> None:
        self._results.put(event)
        with self._lock:
            if isinstance(event, PitchSample):
                self._latest_pitch = event
            elif isinstance(event, FormantSample):
                self._latest_formant = event
            elif isinstance(event, VoiceQualitySample):
                self._latest_vq = event
            else:
                self._latest_spec = event
