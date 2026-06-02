"""Main application window.

Owns the analysis pipeline lifecycle: the user picks an input source
(microphone or audio file), then Start builds the source + pipeline and a QTimer
polls the result stream into the scrolling pitch and formant plots and the
voice-quality readout. Pause drives the pipeline's pause (analysis stops; the
timestamp-driven views freeze). The F0 range dropdown switches the tracking
ceiling live.
"""

from __future__ import annotations

import os

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtWidgets

from ..analysis.voice_quality import JITTER_LOCAL_WARN, SHIMMER_LOCAL_WARN
from ..audio.file_input import FileInput
from ..audio.input import DEFAULT_SAMPLERATE, AudioInput
from ..pipeline import (
    DEFAULT_F0_TRACK_CEILING,
    DEFAULT_SILENCE_DB,
    AnalysisPipeline,
    FormantSample,
    PitchSample,
    VoiceQualitySample,
)
from .scrolling_plot import ScrollingPlot

# Voice-quality readout styles.
_VQ_BASE = "padding: 2px 8px; border-radius: 3px; font-weight: bold;"
VQ_STYLE_OK = _VQ_BASE + "color: #ddd;"
VQ_STYLE_WARN = _VQ_BASE + "color: white; background: #c0392b;"
VQ_STYLE_IDLE = _VQ_BASE + "color: #888;"

# F0 range modes (ceiling in Hz). Normal tames octave jumps; extended reaches C7.
NORMAL_CEILING = 880.0      # ~A5
EXTENDED_CEILING = 2100.0   # ~C7

# Formant series: key, display name, color.
FORMANT_SERIES = [("f1", "F1", "r"), ("f2", "F2", "g"), ("f3", "F3", "c"), ("f4", "F4", "m")]
FORMANT_Y_MAX = 5000.0

# Numeric readout colors (match the plot pens; bright for a dark background).
READOUT_SERIES = [
    ("f0", "#ffff00"), ("f1", "#ff5555"), ("f2", "#55ff55"),
    ("f3", "#55ffff"), ("f4", "#ff55ff"),
]

AUDIO_FILE_FILTER = "Audio (*.wav *.flac *.ogg *.aiff *.aif *.mp3);;All files (*)"


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        *,
        samplerate: int = DEFAULT_SAMPLERATE,
        device: int | None = None,
        silence_db: float = DEFAULT_SILENCE_DB,
        initial_file: str | None = None,
        initial_ceiling: float = DEFAULT_F0_TRACK_CEILING,
        refresh_ms: int = 33,
    ) -> None:
        super().__init__()
        self.setWindowTitle("XVALite — voice trainer")

        self.samplerate = samplerate
        self.device = device
        self.silence_db = silence_db
        self._ceiling = initial_ceiling
        self._file_path = initial_file
        self.pipeline: AnalysisPipeline | None = None
        self._running = False

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        layout.addLayout(self._build_source_row())
        layout.addLayout(self._build_controls_row())
        layout.addLayout(self._build_vq_row())

        # -- pitch plot (axis follows the tracked F0 range) --
        self.pitch_plot = ScrollingPlot(
            title="Pitch (F0)", y_label="Hz",
            y_range=(75.0, self._ceiling), window_sec=10.0,
        )
        self.pitch_plot.add_series("f0", pen=pg.mkPen("y", width=2), name="F0")
        layout.addWidget(self.pitch_plot)

        # -- formant plot (F1–F4) --
        self.formant_plot = ScrollingPlot(
            title="Formants (F1–F4)", y_label="Hz",
            y_range=(0.0, FORMANT_Y_MAX), window_sec=10.0,
        )
        for key, name, color in FORMANT_SERIES:
            self.formant_plot.add_series(
                key, pen=pg.mkPen(color, width=2), name=name, symbol="o", symbol_size=6
            )
        layout.addWidget(self.formant_plot)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self._on_tick)

        self._sync_source_widgets()
        self._set_running_ui(False)

    # -- UI construction ---------------------------------------------------
    def _build_source_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Microphone", "mic")
        self.src_combo.addItem("Audio file", "file")
        self.src_combo.setCurrentIndex(1 if self._file_path else 0)
        self.src_combo.currentIndexChanged.connect(self._on_source_changed)

        self.browse_btn = QtWidgets.QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._on_browse)
        self.file_label = QtWidgets.QLabel()

        row.addWidget(QtWidgets.QLabel("Source:"))
        row.addWidget(self.src_combo)
        row.addWidget(self.browse_btn)
        row.addWidget(self.file_label, stretch=1)
        return row

    def _build_controls_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.pause_btn = QtWidgets.QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.toggled.connect(self._on_pause_toggled)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Normal (≤880 Hz)", NORMAL_CEILING)
        self.mode_combo.addItem("Extended (≤2100 Hz, C7)", EXTENDED_CEILING)
        self.mode_combo.setCurrentIndex(1 if self._ceiling >= EXTENDED_CEILING else 0)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

        row.addWidget(self.start_btn)
        row.addWidget(self.pause_btn)
        row.addWidget(QtWidgets.QLabel("Range:"))
        row.addWidget(self.mode_combo)
        row.addStretch(1)

        # Numeric readout: F0 + F1–F4, color-matched to the plots.
        self.readout = {}
        for key, color in READOUT_SERIES:
            lbl = QtWidgets.QLabel(f"{key.upper()}: --")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold; padding: 0 4px;")
            self.readout[key] = lbl
            row.addWidget(lbl)
        return row

    def _build_vq_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self.jitter_label = QtWidgets.QLabel("Jitter: --")
        self.shimmer_label = QtWidgets.QLabel("Shimmer: --")
        self.jitter_label.setToolTip(f"warns above {JITTER_LOCAL_WARN:.0%}")
        self.shimmer_label.setToolTip(f"warns above {SHIMMER_LOCAL_WARN:.0%}")
        self.jitter_label.setStyleSheet(VQ_STYLE_IDLE)
        self.shimmer_label.setStyleSheet(VQ_STYLE_IDLE)
        row.addWidget(QtWidgets.QLabel("Voice quality:"))
        row.addWidget(self.jitter_label)
        row.addWidget(self.shimmer_label)
        row.addStretch(1)
        return row

    # -- public ------------------------------------------------------------
    def start(self) -> None:
        """Auto-start with the current source selection (used at launch)."""
        self._start()

    # -- pipeline lifecycle ------------------------------------------------
    def _build_source(self):
        if self.src_combo.currentData() == "file":
            if not self._file_path or not os.path.isfile(self._file_path):
                QtWidgets.QMessageBox.warning(
                    self, "No file", "Choose an audio file with Browse… first."
                )
                return None
            return FileInput(self._file_path, samplerate=self.samplerate, realtime=True)
        return AudioInput(samplerate=self.samplerate, device=self.device)

    def _start(self) -> None:
        if self._running:
            return
        source = self._build_source()
        if source is None:
            return
        pipeline = AnalysisPipeline(
            source,
            samplerate=self.samplerate,
            pitch_ceiling=self._ceiling,
            silence_db=self.silence_db,
        )
        try:
            pipeline.start()  # opens the device / loads the file; may raise
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, "Could not start", f"Failed to start audio input:\n\n{exc}"
            )
            return
        self.pipeline = pipeline
        self.pitch_plot.clear_data()
        self.formant_plot.clear_data()
        self._reset_vq_labels()
        self._reset_readout()
        self._timer.start()
        self._set_running_ui(True)

    def _stop(self) -> None:
        self._timer.stop()
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
        self._set_running_ui(False)

    # -- timer tick --------------------------------------------------------
    def _on_tick(self) -> None:
        if self.pipeline is None:
            return
        for ev in self.pipeline.drain():
            if isinstance(ev, PitchSample):
                self.pitch_plot.append("f0", ev.t, ev.f0)
                self._set_readout("f0", ev.f0)
            elif isinstance(ev, FormantSample):
                for i, (key, _name, _color) in enumerate(FORMANT_SERIES):
                    self.formant_plot.append(key, ev.t, ev.formants[i])
                    self._set_readout(key, ev.formants[i])
            elif isinstance(ev, VoiceQualitySample):
                self._update_voice_quality(ev.voice_quality)
        self.pitch_plot.refresh()
        self.formant_plot.refresh()
        if self.pipeline is not None and self.pipeline.is_finished:
            error = self.pipeline.error
            self._stop()  # file ended (or source failed): reset controls
            if error:
                QtWidgets.QMessageBox.warning(self, "Input stopped", error)

    def _set_readout(self, key: str, value: float) -> None:
        text = f"{key.upper()}: {value:.0f}" if np.isfinite(value) else f"{key.upper()}: --"
        self.readout[key].setText(text)

    def _reset_readout(self) -> None:
        for key in self.readout:
            self.readout[key].setText(f"{key.upper()}: --")

    # -- voice quality -----------------------------------------------------
    def _update_voice_quality(self, vq) -> None:
        self._set_vq_label(self.jitter_label, "Jitter", vq.jitter_local, vq.jitter_warning)
        self._set_vq_label(
            self.shimmer_label, "Shimmer", vq.shimmer_local, vq.shimmer_warning
        )

    def _reset_vq_labels(self) -> None:
        self.jitter_label.setText("Jitter: --")
        self.shimmer_label.setText("Shimmer: --")
        self.jitter_label.setStyleSheet(VQ_STYLE_IDLE)
        self.shimmer_label.setStyleSheet(VQ_STYLE_IDLE)

    @staticmethod
    def _set_vq_label(label, name: str, value: float, warning: bool) -> None:
        if not np.isfinite(value):
            label.setText(f"{name}: --")
            label.setStyleSheet(VQ_STYLE_IDLE)
            return
        prefix = "⚠ " if warning else ""
        label.setText(f"{prefix}{name}: {value:.2%}")
        label.setStyleSheet(VQ_STYLE_WARN if warning else VQ_STYLE_OK)

    # -- control handlers --------------------------------------------------
    def _on_start_clicked(self) -> None:
        self._stop() if self._running else self._start()

    def _on_pause_toggled(self, checked: bool) -> None:
        if self.pipeline is None:
            return
        if checked:
            self.pipeline.pause()
            self.pause_btn.setText("Resume")
        else:
            self.pipeline.resume()
            self.pause_btn.setText("Pause")

    def _on_mode_changed(self, _index: int) -> None:
        self._ceiling = float(self.mode_combo.currentData())
        # Worker reads pitch_ceiling each loop; updating the attribute suffices.
        if self.pipeline is not None:
            self.pipeline.pitch_ceiling = self._ceiling
        self.pitch_plot.set_y_range(75.0, self._ceiling)

    def _on_source_changed(self, _index: int) -> None:
        self._sync_source_widgets()

    def _on_browse(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select audio file", "", AUDIO_FILE_FILTER
        )
        if path:
            self._file_path = path
            self._sync_source_widgets()

    # -- UI state ----------------------------------------------------------
    def _sync_source_widgets(self) -> None:
        is_file = self.src_combo.currentData() == "file"
        self.browse_btn.setVisible(is_file)
        self.file_label.setVisible(is_file)
        if is_file:
            self.file_label.setText(
                os.path.basename(self._file_path) if self._file_path else "(no file selected)"
            )

    def _set_running_ui(self, running: bool) -> None:
        self._running = running
        self.start_btn.setText("Stop" if running else "Start")
        self.src_combo.setEnabled(not running)
        self.browse_btn.setEnabled(not running)
        self.pause_btn.setEnabled(running)
        if not running:
            self.pause_btn.blockSignals(True)
            self.pause_btn.setChecked(False)
            self.pause_btn.setText("Pause")
            self.pause_btn.blockSignals(False)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        self._timer.stop()
        if self.pipeline is not None:
            self.pipeline.stop()
        super().closeEvent(event)
