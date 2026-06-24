"""Analysis report window (shown after a report-mode session).

Aggregates data collected during the session and presents it: average pitch,
average voice quality, ratio pie charts (voice tendency / register / resonance),
and a per-vowel F1×F2 formant plot vs male/female references. Exportable to PNG.

Pies are drawn with QPainter (pyqtgraph has no pie chart); the formant plot uses
pyqtgraph. No new dependencies.
"""

from __future__ import annotations

import math
import statistics
from typing import Dict, List, Tuple

import numpy as np
import pyqtgraph as pg
from PySide6 import QtCore, QtGui, QtWidgets

from ..analysis.pitch import note_name
from ..analysis.voice_profile import VOWEL_REF_FEMALE, VOWEL_REF_MALE
from ..i18n import tr

_TENDENCY_COLORS = {"low": "#5aa0e6", "mid": "#bbbbbb", "high": "#e67ad0"}
_REGISTER_COLORS = {"Chest": "#e6a14a", "Mix": "#7ad07a", "Head": "#b07ad0"}
_VOWEL_ORDER = ["i", "e", "a", "o", "u"]  # perimeter order for the polygon


class PieChart(QtWidgets.QWidget):
    """Small pie chart with a side legend. Data: list of (label, value, color)."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent=parent)
        self._title = title
        self._slices: List[Tuple[str, float, QtGui.QColor]] = []
        self.setMinimumSize(240, 170)

    def set_data(self, slices: List[Tuple[str, float, str]]) -> None:
        self._slices = [(lbl, val, QtGui.QColor(col)) for lbl, val, col in slices if val > 0]
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtGui.QColor("#ddd"))
        p.drawText(QtCore.QRect(0, 0, self.width(), 18),
                   QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, self._title)

        total = sum(v for _, v, _ in self._slices)
        diameter = min(self.height() - 24, self.width() // 2 - 8)
        box = QtCore.QRectF(4, 22, diameter, diameter)
        if total <= 0:
            p.drawText(box, QtCore.Qt.AlignCenter, "--")
            p.end()
            return

        start = 90 * 16  # start at top, clockwise
        for _lbl, val, col in self._slices:
            span = -int(round(360 * 16 * val / total))
            p.setBrush(col)
            p.setPen(QtGui.QColor("#2d2d2d"))
            p.drawPie(box, start, span)
            start += span

        # Legend on the right.
        lx = int(diameter) + 14
        ly = 26
        p.setPen(QtGui.QColor("#ddd"))
        for lbl, val, col in self._slices:
            pct = 100.0 * val / total
            p.setBrush(col)
            p.setPen(QtGui.QColor("#2d2d2d"))
            p.drawRect(lx, ly, 11, 11)
            p.setPen(QtGui.QColor("#ddd"))
            p.drawText(lx + 16, ly + 10, f"{lbl}: {pct:.0f}%")
            ly += 18
        p.end()


def _vowel_formant_plot(your_means: Dict[str, Tuple[float, float]]) -> pg.PlotWidget:
    plot = pg.PlotWidget()
    plot.setTitle(tr("rep_vowel_formants"))
    plot.setLabel("bottom", "F1", units="Hz")
    plot.setLabel("left", "F2", units="Hz")
    plot.showGrid(x=True, y=True, alpha=0.3)
    plot.addLegend(offset=(-10, 10))

    def add_ref(ref, color, name):
        xs = [ref[v][0] for v in _VOWEL_ORDER] + [ref[_VOWEL_ORDER[0]][0]]
        ys = [ref[v][1] for v in _VOWEL_ORDER] + [ref[_VOWEL_ORDER[0]][1]]
        plot.plot(xs, ys, pen=pg.mkPen(color, width=1, style=QtCore.Qt.DashLine),
                  symbol="o", symbolSize=6, symbolBrush=color, name=name)

    add_ref(VOWEL_REF_MALE, "#6a90e0", tr("rep_male_avg"))
    add_ref(VOWEL_REF_FEMALE, "#e08aa0", tr("rep_female_avg"))

    pts = [(your_means[v][0], your_means[v][1], v) for v in _VOWEL_ORDER if v in your_means]
    if pts:
        xs = [x for x, _, _ in pts]
        ys = [y for _, y, _ in pts]
        plot.plot(xs, ys, pen=pg.mkPen("#3fcf3f", width=2),
                  symbol="star", symbolSize=16, symbolBrush="#3fcf3f", name=tr("rep_your_voice"))
        for x, y, v in pts:
            t = pg.TextItem(v, color="#3fcf3f", anchor=(0.5, 1.2))
            t.setPos(x, y)
            plot.addItem(t)
    return plot


class ReportWindow(QtWidgets.QWidget):
    def __init__(self, data: dict, parent=None) -> None:
        super().__init__(parent=parent)
        self.setWindowTitle(tr("report_title"))
        self.resize(940, 760)
        layout = QtWidgets.QVBoxLayout(self)

        layout.addWidget(self._summary_label(data))

        pies = QtWidgets.QHBoxLayout()
        pies.addWidget(self._make_pie(tr("rep_tendency"), data["tendency"], _TENDENCY_COLORS, "tendency"))
        pies.addWidget(self._make_pie(tr("rep_register"), data["register"], _REGISTER_COLORS, "register"))
        pies.addStretch(1)
        layout.addLayout(pies)

        means = {v: (float(np.mean([f1 for f1, _ in pairs])),
                     float(np.mean([f2 for _, f2 in pairs])))
                 for v, pairs in data["vowel_f1f2"].items() if pairs}
        layout.addWidget(_vowel_formant_plot(means), stretch=1)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        self.export_btn = QtWidgets.QPushButton(tr("export_png"))
        self.export_btn.clicked.connect(self._export_png)
        btn_row.addWidget(self.export_btn)
        layout.addLayout(btn_row)

    @staticmethod
    def _make_pie(title: str, counts: Dict[str, int], colors: Dict[str, str], prefix: str) -> PieChart:
        pie = PieChart(title)
        slices = [
            (tr(f"{prefix}.{key}"), float(n), colors.get(key, "#888"))
            for key, n in counts.items() if n > 0
        ]
        pie.set_data(slices)
        return pie

    @staticmethod
    def _summary_label(data: dict) -> QtWidgets.QLabel:
        f0 = [v for v in data["f0"] if math.isfinite(v)]
        lines = []
        if f0:
            med = statistics.median(f0)
            lines.append(
                f"{tr('rep_avg_pitch')}: {med:.0f} Hz  {note_name(med)}"
                f"  ({tr('rep_range')}: {min(f0):.0f}–{max(f0):.0f} Hz)"
            )
        else:
            lines.append(f"{tr('rep_avg_pitch')}: --")

        def avg(key, fmt):
            vals = [v for v in data[key] if math.isfinite(v)]
            return fmt.format(np.mean(vals)) if vals else "--"

        lines.append(
            f"{tr('rep_quality')}:  Jitter {avg('jitter', '{:.2%}')}  "
            f"Shimmer {avg('shimmer', '{:.2%}')}  HNR {avg('hnr', '{:.1f} dB')}"
        )
        lines.append(f"{tr('rep_duration')}: {data.get('seconds', 0):.0f} s")
        lbl = QtWidgets.QLabel("\n".join(lines))
        lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #eee;")
        return lbl

    def _export_png(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("export_png"), "report.png", "PNG (*.png)"
        )
        if path:
            self.grab().save(path)


def has_data(data: dict) -> bool:
    return bool(data["f0"]) or any(data["vowel_f1f2"].values()) or sum(data["tendency"].values())
