"""Scrolling narrowband spectrogram (waterfall) widget.

Keeps a fixed-width 2-D buffer (time columns × frequency bins) and shows it as a
heatmap via a pyqtgraph ImageItem. New columns are pushed in at the right; the
oldest scroll off the left, matching the line plots' left→right convention.

dB values are mapped through a colormap with auto-leveled contrast.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore

DB_FLOOR = -120.0          # initial fill for empty columns
DISPLAY_RANGE_DB = 70.0    # contrast window below the running peak


class SpectrogramPlot(pg.PlotWidget):
    def __init__(
        self,
        freqs: np.ndarray,
        *,
        window_sec: float = 10.0,
        column_rate_hz: float = 21.5,
        title: str = "Spectrogram (narrowband)",
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self.freqs = np.asarray(freqs, dtype=float)
        self.window_sec = window_sec
        self._n_freq = self.freqs.size
        self._n_cols = max(1, int(window_sec * column_rate_hz))
        self._buffer = np.full((self._n_cols, self._n_freq), DB_FLOOR, dtype=np.float32)
        self._t_max = 0.0
        self._count = 0  # columns received (for initial level scaling)

        self.setTitle(title)
        self.setLabel("left", "frequency", units="Hz")
        self.setLabel("bottom", "time", units="s")
        self.setYRange(0, float(self.freqs[-1]) if self._n_freq else 5000.0)

        self._img = pg.ImageItem()
        self.addItem(self._img)
        self._img.setColorMap(pg.colormap.get("inferno"))
        self._max_freq = float(self.freqs[-1]) if self._n_freq else 5000.0

    def append(self, t: float, db_column: np.ndarray) -> None:
        n = min(db_column.size, self._n_freq)
        self._buffer[:-1] = self._buffer[1:]          # scroll left
        self._buffer[-1, :n] = db_column[:n]
        self._t_max = max(self._t_max, t)
        self._count += 1

    def refresh(self) -> None:
        # Image data is (x=time, y=freq); buffer is already [col, freq].
        self._img.setImage(self._buffer, autoLevels=False)
        peak = float(self._buffer[-min(self._count, self._n_cols) :].max()) if self._count else 0.0
        self._img.setLevels((peak - DISPLAY_RANGE_DB, peak))
        x0 = self._t_max - self.window_sec
        self._img.setRect(QtCore.QRectF(x0, 0.0, self.window_sec, self._max_freq))
        self.setXRange(x0, self._t_max, padding=0)

    def clear_data(self) -> None:
        self._buffer[:] = DB_FLOOR
        self._t_max = 0.0
        self._count = 0
        self._img.clear()
