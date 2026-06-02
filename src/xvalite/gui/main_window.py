"""Main application window (phase 2A: pitch graph only).

A QTimer polls the pipeline's result stream and feeds the scrolling pitch plot.
Pause/Resume drives the pipeline's pause (which stops analysis); since the view
follows the latest data timestamp, the graph freezes while paused with no extra
handling. Formant/jitter widgets are added in later steps.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from ..pipeline import AnalysisPipeline, PitchSample
from .scrolling_plot import ScrollingPlot


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, pipeline: AnalysisPipeline, refresh_ms: int = 33) -> None:
        super().__init__()
        self.pipeline = pipeline
        self.setWindowTitle("XVALite — voice trainer")

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # -- controls --
        controls = QtWidgets.QHBoxLayout()
        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self._on_pause_toggled)
        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.clicked.connect(self._on_stop)
        self.status = QtWidgets.QLabel("F0: --")
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        controls.addStretch(1)
        controls.addWidget(self.status)
        layout.addLayout(controls)

        # -- pitch plot (axis follows the pipeline's tracked F0 range) --
        self.pitch_plot = ScrollingPlot(
            title="Pitch (F0)",
            y_label="Hz",
            y_range=(pipeline.pitch_floor, pipeline.pitch_ceiling),
            window_sec=10.0,
        )
        self.pitch_plot.add_series("f0", pen=pg.mkPen("y", width=2), name="F0")
        layout.addWidget(self.pitch_plot)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        self.pipeline.start()
        self._timer.start()

    def _on_tick(self) -> None:
        for ev in self.pipeline.drain():
            if isinstance(ev, PitchSample):
                self.pitch_plot.append("f0", ev.t, ev.f0)
                if np.isfinite(ev.f0):
                    self.status.setText(f"F0: {ev.f0:.1f} Hz")
        self.pitch_plot.refresh()

    def _on_pause_toggled(self, checked: bool) -> None:
        if checked:
            self.pipeline.pause()
            self.pause_btn.setText("Resume")
        else:
            self.pipeline.resume()
            self.pause_btn.setText("Pause")

    def _on_stop(self) -> None:
        self._timer.stop()
        self.pipeline.stop()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        self._timer.stop()
        self.pipeline.stop()
        super().closeEvent(event)
