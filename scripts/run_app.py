"""Launch the XVALite GUI (dev launcher).

    # Microphone input (auto-starts):
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\run_app.py

    # Preselect a file (real-time playback through the same pipeline):
    & "C:\\XVALite\\.venv\\Scripts\\python.exe" scripts\\run_app.py --file testdata\\test.wav

The packaged executable uses the same entry point via xvalite_app.py.
"""

import _bootstrap  # noqa: F401  (adds src/ to sys.path)

from xvalite.app import main

if __name__ == "__main__":
    raise SystemExit(main())
