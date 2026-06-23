"""Headless smoke test for report mode.

Offscreen: run a report-mode session on the test recording, stop, and confirm a
report window was produced and can be exported to PNG.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\smoke_report.py
"""

import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("XVALITE_CONFIG_DIR", os.path.join(tempfile.gettempdir(), "xvalite_report"))

import _bootstrap  # noqa: E402,F401

from PySide6 import QtCore, QtWidgets  # noqa: E402

from xvalite.audio.input import DEFAULT_SAMPLERATE  # noqa: E402
from xvalite.gui.main_window import MainWindow  # noqa: E402

PATH = r"C:\XVALite\testdata\test.wav"


def main() -> int:
    app = QtWidgets.QApplication([])
    window = MainWindow(samplerate=DEFAULT_SAMPLERATE, initial_file=PATH)
    window.report_check.setChecked(True)
    window.show()
    window.start()
    QtCore.QTimer.singleShot(5000, window._stop)
    QtCore.QTimer.singleShot(5400, app.quit)
    app.exec()

    win = window._report_win
    png = os.path.join(tempfile.gettempdir(), "xvalite_report_smoke.png")
    png_ok = False
    if win is not None:
        win.grab().save(png)
        png_ok = os.path.exists(png) and os.path.getsize(png) > 1000

    print(f"report window: {win is not None}")
    print(f"PNG export:    {png_ok}")
    ok = win is not None and png_ok
    print("SMOKE OK" if ok else "SMOKE FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
