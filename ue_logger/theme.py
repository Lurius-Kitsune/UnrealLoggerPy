"""Dark palette and visual components inspired by iOS and HeroUI."""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_dark_theme(app: QApplication) -> None:
    """Apply layered colors, soft borders, and a clear blue accent."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#10141b"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e5eaf2"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111720"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#171e29"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e5eaf2"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#202a38"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e5eaf2"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2563eb"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#202a38"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f4f7fb"))
    app.setPalette(palette)
    app.setStyleSheet(_application_stylesheet())


def _application_stylesheet() -> str:
    """Return shared styles for Qt panels, fields, and controls."""
    return """
        QWidget {
            color: #e5eaf2;
            font-family: 'Segoe UI';
            font-size: 9pt;
        }
        QMainWindow, QMainWindow > QWidget { background: #10141b; }
        QToolBar {
            background: #151b25;
            border: 0;
            border-bottom: 1px solid #273142;
            spacing: 7px;
            padding: 8px 10px;
        }
        QToolBar QToolButton {
            background: transparent;
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 7px 10px;
        }
        QToolBar QToolButton:hover { background: #202a38; border-color: #334155; }
        QToolBar QToolButton:checked { background: #1d4ed8; color: #ffffff; }
        QDockWidget::title {
            background: #151b25;
            color: #aab6c8;
            padding: 11px 12px;
            border-bottom: 1px solid #273142;
            font-weight: 600;
        }
        QDockWidget::widget { background: #121822; border: 0; }
        QGroupBox {
            background: #171e29;
            border: 1px solid #273142;
            border-radius: 10px;
            margin-top: 12px;
            padding: 12px 8px 8px;
            font-weight: 600;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; color: #aab6c8; }
        QLineEdit, QComboBox, QDateTimeEdit, QPlainTextEdit, QListWidget {
            background: #111720;
            border: 1px solid #2b3545;
            border-radius: 9px;
            padding: 7px 9px;
            selection-background-color: #2563eb;
        }
        QLineEdit:focus, QComboBox:focus, QDateTimeEdit:focus, QPlainTextEdit:focus, QListWidget:focus {
            border: 1px solid #4f8cff;
        }
        QComboBox::drop-down, QDateTimeEdit::drop-down { border: 0; width: 24px; }
        QPushButton {
            background: #202a38;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 7px 12px;
            font-weight: 600;
        }
        QPushButton:hover { background: #2a3749; border-color: #4a5a70; }
        QPushButton:pressed { background: #1d4ed8; }
        QCheckBox { spacing: 8px; padding: 3px 2px; }
        QCheckBox::indicator { width: 16px; height: 16px; }
        QCheckBox::indicator:unchecked {
            background: #111720; border: 1px solid #48566b; border-radius: 5px;
        }
        QCheckBox::indicator:checked {
            background: #3b82f6; border: 1px solid #60a5fa; border-radius: 5px;
        }
        QTableView {
            background: #111720;
            alternate-background-color: #151c27;
            border: 1px solid #273142;
            border-radius: 11px;
            gridline-color: transparent;
            outline: 0;
            selection-background-color: #1e3a5f;
            selection-color: #f4f7fb;
        }
        QTableView::item { padding: 4px 7px; border: 0; }
        QHeaderView::section {
            background: #1a2230;
            color: #aab6c8;
            border: 0;
            border-bottom: 1px solid #2b3545;
            padding: 9px 8px;
            font-weight: 600;
        }
        QHeaderView::section:hover { background: #222d3d; color: #ffffff; }
        QHeaderView::down-arrow, QHeaderView::up-arrow { width: 9px; height: 9px; }
        #chartPanel {
            background: #151b25;
            border: 1px solid #273142;
            border-radius: 12px;
        }
        #socketStatus[status="connected"] {
            background: #142a24;
            color: #69d6a7;
            border: 1px solid #24533f;
            border-radius: 10px;
            padding: 6px 10px;
            font-weight: 600;
        }
        #socketStatus[status="unavailable"] {
            background: #321c21; color: #ff9b9b; border: 1px solid #67303a;
            border-radius: 10px; padding: 6px 10px; font-weight: 600;
        }
        #socketStatus[status="starting"] {
            background: #302719; color: #f0c674; border: 1px solid #5e4b27;
            border-radius: 10px; padding: 6px 10px; font-weight: 600;
        }
        QStatusBar { background: #151b25; color: #9aa8bb; border-top: 1px solid #273142; }
        QSplitter::handle { background: #10141b; }
        QSplitter::handle:horizontal { width: 5px; }
        QSplitter::handle:vertical { height: 6px; }
        QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
        QScrollBar::handle:vertical { background: #354154; min-height: 28px; border-radius: 5px; }
        QScrollBar::handle:vertical:hover { background: #4b5c74; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
        QScrollBar::handle:horizontal { background: #354154; min-width: 28px; border-radius: 5px; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QToolTip { background: #202a38; color: #f4f7fb; border: 1px solid #46556b; padding: 6px 8px; }
    """
