"""Headless smoke test for the GUI.

Runs the real window offscreen (no visible window) against the test recording
for a short time, then confirms the pitch plot actually received data and no
exception was raised. This is the automatable check; visual confirmation needs
a real run via run_app.py on the user's machine.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\smoke_gui.py
"""

import os

# Must be set before any Qt platform initialization — no window will appear.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: E402,F401  (adds src/ to sys.path)

import sys  # noqa: E402

from PySide6 import QtCore, QtWidgets  # noqa: E402

from xvalite.audio.file_input import FileInput  # noqa: E402
from xvalite.audio.input import DEFAULT_SAMPLERATE  # noqa: E402
from xvalite.gui.main_window import MainWindow  # noqa: E402
from xvalite.pipeline import AnalysisPipeline  # noqa: E402

PATH = r"C:\XVALite\testdata\test.wav"
RUN_MS = 3000


def main() -> int:
    app = QtWidgets.QApplication([])
    source = FileInput(PATH, samplerate=DEFAULT_SAMPLERATE, realtime=True)
    pipeline = AnalysisPipeline(source, samplerate=DEFAULT_SAMPLERATE)
    window = MainWindow(pipeline)
    window.resize(900, 600)
    window.show()
    window.start()

    # Exercise the range-mode toggle, then a pause/resume cycle.
    QtCore.QTimer.singleShot(400, lambda: window.mode_combo.setCurrentIndex(0))
    QtCore.QTimer.singleShot(800, lambda: window.mode_combo.setCurrentIndex(1))
    QtCore.QTimer.singleShot(RUN_MS // 2, lambda: window.pause_btn.setChecked(True))
    QtCore.QTimer.singleShot(RUN_MS // 2 + 400, lambda: window.pause_btn.setChecked(False))
    QtCore.QTimer.singleShot(RUN_MS, app.quit)
    app.exec()

    pitch_n = window.pitch_plot.point_count("f0")
    formant_n = window.formant_plot.point_count("f1")
    window.pipeline.stop()
    print(f"pitch points collected:   {pitch_n}")
    print(f"formant points collected: {formant_n}")
    ok = pitch_n > 0 and formant_n > 0
    print("SMOKE OK" if ok else "SMOKE FAIL (missing data)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
