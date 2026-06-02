"""Application entry point.

Builds the Qt application and main window. Used both by the dev launcher
(`scripts/run_app.py`) and the packaged executable (`xvalite_app.py` +
PyInstaller), so the launch logic lives in one place.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional, Sequence

from PySide6 import QtGui, QtWidgets

from .audio.input import DEFAULT_SAMPLERATE
from .gui.main_window import MainWindow
from .pipeline import DEFAULT_SILENCE_DB


def _icon_path() -> Optional[str]:
    """Locate assets/icon.ico whether running from source or a frozen build."""
    if hasattr(sys, "_MEIPASS"):  # PyInstaller bundle
        candidate = os.path.join(sys._MEIPASS, "assets", "icon.ico")
    else:  # repo: src/xvalite/app.py -> ../../assets
        candidate = os.path.join(
            os.path.dirname(__file__), "..", "..", "assets", "icon.ico"
        )
    return candidate if os.path.isfile(candidate) else None


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="XVALite voice trainer")
    parser.add_argument("--file", default=None, help="audio file to preselect (else mic)")
    parser.add_argument("--device", type=int, default=None, help="mic device index")
    parser.add_argument(
        "--silence-db",
        type=float,
        default=DEFAULT_SILENCE_DB,
        help="input dead zone in dBFS (default -40); raise toward 0 to gate more.",
    )
    parser.add_argument(
        "--no-autostart",
        action="store_true",
        help="open the window without starting capture (pick a source, then Start).",
    )
    args = parser.parse_args(argv)

    app = QtWidgets.QApplication(sys.argv[:1])
    icon = _icon_path()
    if icon:
        app.setWindowIcon(QtGui.QIcon(icon))
    window = MainWindow(
        samplerate=DEFAULT_SAMPLERATE,
        device=args.device,
        silence_db=args.silence_db,
        initial_file=args.file,
    )
    window.resize(900, 600)
    window.show()
    if not args.no_autostart:
        window.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
