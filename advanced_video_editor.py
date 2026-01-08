import sys
import os
import logging
import traceback
import ctypes
from ctypes.wintypes import HWND, UINT, DWORD
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from system import setup_system, StreamToLogger
from binary_manager import BinaryManager

def exception_hook(exctype, value, tb):
    """Goal 19: Global Exception Hook for Emergency Sidecar Recovery."""
    err_msg = "".join(traceback.format_exception(exctype, value, tb))
    logger = logging.getLogger("Advanced_Video_Editor")
    logger.critical(f"CORE CRASH DETECTED:\n{err_msg}")
    if 'window' in globals() and window:
        try:
            logger.info("[RECOVERY] Initializing Emergency Sidecar Dump...")
            window.save_crash_backup()
            logger.info("[RECOVERY] Emergency backup successful. Check project.sidecar.json.")
        except Exception as e:
            logger.critical(f"[RECOVERY] Sidecar dump FAILED: {e}")
    sys.__excepthook__(exctype, value, tb)

def enable_drag_drop_for_elevated_app(hwnd):
    MSGFLT_ADD = 1
    WM_DROPFILES = 0x0233
    WM_COPYDATA = 0x004A
    WM_COPYGLOBALDATA = 0x0049
    user32 = ctypes.WinDLL("user32")
    ChangeWindowMessageFilterEx = user32.ChangeWindowMessageFilterEx
    ChangeWindowMessageFilterEx.argtypes = [HWND, UINT, DWORD, ctypes.POINTER(ctypes.c_void_p)]
    ChangeWindowMessageFilterEx.restype = ctypes.c_bool
    success_dropfiles = ChangeWindowMessageFilterEx(HWND(hwnd), WM_DROPFILES, MSGFLT_ADD, None)
    success_copydata = ChangeWindowMessageFilterEx(HWND(hwnd), WM_COPYDATA, MSGFLT_ADD, None)
    success_globaldata = ChangeWindowMessageFilterEx(HWND(hwnd), WM_COPYGLOBALDATA, MSGFLT_ADD, None)
    if success_dropfiles and success_copydata:
        logging.getLogger("Advanced_Video_Editor").info(f"Successfully enabled drag and drop messages for HWND: {hwnd}")
        return True
    else:
        logging.getLogger("Advanced_Video_Editor").warning(f"Failed to enable some drag and drop messages for HWND: {hwnd}")
        return False
if __name__ == "__main__":
    sys.excepthook = exception_hook
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base_dir)
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    logger = setup_system(base_dir)
    sys.stdout = StreamToLogger(logger, logging.INFO)
    sys.stderr = StreamToLogger(logger, logging.ERROR)
    logger.info("=== Booting Advanced Video Editor ===")

    logger.info("Importing MainWindow...")
    from main_window import MainWindow
    logger.info("Creating QApplication...")
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
        logger.info("Creating MainWindow...")
        file_to_load = sys.argv[1] if len(sys.argv) > 1 else None
        window = MainWindow(base_dir, file_to_load=file_to_load)
        logger.info("Showing MainWindow...")
        window.show()
        native_hwnd = window.winId().__int__()
        if enable_drag_drop_for_elevated_app(native_hwnd):
            logger.info(f"[UIPI] Firewall bypassed for HWND {native_hwnd}. Drag-and-drop is now enabled for Admin mode.")
        else:
            logger.error("[UIPI] Failed to apply elevation workaround.")
        logger.info("Starting app event loop...")
        sys.exit(app.exec_())
    except Exception as e:
        logger.critical(f"FATAL CRASH during app execution: {e}", exc_info=True)
        if 'window' in globals() and hasattr(window, 'save_crash_backup'):
            try:
                window.save_crash_backup()
            except Exception:
                pass
        sys.exit(1)