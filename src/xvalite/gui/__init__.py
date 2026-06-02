"""GUI layer: PySide6 window + pyqtgraph scrolling plots."""

import os

# Ensure pyqtgraph binds to PySide6 (must be set before pyqtgraph is imported).
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
