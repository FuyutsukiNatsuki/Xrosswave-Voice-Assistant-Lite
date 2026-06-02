"""A reusable scrolling time-series plot.

Holds one or more named series in ring buffers keyed by timestamp. The view
shows the most recent ``window_sec`` seconds: the trace grows left→right and
older samples scroll off the left edge, driven by the latest data timestamp
(not wall-clock), so the view freezes naturally when no new data arrives
(e.g. while paused).

NaN values are kept in the buffer and rendered as gaps (``connect='finite'``),
which is how unvoiced frames / undefined formants appear.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, Dict, Tuple

import pyqtgraph as pg
from PySide6 import QtCore


class ScrollingPlot(pg.PlotWidget):
    def __init__(
        self,
        *,
        title: str,
        y_label: str,
        y_range: Tuple[float, float],
        window_sec: float = 10.0,
        parent=None,
    ) -> None:
        super().__init__(parent=parent)
        self.window_sec = window_sec
        self._t_max = 0.0
        self._series: Dict[str, Tuple[Deque, Deque, pg.PlotDataItem]] = {}

        self.setTitle(title)
        self.setLabel("left", y_label)
        self.setLabel("bottom", "time", units="s")
        self.setYRange(*y_range)
        self.showGrid(x=True, y=True, alpha=0.3)
        self.addLegend(offset=(-10, 10))

        self._init_hover_readout()

    def _init_hover_readout(self) -> None:
        """Crosshair line + label that follows the mouse, showing Hz at cursor."""
        self._hline = pg.InfiniteLine(
            angle=0, movable=False, pen=pg.mkPen("#888", style=QtCore.Qt.DashLine)
        )
        self._hline.setZValue(50)
        self.addItem(self._hline, ignoreBounds=True)
        self._cursor_label = pg.TextItem(color="#ddd", anchor=(0, 1))
        self._cursor_label.setZValue(51)
        self.addItem(self._cursor_label, ignoreBounds=True)
        self._hline.hide()
        self._cursor_label.hide()
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, scene_pos) -> None:
        if not self.sceneBoundingRect().contains(scene_pos):
            self._hline.hide()
            self._cursor_label.hide()
            return
        point = self.plotItem.vb.mapSceneToView(scene_pos)
        self._hline.setPos(point.y())
        self._cursor_label.setText(f"{point.y():.0f} Hz")
        self._cursor_label.setPos(point.x(), point.y())
        self._hline.show()
        self._cursor_label.show()

    def add_series(
        self,
        key: str,
        pen,
        name: str | None = None,
        symbol: str | None = None,
        symbol_size: int = 7,
    ) -> None:
        kwargs = dict(pen=pen, name=name, connect="finite")
        if symbol is not None:
            kwargs.update(
                symbol=symbol,
                symbolSize=symbol_size,
                symbolPen=pen,
                symbolBrush=pen.color(),
            )
        curve = self.plot(**kwargs)
        self._series[key] = (deque(), deque(), curve)

    def set_y_range(self, lo: float, hi: float) -> None:
        self.setYRange(lo, hi)

    def clear_data(self) -> None:
        """Drop all buffered points (e.g. when switching input source)."""
        for tq, yq, curve in self._series.values():
            tq.clear()
            yq.clear()
            curve.setData([], [])
        self._t_max = 0.0

    def append(self, key: str, t: float, value: float) -> None:
        tq, yq, _ = self._series[key]
        tq.append(t)
        yq.append(float(value))
        self._t_max = max(self._t_max, t)
        cutoff = self._t_max - self.window_sec
        while tq and tq[0] < cutoff:
            tq.popleft()
            yq.popleft()

    def refresh(self) -> None:
        for tq, yq, curve in self._series.values():
            ys = list(yq)
            # An all-NaN window (e.g. sustained silence) makes pyqtgraph's symbol
            # bounds spam "All-NaN slice" warnings; nothing to draw, so send empty.
            if ys and not any(math.isfinite(v) for v in ys):
                curve.setData([], [])
            else:
                curve.setData(list(tq), ys)
        if self._t_max > 0:
            self.setXRange(self._t_max - self.window_sec, self._t_max, padding=0)

    def point_count(self, key: str) -> int:
        return len(self._series[key][0])
