import os
import logging
from PyQt5.QtCore import QObject
from binary_manager import BinaryManager

class MPVPlayer(QObject):
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        BinaryManager.ensure_env()

        import mpv
        self.logger = logging.getLogger("Advanced_Video_Editor")
        wid = int(parent_widget.winId())
        self.mpv = mpv.MPV(
            wid=wid,
            osc=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            keep_open=True,
            pause=True,
            log_handler=self._on_mpv_log,
            loglevel="warn",
        )
        self._playing = False

    def _on_mpv_log(self, level, component, message):
        try:
            self.logger.debug(f"[mpv:{level}:{component}] {message}")
        except Exception:
            pass

    def load(self, path: str):
        if not path:
            return
        self.mpv.command("loadfile", path, "replace")
        self._playing = False

    def play(self):
        self.mpv.pause = False
        self._playing = True

    def pause(self):
        self.mpv.pause = True
        self._playing = False

    def stop(self):
        try:
            self.mpv.command("stop")
        except Exception:
            pass
        self._playing = False

    def seek(self, seconds: float):
        try:
            self.mpv.command("seek", float(seconds), "absolute")
        except Exception:
            pass

    def seek_relative(self, seconds: float):
        try:
            self.mpv.command("seek", float(seconds), "relative")
        except Exception:
            pass

    def set_speed(self, speed: float):
        try:
            self.mpv.speed = max(0.1, float(speed))
        except Exception:
            pass

    def set_volume(self, volume: float):
        try:
            self.mpv.volume = max(0.0, float(volume))
        except Exception:
            pass

    def is_playing(self) -> bool:
        return self._playing

    def apply_crop(self, clip_model):
        try:
            x1 = float(getattr(clip_model, "crop_x1", 0.0))
            y1 = float(getattr(clip_model, "crop_y1", 0.0))
            x2 = float(getattr(clip_model, "crop_x2", 1.0))
            y2 = float(getattr(clip_model, "crop_y2", 1.0))
            x1 = min(max(x1, 0.0), 1.0)
            y1 = min(max(y1, 0.0), 1.0)
            x2 = min(max(x2, 0.0), 1.0)
            y2 = min(max(y2, 0.0), 1.0)
            w_expr = f"iw*({x2 - x1})"
            h_expr = f"ih*({y2 - y1})"
            x_expr = f"iw*({x1})"
            y_expr = f"ih*({y1})"
            self.mpv.vf = f"crop={w_expr}:{h_expr}:{x_expr}:{y_expr}"
        except Exception:
            try:
                self.mpv.vf = ""
            except Exception:
                pass

    def cleanup(self):
        try:
            self.mpv.terminate()
        except Exception:
            pass
