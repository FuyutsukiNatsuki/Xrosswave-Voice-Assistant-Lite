"""Headless check that input errors are handled, not crashes.

Offscreen, and with QMessageBox auto-dismissed, confirm that starting with a
missing file leaves the app cleanly stopped rather than raising.

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\smoke_errors.py
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile  # noqa: E402

os.environ.setdefault("XVALITE_CONFIG_DIR", os.path.join(tempfile.gettempdir(), "xvalite_err"))

import _bootstrap  # noqa: E402,F401

from PySide6 import QtCore, QtWidgets  # noqa: E402

from xvalite.audio.input import DEFAULT_SAMPLERATE  # noqa: E402
from xvalite.gui.main_window import MainWindow  # noqa: E402


def _dismiss_dialogs() -> None:
    for w in QtWidgets.QApplication.topLevelWidgets():
        if isinstance(w, QtWidgets.QMessageBox):
            w.accept()


def main() -> int:
    app = QtWidgets.QApplication([])
    # Auto-dismiss any modal QMessageBox so exec() doesn't block.
    timer = QtCore.QTimer()
    timer.timeout.connect(_dismiss_dialogs)
    timer.start(100)

    window = MainWindow(
        samplerate=DEFAULT_SAMPLERATE,
        initial_file=os.path.join(
            os.path.dirname(__file__), "..", "testdata", "does_not_exist.wav"
        ),
    )
    window.show()
    window.start()  # should show a dialog and NOT start

    QtCore.QTimer.singleShot(600, app.quit)
    app.exec()

    ok = (window.pipeline is None) and (window._running is False)
    print(f"pipeline={window.pipeline}  running={window._running}")
    print("SMOKE OK" if ok else "SMOKE FAIL (should be stopped)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
