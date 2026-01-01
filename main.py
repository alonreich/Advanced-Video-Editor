import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from system import setup_system
from main_window import MainWindow
if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base_dir)
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    logger = setup_system(base_dir)
    logger.info("=== Booting ProEditor v2.0 (Semi-Pro) ===")
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        from PyQt5.QtGui import QPalette, QColor
        p = app.palette()
        p.setColor(QPalette.Window, QColor(53, 53, 53))
        p.setColor(QPalette.WindowText, Qt.white)
        p.setColor(QPalette.Base, QColor(25, 25, 25))
        p.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        p.setColor(QPalette.ToolTipBase, Qt.white)
        p.setColor(QPalette.ToolTipText, Qt.white)
        p.setColor(QPalette.Text, Qt.white)
        p.setColor(QPalette.Button, QColor(53, 53, 53))
        p.setColor(QPalette.ButtonText, Qt.white)
        p.setColor(QPalette.BrightText, Qt.red)
        p.setColor(QPalette.Link, QColor(42, 130, 218))
        p.setColor(QPalette.Highlight, QColor(42, 130, 218))
        p.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(p)
        window = MainWindow(base_dir)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"FATAL CRASH: {e}", exc_info=True)
        sys.exit(1)
