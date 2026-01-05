import vlc
import sys
import logging
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt

class VLCPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.instance = vlc.Instance('--no-xlib', '--hwdec=auto', '--verbose=2')
        if not self.instance:
            self.logger.critical("VLC binaries not found. Install VLC (64-bit) or check your PATH.")
            raise RuntimeError("VLC failed to initialize: libvlc.dll missing.")
        self._setup_vlc_logging()
        self.player = self.instance.media_player_new()
        self.player.set_hwnd(int(self.winId()))

    def _setup_vlc_logging(self):
        """Connects libvlc logging to the Python logger to monitor HW acceleration."""
        def vlc_log_callback(data, level, ctx, fmt, args):
            try:
                log_map = {0: logging.INFO, 1: logging.ERROR, 2: logging.WARNING, 3: logging.DEBUG}
                py_level = log_map.get(level, logging.DEBUG)
                import ctypes
                message = ctypes.string_at(fmt).decode('utf-8', 'ignore')
                if any(x in message.lower() for x in ["dxva2", "d3d11va", "hwdec", "using hardware"]):
                    self.logger.info(f"[VLC-HW-ACCEL] {message}")
                else:
                    self.logger.log(py_level, f"[VLC-INTERNAL] {message}")
            except Exception:
                pass
        try:
            self._vlc_cb = vlc.CallbackPrototype(None, ctypes.c_void_p, ctypes.c_int,
                                                ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p)(vlc_log_callback)
            vlc.libvlc_log_set(self.instance, self._vlc_cb, None)
            self.logger.info("[VLC-LOGGER] Internal VLC logging hooked successfully.")
        except Exception as e:
            self.logger.error(f"[VLC-LOGGER] Failed to hook libvlc logs: {e}")

    def load(self, path):
        """Loads a new media file into the VLC player."""
        media = self.instance.media_new(path)
        self.player.set_media(media)

    def play(self):
        self.player.play()

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def seek(self, seconds: float):
        self.player.set_time(int(seconds * 1000))

    def seek_relative(self, delta: float):
        new_time = self.player.get_time() + int(delta * 1000)
        self.player.set_time(max(0, new_time))

    def set_volume(self, volume: float):
        self.player.audio_set_volume(int(max(0, min(volume, 200))))

    def set_speed(self, speed: float):
        self.player.set_rate(max(0.1, float(speed)))

    def update_live_speed(self, speed: float):
        self.set_speed(speed)

    def get_time(self) -> float:
        t = self.player.get_time()
        return t / 1000.0 if t > 0 else 0.0

    def resizeEvent(self, event):
        """Ensure VLC internal window handles resizing to match overlay math."""
        super().resizeEvent(event)
        if hasattr(self, 'player') and self.player:
            self.player.set_hwnd(int(self.winId()))

    def is_playing(self) -> bool:
        return self.player.is_playing()

    def cleanup(self):
        self.player.stop()
        self.player.release()
        self.instance.release()
