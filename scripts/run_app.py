"""Launch the XVALite GUI.

    # Microphone input:
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\run_app.py

    # File input (real-time playback through the same pipeline):
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\run_app.py --file testdata\\test.wav
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

import argparse
import sys

from PySide6 import QtWidgets

from xvalite.audio.input import DEFAULT_SAMPLERATE
from xvalite.gui.main_window import MainWindow
from xvalite.pipeline import DEFAULT_SILENCE_DB


def main() -> int:
    parser = argparse.ArgumentParser(description="XVALite voice trainer")
    parser.add_argument("--file", default=None, help="audio file to preselect (else mic)")
    parser.add_argument("--device", type=int, default=None, help="mic device index")
    parser.add_argument(
        "--silence-db",
        type=float,
        default=DEFAULT_SILENCE_DB,
        help="input dead zone in dBFS; windows quieter than this are silence "
        "(default -40). Raise toward 0 to gate more aggressively.",
    )
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(
        samplerate=DEFAULT_SAMPLERATE,
        device=args.device,
        silence_db=args.silence_db,
        initial_file=args.file,
    )
    window.resize(900, 600)
    window.show()
    window.start()  # auto-start with the preselected source
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
