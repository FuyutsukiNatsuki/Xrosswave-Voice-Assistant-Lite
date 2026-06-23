"""Force a dark theme regardless of the OS setting.

Light mode left some Qt-widget text hard to read, so we apply a dark Fusion
palette to the whole application. Plots (pyqtgraph) are already dark.
"""

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

_C = QtGui.QColor


def apply_dark_theme(app: QtWidgets.QApplication) -> None:
    app.setStyle("Fusion")
    pal = QtGui.QPalette()
    Role = QtGui.QPalette.ColorRole
    Group = QtGui.QPalette.ColorGroup

    pal.setColor(Role.Window, _C(45, 45, 45))
    pal.setColor(Role.WindowText, _C(221, 221, 221))
    pal.setColor(Role.Base, _C(30, 30, 30))
    pal.setColor(Role.AlternateBase, _C(45, 45, 45))
    pal.setColor(Role.ToolTipBase, _C(45, 45, 45))
    pal.setColor(Role.ToolTipText, _C(221, 221, 221))
    pal.setColor(Role.Text, _C(221, 221, 221))
    pal.setColor(Role.Button, _C(53, 53, 53))
    pal.setColor(Role.ButtonText, _C(221, 221, 221))
    pal.setColor(Role.BrightText, _C(255, 80, 80))
    pal.setColor(Role.Link, _C(90, 160, 230))
    pal.setColor(Role.Highlight, _C(42, 130, 218))
    pal.setColor(Role.HighlightedText, _C(0, 0, 0))
    pal.setColor(Role.PlaceholderText, _C(150, 150, 150))

    disabled = _C(120, 120, 120)
    for role in (Role.WindowText, Role.Text, Role.ButtonText):
        pal.setColor(Group.Disabled, role, disabled)

    app.setPalette(pal)
