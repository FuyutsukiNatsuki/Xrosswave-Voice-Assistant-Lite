"""Add ``src/`` to sys.path so verification scripts can import xvalite.

This keeps phase-1 verification runnable without an editable install.
"""

import os
import sys

_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
if _SRC not in sys.path:
    sys.path.insert(0, os.path.abspath(_SRC))
