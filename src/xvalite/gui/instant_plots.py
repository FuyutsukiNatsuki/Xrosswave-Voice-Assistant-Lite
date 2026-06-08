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
    # Auto-gain: the Y axis tracks the signal so quiet input still fills the view.
    MIN_HALF_SPAN = 0.02   # don't zoom in past this (keeps silence from blowing up)
    DECAY = 0.92           # how fast the range shrinks when the signal gets quieter

    def __init__(self, samplerate: int, window_size: int = 2048, parent=None) -> None:
        super().__init__(parent=parent)
        self.samplerate = samplerate
        self.setTitle("Waveform (oscilloscope)")
        self.setLabel("left", "amplitude")
        self.setLabel("bottom", "time", units="ms")
        self.showGrid(x=True, y=True, alpha=0.3)
        self._curve = self.plot(pen=pg.mkPen("#7fdfff", width=1))
        self._x = np.arange(window_size) / samplerate * 1000.0
        self._half_span = self.MIN_HALF_SPAN
        self.setYRange(-self._half_span, self._half_span)
        self.setXRange(0.0, float(self._x[-1]) if self._x.size else 1.0, padding=0)

    def set_frame(self, samples: np.ndarray) -> None:
        n = samples.size
        x = self._x[:n] if n <= self._x.size else np.arange(n) / self.samplerate * 1000.0
        self._curve.setData(x, samples)
        # Fast attack, slow decay so the trace fills ~80% of the pane.
        peak = float(np.max(np.abs(samples))) if n else 0.0
        target = max(peak * 1.25, self.MIN_HALF_SPAN)
        self._half_span = max(target, self._half_span * self.DECAY)
        self.setYRange(-self._half_span, self._half_span)

    def clear_data(self) -> None:
        self._curve.setData([], [])
        self._half_span = self.MIN_HALF_SPAN
        self.setYRange(-self._half_span, self._half_span)


class SpectrumPlot(pg.PlotWidget):
    def __init__(
        self,
        freqs: np.ndarray,
        peak_hold: bool = True,
        min_freq: float = 10.0,
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self.setTitle("Spectrum (instantaneous)")
        self.setLabel("left", "level", units="dB")
        self.setLabel("bottom", "frequency", units="Hz")
        self.setLogMode(x=True, y=False)  # log frequency axis (WaveSpectra style)
        self.showGrid(x=True, y=True, alpha=0.3)

        f = np.asarray(freqs, dtype=float)
        # Keep bins at/above the display floor (drops DC and the very-low region
        # that otherwise eats most of the log axis width).
        self._mask = f >= min_freq
        self._freqs = f[self._mask]
        self._peak_hold = peak_hold
        self._peak: np.ndarray | None = None
        self._gmax = -60.0

        self._peak_curve = self.plot(pen=pg.mkPen("#ff7777", width=1))  # dim peak-hold
        self._cur_curve = self.plot(pen=pg.mkPen("#ffdd00", width=1))   # current
        if self._freqs.size:
            hi = float(self._freqs[-1])
            # Fixed log range from min_freq to the top bin; don't let data auto-refit it.
            self.setXRange(np.log10(min_freq), np.log10(hi), padding=0)
            self.setLimits(xMin=np.log10(min_freq), xMax=np.log10(hi))
            self.enableAutoRange(axis="x", enable=False)

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
