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

from xvalite.audio.file_input import FileInput
from xvalite.audio.input import DEFAULT_SAMPLERATE, AudioInput
from xvalite.gui.main_window import MainWindow
from xvalite.pipeline import AnalysisPipeline


def main() -> int:
    parser = argparse.ArgumentParser(description="XVALite voice trainer")
    parser.add_argument("--file", default=None, help="audio file to analyze (else mic)")
    parser.add_argument("--device", type=int, default=None, help="mic device index")
    parser.add_argument(
        "--silence-db",
        type=float,
        default=None,
        help="input dead zone in dBFS; windows quieter than this are silence "
        "(default -40). Raise toward 0 to gate more aggressively.",
    )
    args = parser.parse_args()

    app = QtWidgets.QApplication(sys.argv)

    if args.file:
        source = FileInput(args.file, samplerate=DEFAULT_SAMPLERATE, realtime=True)
    else:
        source = AudioInput(samplerate=DEFAULT_SAMPLERATE, device=args.device)

    pipeline_kwargs = {}
    if args.silence_db is not None:
        pipeline_kwargs["silence_db"] = args.silence_db
    pipeline = AnalysisPipeline(source, samplerate=DEFAULT_SAMPLERATE, **pipeline_kwargs)
    window = MainWindow(pipeline)
    window.resize(900, 420)
    window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
