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
from PySide6 import QtCore, QtGui, QtWidgets

from ..analysis.spectrogram import (
    DEFAULT_MAX_FREQ,
    NARROWBAND_FFT,
    WIDEBAND_FFT,
    WIDEBAND_HOP,
    column_frequencies,
)
from ..analysis.voice_quality import JITTER_LOCAL_WARN, SHIMMER_LOCAL_WARN
from ..audio.file_input import FileInput
from ..audio.input import (
    DEFAULT_SAMPLERATE,
    AudioInput,
    list_input_devices,
    list_output_devices,
)
from ..config import load_config, save_config
from ..pipeline import (
    DEFAULT_SILENCE_DB,
    SPECTRUM_MAX_FREQ,
    AnalysisPipeline,
    FormantSample,
    PitchSample,
    SpectrogramColumn,
    SpectrumFrame,
    VoiceProfileSample,
    VoiceQualitySample,
    WaveformFrame,
)
from .instant_plots import SpectrumPlot, WaveformPlot
from .scrolling_plot import ScrollingPlot
from .spectrogram_plot import SpectrogramPlot

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
FORMANT_Y_MAX = 6400.0

# Selectable plot panes (config key, menu label). Order = top→bottom in the splitter.
PANELS = [
    ("pitch", "Pitch (F0)"),
    ("formants", "Formants (F1–F4)"),
    ("oscilloscope", "Waveform (oscilloscope)"),
    ("spectrum", "Spectrum (instantaneous)"),
    ("narrowband", "Spectrogram — narrowband"),
    ("wideband", "Spectrogram — wideband"),
]

# Numeric readout colors (match the plot pens; bright for a dark background).
READOUT_SERIES = [
    ("f0", "#ffff00"), ("f1", "#ff5555"), ("f2", "#55ff55"),
    ("f3", "#55ffff"), ("f4", "#ff55ff"),
]

AUDIO_FILE_FILTER = "Audio (*.wav *.flac *.ogg *.aiff *.aif *.mp3);;All files (*)"
DEFAULT_VOLUME_PCT = 10  # quiet default for file playback


class MainWindow(QtWidgets.QMainWindow):
    def __init__(
        self,
        *,
        samplerate: int = DEFAULT_SAMPLERATE,
        device: int | None = None,
        silence_db: float = DEFAULT_SILENCE_DB,
        initial_file: str | None = None,
        refresh_ms: int = 33,
    ) -> None:
        super().__init__()
        self.setWindowTitle("XVALite — voice trainer")

        self._config = load_config()
        self._loaded = False  # gate config saves during construction

        self.samplerate = samplerate
        self.device = device
        self.silence_db = silence_db
        self._file_path = initial_file
        self.pipeline: AnalysisPipeline | None = None
        self._running = False
        self._ceiling = (
            EXTENDED_CEILING if self._config["range_mode"] == "extended" else NORMAL_CEILING
        )

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        layout.addLayout(self._build_source_row())
        layout.addLayout(self._build_controls_row())

        # -- six selectable plot panes in a resizable vertical splitter --
        self.pitch_plot = ScrollingPlot(
            title="Pitch (F0)", y_label="Hz",
            y_range=(75.0, self._ceiling), window_sec=10.0,
        )
        self.pitch_plot.add_series("f0", pen=pg.mkPen("y", width=2), name="F0")

        self.formant_plot = ScrollingPlot(
            title="Formants (F1–F4)", y_label="Hz",
            y_range=(0.0, FORMANT_Y_MAX), window_sec=10.0,
        )
        for key, name, color in FORMANT_SERIES:
            self.formant_plot.add_series(
                key, pen=pg.mkPen(color, width=2), name=name, symbol="o", symbol_size=6
            )

        self.spectrogram_narrow = SpectrogramPlot(
            column_frequencies(self.samplerate, NARROWBAND_FFT, DEFAULT_MAX_FREQ),
            window_sec=10.0, title="Spectrogram (narrowband)",
        )
        self.spectrogram_wide = SpectrogramPlot(
            column_frequencies(self.samplerate, WIDEBAND_FFT, DEFAULT_MAX_FREQ),
            window_sec=10.0, title="Spectrogram (wideband)",
            column_rate_hz=self.samplerate / WIDEBAND_HOP,  # finer time resolution
        )
        self.osc_plot = WaveformPlot(self.samplerate)
        spectrum_max = min(SPECTRUM_MAX_FREQ, self.samplerate / 2.0)
        self.spectrum_plot = SpectrumPlot(
            column_frequencies(self.samplerate, NARROWBAND_FFT, spectrum_max),
            peak_hold=bool(self._config.get("peak_hold", True)),
            min_freq=10.0,
        )

        self._panel_widgets = {
            "pitch": self.pitch_plot,
            "formants": self.formant_plot,
            "oscilloscope": self.osc_plot,
            "spectrum": self.spectrum_plot,
            "narrowband": self.spectrogram_narrow,
            "wideband": self.spectrogram_wide,
        }
        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self._splitter.setChildrenCollapsible(False)  # panes can't shrink to 0
        for key, _label in PANELS:
            widget = self._panel_widgets[key]
            widget.setMinimumHeight(120)  # always readable when shown
            self._splitter.addWidget(widget)

        # Left: vertical list of numeric readouts. Right: the plots.
        body = QtWidgets.QHBoxLayout()
        body.addWidget(self._build_left_panel())
        body.addWidget(self._splitter, stretch=1)
        layout.addLayout(body, stretch=1)

        self._build_view_menu()

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(refresh_ms)
        self._timer.timeout.connect(self._on_tick)

        self._apply_config()
        self._sync_source_widgets()
        self._set_running_ui(False)
        self._loaded = True

    # -- UI construction ---------------------------------------------------
    def _build_source_row(self) -> QtWidgets.QHBoxLayout:
        row = QtWidgets.QHBoxLayout()
        self.src_combo = QtWidgets.QComboBox()
        self.src_combo.addItem("Microphone", "mic")
        self.src_combo.addItem("Audio file", "file")
        self.src_combo.setCurrentIndex(1 if self._file_path else 0)
        self.src_combo.currentIndexChanged.connect(self._on_source_changed)

        # Microphone device picker (shown when source = Microphone).
        self.device_label = QtWidgets.QLabel("Device:")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.addItem("Default (system)", None)
        for idx, name in list_input_devices():
            self.device_combo.addItem(f"{name}  (#{idx})", idx)
        if self.device is not None:
            pos = self.device_combo.findData(self.device)
            if pos >= 0:
                self.device_combo.setCurrentIndex(pos)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)

        # File picker + playback controls (shown when source = Audio file).
        self.browse_btn = QtWidgets.QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._on_browse)
        self.file_label = QtWidgets.QLabel()

        self.output_label = QtWidgets.QLabel("Output:")
        self.output_combo = QtWidgets.QComboBox()
        self.output_combo.addItem("Default (system)", None)
        for idx, name in list_output_devices():
            self.output_combo.addItem(f"{name}  (#{idx})", idx)
        self.output_combo.currentIndexChanged.connect(self._on_device_changed)

        self.vol_label = QtWidgets.QLabel("Vol:")
        self.vol_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(DEFAULT_VOLUME_PCT)
        self.vol_slider.setFixedWidth(90)
        self.vol_value = QtWidgets.QLabel(f"{DEFAULT_VOLUME_PCT}%")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)

        row.addWidget(QtWidgets.QLabel("Source:"))
        row.addWidget(self.src_combo)
        row.addWidget(self.device_label)
        row.addWidget(self.device_combo)
        row.addWidget(self.browse_btn)
        row.addWidget(self.file_label, stretch=1)
        row.addWidget(self.output_label)
        row.addWidget(self.output_combo)
        row.addWidget(self.vol_label)
        row.addWidget(self.vol_slider)
        row.addWidget(self.vol_value)
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

        self.peak_check = QtWidgets.QCheckBox("Peak hold")
        self.peak_check.setToolTip("Hold the per-frequency maximum on the spectrum view")
        self.peak_check.toggled.connect(self._on_peak_hold_toggled)

        row.addWidget(self.start_btn)
        row.addWidget(self.pause_btn)
        row.addWidget(QtWidgets.QLabel("Range:"))
        row.addWidget(self.mode_combo)
        row.addWidget(self.peak_check)
        row.addStretch(1)
        return row

    def _build_left_panel(self) -> QtWidgets.QWidget:
        """Vertical list of numeric readouts down the left side of the window."""
        panel = QtWidgets.QWidget()
        panel.setFixedWidth(200)
        col = QtWidgets.QVBoxLayout(panel)
        col.setContentsMargins(6, 4, 6, 4)
        col.setSpacing(3)

        def header(text: str) -> None:
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet("color: #9ad; font-weight: bold; margin-top: 6px;")
            col.addWidget(lbl)

        # Pitch / formants.
        header("ピッチ・フォルマント")
        self.readout = {}
        for key, color in READOUT_SERIES:
            lbl = QtWidgets.QLabel(f"{key.upper()}: --")
            lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            self.readout[key] = lbl
            col.addWidget(lbl)

        # Voice quality.
        header("声質")
        self.jitter_label = QtWidgets.QLabel("Jitter: --")
        self.shimmer_label = QtWidgets.QLabel("Shimmer: --")
        self.jitter_label.setToolTip(f"warns above {JITTER_LOCAL_WARN:.0%}")
        self.shimmer_label.setToolTip(f"warns above {SHIMMER_LOCAL_WARN:.0%}")
        self.jitter_label.setStyleSheet(VQ_STYLE_IDLE)
        self.shimmer_label.setStyleSheet(VQ_STYLE_IDLE)
        col.addWidget(self.jitter_label)
        col.addWidget(self.shimmer_label)

        # Estimation (register + voice tendency).
        header("推定")
        self.register_label = QtWidgets.QLabel("声区: --")
        self.tendency_label = QtWidgets.QLabel("声の傾向: --")
        self.hnr_label = QtWidgets.QLabel("HNR: --")
        self.register_label.setToolTip("地声寄り / ミックス / 裏声寄り（推定）")
        self.tendency_label.setToolTip("男声寄り / 中声 / 女声寄り（声の音響的傾向。性別判定ではありません）")
        for lbl in (self.register_label, self.tendency_label, self.hnr_label):
            lbl.setStyleSheet("color: #ddd;")
            lbl.setWordWrap(True)
            col.addWidget(lbl)

        col.addStretch(1)
        return panel

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
            return FileInput(
                self._file_path,
                samplerate=self.samplerate,
                realtime=True,
                play=True,
                output_device=self.output_combo.currentData(),
                volume=self.vol_slider.value() / 100.0,
            )
        return AudioInput(samplerate=self.samplerate, device=self.device_combo.currentData())

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
        self.spectrogram_narrow.clear_data()
        self.spectrogram_wide.clear_data()
        self.osc_plot.clear_data()
        self.spectrum_plot.clear_data()
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
            elif isinstance(ev, VoiceProfileSample):
                self._update_voice_profile(ev.profile)
            elif isinstance(ev, WaveformFrame):
                if self.osc_plot.isVisible():
                    self.osc_plot.set_frame(ev.samples)
            elif isinstance(ev, SpectrumFrame):
                if self.spectrum_plot.isVisible():
                    self.spectrum_plot.set_column(ev.db)
            elif isinstance(ev, SpectrogramColumn):
                if ev.wide:
                    self.spectrogram_wide.append(ev.t, ev.db)
                else:
                    self.spectrogram_narrow.append(ev.t, ev.db)
        if self.pitch_plot.isVisible():
            self.pitch_plot.refresh()
        if self.formant_plot.isVisible():
            self.formant_plot.refresh()
        if self.spectrogram_narrow.isVisible():
            self.spectrogram_narrow.refresh()
        if self.spectrogram_wide.isVisible():
            self.spectrogram_wide.refresh()
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
        self.register_label.setText("声区: --")
        self.tendency_label.setText("声の傾向: --")
        self.hnr_label.setText("HNR: --")

    def _update_voice_profile(self, p) -> None:
        if p.register == "Unknown":
            self.register_label.setText("声区: --")
            self.tendency_label.setText("声の傾向: --")
            self.hnr_label.setText("HNR: --")
            return
        self.register_label.setText(f"声区: {p.register_ja}（{p.register_conf}）")
        self.tendency_label.setText(f"声の傾向: {p.tendency_ja}（{p.tendency_conf}）")
        hnr = f"{p.hnr:.1f} dB" if np.isfinite(p.hnr) else "--"
        self.hnr_label.setText(f"HNR: {hnr}")

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
        self._save_config()

    def _on_panel_toggled(self, key: str, checked: bool) -> None:
        self._panel_widgets[key].setVisible(checked)
        self._rebalance_panels()
        self._save_config()

    def _rebalance_panels(self) -> None:
        """Give every visible pane an equal share (Qt distributes by ratio), so a
        just-shown pane never stays collapsed at size 0."""
        sizes = [1000 if self._panel_actions[k].isChecked() else 0 for k, _ in PANELS]
        self._splitter.setSizes(sizes)

    def _on_volume_changed(self, value: int) -> None:
        self.vol_value.setText(f"{value}%")
        # Apply live to a running file-playback source.
        source = self.pipeline.source if self.pipeline is not None else None
        if source is not None and hasattr(source, "volume"):
            source.volume = value / 100.0
        self._save_config()

    def _on_device_changed(self, _index: int) -> None:
        self._save_config()

    def _on_peak_hold_toggled(self, checked: bool) -> None:
        self.spectrum_plot.set_peak_hold(checked)
        self._save_config()

    def _on_source_changed(self, _index: int) -> None:
        self._sync_source_widgets()

    # -- View menu + config -----------------------------------------------
    def _build_view_menu(self) -> None:
        menu = self.menuBar().addMenu("View")
        self._panel_actions = {}
        for key, label in PANELS:
            action = QtGui.QAction(label, self, checkable=True)
            action.toggled.connect(lambda checked, k=key: self._on_panel_toggled(k, checked))
            menu.addAction(action)
            self._panel_actions[key] = action

    def _apply_config(self) -> None:
        cfg = self._config
        self.mode_combo.setCurrentIndex(1 if cfg["range_mode"] == "extended" else 0)
        self.vol_slider.setValue(int(cfg["volume_pct"]))
        self.peak_check.setChecked(bool(cfg.get("peak_hold", True)))
        for key, _label in PANELS:
            visible = bool(cfg["panels"].get(key, True))
            self._panel_actions[key].setChecked(visible)
            self._panel_widgets[key].setVisible(visible)
        self._restore_device(self.device_combo, cfg.get("input_device"))
        self._restore_device(self.output_combo, cfg.get("output_device"))
        self._rebalance_panels()

    @staticmethod
    def _restore_device(combo, label) -> None:
        if label:
            pos = combo.findText(label)
            if pos >= 0:
                combo.setCurrentIndex(pos)

    def _save_config(self) -> None:
        if not self._loaded:
            return
        save_config(
            {
                "range_mode": "extended" if self._ceiling >= EXTENDED_CEILING else "normal",
                "volume_pct": self.vol_slider.value(),
                "panels": {k: self._panel_actions[k].isChecked() for k, _ in PANELS},
                "peak_hold": self.peak_check.isChecked(),
                "input_device": self.device_combo.currentText(),
                "output_device": self.output_combo.currentText(),
            }
        )

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
        self.output_label.setVisible(is_file)
        self.output_combo.setVisible(is_file)
        self.vol_label.setVisible(is_file)
        self.vol_slider.setVisible(is_file)
        self.vol_value.setVisible(is_file)
        self.device_label.setVisible(not is_file)
        self.device_combo.setVisible(not is_file)
        if is_file:
            self.file_label.setText(
                os.path.basename(self._file_path) if self._file_path else "(no file selected)"
            )

    def _set_running_ui(self, running: bool) -> None:
        self._running = running
        self.start_btn.setText("Stop" if running else "Start")
        self.src_combo.setEnabled(not running)
        self.browse_btn.setEnabled(not running)
        self.device_combo.setEnabled(not running)
        self.output_combo.setEnabled(not running)  # volume slider stays live
        self.pause_btn.setEnabled(running)
        if not running:
            self.pause_btn.blockSignals(True)
            self.pause_btn.setChecked(False)
            self.pause_btn.setText("Pause")
            self.pause_btn.blockSignals(False)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        self._save_config()
        self._timer.stop()
        if self.pipeline is not None:
            self.pipeline.stop()
        super().closeEvent(event)
