"""Frozen-app entry point for PyInstaller.

Kept at the repo root and pointed at by the build. Adds ``src/`` to the path so
it also runs directly (``python xvalite_app.py``); when frozen, PyInstaller has
already bundled the ``xvalite`` package and the extra path is harmless.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from xvalite.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
