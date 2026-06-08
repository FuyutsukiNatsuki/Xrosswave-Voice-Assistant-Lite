"""Instant (non-scrolling) views, à la WaveSpectra.

* ``WaveformPlot`` — oscilloscope: amplitude vs time for the most recent window.
* ``SpectrumPlot`` — instantaneous FFT magnitude (dB) vs frequency, log X axis,
  with an optional peak-hold trace.

Both replace their data each refresh (they show "now", not a scrolling history).
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg


class WaveformPlot(pg.PlotWidget):
    def __init__(self, samplerate: int, window_size: int = 1024, parent=None) -> None:
        super().__init__(parent=parent)
        self.samplerate = samplerate
        self.setTitle("Waveform (oscilloscope)")
        self.setLabel("left", "amplitude")
        self.setLabel("bottom", "time", units="ms")
        self.setYRange(-1.0, 1.0)
        self.showGrid(x=True, y=True, alpha=0.3)
        self._curve = self.plot(pen=pg.mkPen("#7fdfff", width=1))
        self._x = np.arange(window_size) / samplerate * 1000.0
        self.setXRange(0.0, float(self._x[-1]) if self._x.size else 1.0, padding=0)

    def set_frame(self, samples: np.ndarray) -> None:
        n = samples.size
        x = self._x[:n] if n <= self._x.size else np.arange(n) / self.samplerate * 1000.0
        self._curve.setData(x, samples)

    def clear_data(self) -> None:
        self._curve.setData([], [])


class SpectrumPlot(pg.PlotWidget):
    def __init__(self, freqs: np.ndarray, peak_hold: bool = True, parent=None) -> None:
        super().__init__(parent=parent)
        self.setTitle("Spectrum (instantaneous)")
        self.setLabel("left", "level", units="dB")
        self.setLabel("bottom", "frequency", units="Hz")
        self.setLogMode(x=True, y=False)  # log frequency axis (WaveSpectra style)
        self.showGrid(x=True, y=True, alpha=0.3)

        f = np.asarray(freqs, dtype=float)
        self._mask = f > 0.0  # drop the DC bin (log axis can't show 0 Hz)
        self._freqs = f[self._mask]
        self._peak_hold = peak_hold
        self._peak: np.ndarray | None = None
        self._gmax = -60.0

        self._peak_curve = self.plot(pen=pg.mkPen("#ff7777", width=1))  # dim peak-hold
        self._cur_curve = self.plot(pen=pg.mkPen("#ffdd00", width=1))   # current
        if self._freqs.size:
            lo = np.log10(max(20.0, self._freqs[0]))
            self.setXRange(lo, np.log10(self._freqs[-1]), padding=0)

    def set_peak_hold(self, on: bool) -> None:
        self._peak_hold = on
        if not on:
            self._peak = None
            self._peak_curve.setData([], [])

    def set_column(self, db: np.ndarray) -> None:
        d = np.asarray(db, dtype=float)[self._mask]
        self._cur_curve.setData(self._freqs, d)
        peak_now = float(np.max(d)) if d.size else self._gmax
        if peak_now > self._gmax:
            self._gmax = peak_now
        self.setYRange(self._gmax - 100.0, self._gmax + 6.0)
        if self._peak_hold:
            self._peak = d if self._peak is None else np.maximum(self._peak, d)
            self._peak_curve.setData(self._freqs, self._peak)

    def clear_data(self) -> None:
        self._peak = None
        self._gmax = -60.0
        self._cur_curve.setData([], [])
        self._peak_curve.setData([], [])
