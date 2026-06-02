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

from ..pipeline import AnalysisPipeline, PitchSample, SlowSample
from .scrolling_plot import ScrollingPlot

# F0 range modes (ceiling in Hz). Normal tames octave jumps; extended reaches C7.
NORMAL_CEILING = 880.0      # ~A5
EXTENDED_CEILING = 2100.0   # ~C7

# Formant series: key, display name, color.
FORMANT_SERIES = [("f1", "F1", "r"), ("f2", "F2", "g"), ("f3", "F3", "c"), ("f4", "F4", "m")]
FORMANT_Y_MAX = 5000.0


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

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Normal (≤880 Hz)", NORMAL_CEILING)
        self.mode_combo.addItem("Extended (≤2100 Hz, C7)", EXTENDED_CEILING)
        self.mode_combo.setCurrentIndex(
            1 if pipeline.pitch_ceiling >= EXTENDED_CEILING else 0
        )
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        self.status = QtWidgets.QLabel("F0: --")
        controls.addWidget(self.pause_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(QtWidgets.QLabel("Range:"))
        controls.addWidget(self.mode_combo)
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

        # -- formant plot (F1–F4, updated ~1 Hz) --
        self.formant_plot = ScrollingPlot(
            title="Formants (F1–F4)",
            y_label="Hz",
            y_range=(0.0, FORMANT_Y_MAX),
            window_sec=10.0,
        )
        for key, name, color in FORMANT_SERIES:
            self.formant_plot.add_series(
                key, pen=pg.mkPen(color, width=2), name=name, symbol="o", symbol_size=6
            )
        layout.addWidget(self.formant_plot)

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
            elif isinstance(ev, SlowSample):
                for i, (key, _name, _color) in enumerate(FORMANT_SERIES):
                    self.formant_plot.append(key, ev.t, ev.formants[i])
        self.pitch_plot.refresh()
        self.formant_plot.refresh()

    def _on_mode_changed(self, _index: int) -> None:
        ceiling = float(self.mode_combo.currentData())
        # Worker reads pitch_ceiling each loop; updating the attribute suffices.
        self.pipeline.pitch_ceiling = ceiling
        self.pitch_plot.set_y_range(self.pipeline.pitch_floor, ceiling)

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
