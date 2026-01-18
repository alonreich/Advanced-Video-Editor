import sys
import os
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

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
    if not hasattr(exception_hook, '_recursion_depth'):
        exception_hook._recursion_depth = 0
    exception_hook._recursion_depth += 1
    try:
        if exception_hook._recursion_depth < 3 and 'window' in globals() and window:
            try:
                logger.info("[RECOVERY] Initializing Emergency Sidecar Dump...")
                window.save_crash_backup()
                logger.info("[RECOVERY] Emergency backup successful. Check project.sidecar.json.")
            except Exception as e:
                logger.critical(f"[RECOVERY] Sidecar dump FAILED: {e}")
                exception_hook._recursion_depth = 3
    finally:
        exception_hook._recursion_depth = max(0, exception_hook._recursion_depth - 1)
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
    successes = {}
    failures = {}
    success_dropfiles = ChangeWindowMessageFilterEx(HWND(hwnd), WM_DROPFILES, MSGFLT_ADD, None)
    successes['WM_DROPFILES'] = success_dropfiles
    success_copydata = ChangeWindowMessageFilterEx(HWND(hwnd), WM_COPYDATA, MSGFLT_ADD, None)
    successes['WM_COPYDATA'] = success_copydata
    success_globaldata = ChangeWindowMessageFilterEx(HWND(hwnd), WM_COPYGLOBALDATA, MSGFLT_ADD, None)
    successes['WM_COPYGLOBALDATA'] = success_globaldata
    logger = logging.getLogger("Advanced_Video_Editor")
    for msg, success in successes.items():
        if success:
            logger.debug(f"[UIPI] Successfully enabled {msg} for HWND: {hwnd}")
        else:
            logger.warning(f"[UIPI] Failed to enable {msg} for HWND: {hwnd}")
    if all(successes.values()):
        logger.info(f"[UIPI] Fully enabled drag and drop for HWND: {hwnd}")
        return True
    elif successes['WM_DROPFILES'] and successes['WM_COPYDATA']:
        logger.info(f"[UIPI] Partially enabled drag and drop (missing WM_COPYGLOBALDATA) for HWND: {hwnd}")
        return True
    else:
        logger.error(f"[UIPI] Critical drag-drop messages failed for HWND: {hwnd}")
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
    try:
        from system import ConfigManager
        config = ConfigManager(os.path.join(base_dir, "config", "Advanced_Video_Editor.conf"))
        binary_manager = BinaryManager(config)
        binary_manager.ensure_env()
        # Set MPV_LIBRARY to libmpv-2.dll for python-mpv
        bin_dir = binary_manager.get_bin_path()
        libmpv_path = os.path.join(bin_dir, "libmpv-2.dll")
        if os.path.exists(libmpv_path):
            os.environ["MPV_LIBRARY"] = libmpv_path
            logger.info(f"Set MPV_LIBRARY to {libmpv_path}")
        else:
            logger.warning(f"libmpv-2.dll not found at {libmpv_path}")
        logger.info("Binary environment set up successfully")
    except Exception as e:
        logger.error(f"Failed to set up binary environment: {e}")
    logger.info("Importing MainWindow...")
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
        from main_window import MainWindow
        logger.info("Creating MainWindow...")
        file_to_load = sys.argv[1] if len(sys.argv) > 1 else None
        window = MainWindow(base_dir, binary_manager, file_to_load=file_to_load)
        logger.info("Showing MainWindow...")
        window.show()
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if is_admin:
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
