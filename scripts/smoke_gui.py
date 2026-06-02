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
RUN_MS = 1500


def main() -> int:
    app = QtWidgets.QApplication([])
    source = FileInput(PATH, samplerate=DEFAULT_SAMPLERATE, realtime=True)
    pipeline = AnalysisPipeline(source, samplerate=DEFAULT_SAMPLERATE)
    window = MainWindow(pipeline)
    window.resize(900, 420)
    window.show()
    window.start()

    # Pause/resume mid-run to exercise that path too.
    QtCore.QTimer.singleShot(RUN_MS // 3, lambda: window.pause_btn.setChecked(True))
    QtCore.QTimer.singleShot(2 * RUN_MS // 3, lambda: window.pause_btn.setChecked(False))
    QtCore.QTimer.singleShot(RUN_MS, app.quit)
    app.exec()

    n = window.pitch_plot.point_count("f0")
    window.pipeline.stop()
    print(f"pitch points collected: {n}")
    ok = n > 0
    print("SMOKE OK" if ok else "SMOKE FAIL (no data)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
