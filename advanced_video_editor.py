import sys
import os
import logging
import traceback

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from system import setup_system, StreamToLogger
from binary_manager import BinaryManager

def exception_hook(exctype, value, tb):
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    logging.getLogger("Advanced_Video_Editor").critical(f"Uncaught Exception:\n{err_msg}")
    if 'window' in globals() and hasattr(window, 'save_crash_backup'):
        try:
            window.save_crash_backup()
        except Exception:
            pass
    sys.__excepthook__(exctype, value, tb)
if __name__ == "__main__":
    sys.excepthook = exception_hook
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base_dir)
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    logger = setup_system(base_dir)
    sys.stdout = StreamToLogger(logger, logging.INFO)
    sys.stderr = StreamToLogger(logger, logging.ERROR)
    logger.info("=== Booting Advanced Video Editor ===")
    BinaryManager.ensure_env()
    from main_window import MainWindow
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
    try:
        window = MainWindow(base_dir)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"FATAL CRASH during app execution: {e}", exc_info=True)
        if 'window' in globals() and hasattr(window, 'save_crash_backup'):
            try:
                window.save_crash_backup()
            except Exception:
                pass
        sys.exit(1)
