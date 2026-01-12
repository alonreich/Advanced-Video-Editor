from PyQt5.QtGui import QColor
TRACK_HEIGHT = 40
RULER_HEIGHT = 30
DEFAULT_TIMELINE_SCALE_FACTOR = 50
TRACK_HEADER_WIDTH = 120
MAX_TRACKS = 50
DEFAULT_DOCK_WIDTH_POOL = 228
DEFAULT_DOCK_WIDTH_INSPECTOR = 250
DEFAULT_DOCK_HEIGHT_TIMELINE = 180
COLOR_BACKGROUND = QColor("#1E1E1E")
COLOR_PRIMARY = QColor("#4A90E2")
COLOR_TEXT = QColor("#E0E0E0")
COLOR_SUCCESS = QColor("#3D5A3D")
COLOR_ERROR = QColor("#7A2B2B")
STYLESHEET_MESSAGE_BOX = f"""
    QMessageBox {{ background-color: {COLOR_BACKGROUND.name()}; border: 2px solid #333; }}
    QLabel {{ color: {COLOR_TEXT.name()}; font-size: 14px; font-weight: bold; }}
"""
STYLESHEET_BUTTON_SUCCESS = f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLOR_SUCCESS.name()}, stop:0.2 {COLOR_SUCCESS.lighter(120).name()}, stop:0.5 {COLOR_SUCCESS.darker(120).name()}, stop:0.8 {COLOR_SUCCESS.darker(150).name()}, stop:1 {COLOR_SUCCESS.darker(180).name()});
        color: {COLOR_TEXT.lighter(100).name()}; border: 1px solid {COLOR_SUCCESS.lighter(70).name()}; border-radius: 2px; padding: 10px 20px; font-weight: bold;
        border-bottom: 3px solid {COLOR_SUCCESS.darker(200).name()};
    }}
    QPushButton:hover {{ background: {COLOR_SUCCESS.lighter(50).name()}; color: white; border: 1px solid {COLOR_SUCCESS.lighter(120).name()}; }}
    QPushButton:pressed {{ border-bottom: 1px solid {COLOR_SUCCESS.darker(200).name()}; margin-top: 2px; }}
"""
STYLESHEET_BUTTON_ERROR = f"""
    QPushButton {{
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {COLOR_ERROR.name()}, stop:0.2 {COLOR_ERROR.lighter(120).name()}, stop:0.5 {COLOR_ERROR.darker(120).name()}, stop:0.8 {COLOR_ERROR.darker(150).name()}, stop:1 {COLOR_ERROR.darker(180).name()});
        color: {COLOR_TEXT.lighter(100).name()}; border: 1px solid {COLOR_ERROR.lighter(70).name()}; border-radius: 2px; padding: 10px 20px; font-weight: bold;
        border-bottom: 3px solid {COLOR_ERROR.darker(200).name()};
    }}
    QPushButton:hover {{ background: {COLOR_ERROR.lighter(50).name()}; color: white; border: 1px solid {COLOR_ERROR.lighter(120).name()}; }}
    QPushButton:pressed {{ border-bottom: 1px solid {COLOR_ERROR.darker(200).name()}; margin-top: 2px; }}
"""