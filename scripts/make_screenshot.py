"""Render a GUI screenshot for the README (offscreen).

Runs the window against a recording for a few seconds, then grabs it to
assets/screenshot.png. Needs a local audio file (default testdata/test.wav).

Run:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\make_screenshot.py [path.wav]
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _bootstrap  # noqa: E402,F401

import sys  # noqa: E402

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from xvalite.audio.input import DEFAULT_SAMPLERATE  # noqa: E402
from xvalite.gui.main_window import MainWindow  # noqa: E402

PATH = sys.argv[1] if len(sys.argv) > 1 else r"C:\XVALite\testdata\test.wav"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "screenshot.png")


def main() -> int:
    app = QtWidgets.QApplication([])
    # Offscreen QPA has no font DB; point Qt at a known Windows font so text
    # renders instead of tofu boxes.
    app.setFont(QtGui.QFont("Segoe UI", 9))
    window = MainWindow(samplerate=DEFAULT_SAMPLERATE, initial_file=PATH)
    window.resize(900, 600)
    window.show()
    window.start()

    def capture() -> None:
        window.grab().save(os.path.abspath(OUT))
        if window.pipeline is not None:
            window.pipeline.stop()
        app.quit()

    QtCore.QTimer.singleShot(3500, capture)
    app.exec()
    print(f"wrote {os.path.abspath(OUT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
