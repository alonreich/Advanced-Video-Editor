import os
import logging
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from binary_manager import BinaryManager

class MPVPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        BinaryManager.ensure_env()

        import mpv
        self.logger = logging.getLogger("Advanced_Video_Editor")
        if not self.winId(): self.createWinId()
        self.mpv = mpv.MPV(
            wid=int(self.winId()),
            osc=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            keep_open=True,
            pause=True,
            log_handler=self._on_mpv_log,
            loglevel="warn",
        )
        _orig_command = self.mpv.command

        def _logged_command(*args):
            try:
                self.logger.info("[MPV-CMD] mpv.command(" + ", ".join(repr(a) for a in args) + ")")
            except Exception:
                pass
            return _orig_command(*args)
        self.mpv.command = _logged_command
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
        """Updates playback speed (min 0.1x)."""
        try:
            self.mpv.speed = max(0.1, float(speed))
        except Exception as e:
            self.logger.error(f"Speed update failed: {e}")

    def set_volume(self, volume: float):
        """Live volume update without playback interruption."""
        try:
            self.mpv.volume = max(0.0, float(volume))
        except Exception as e:
            self.logger.error(f"Live volume update failed: {e}")

    def update_live_speed(self, speed: float):
        """Updates playback speed on the fly."""
        try:
            self.mpv.speed = max(0.1, float(speed))
        except Exception as e:
            self.logger.error(f"Live speed update failed: {e}")

    def update_filter_param(self, label, param, value):
        """Advanced: Injects parameters into the running lavfi graph."""
        try:
            self.mpv.command("vf-command", label, param, str(value))
        except Exception:
            pass

    def is_playing(self) -> bool:
        return self._playing

    def play_filter_graph(self, filter_str: str, inputs: list, main_input_used_for_video: bool):
        if not inputs:
            self.stop()
            return
        try:
            main_input = inputs[0]
            if not main_input:
                self.logger.error("[MPV-CMD] Refusing to play: inputs[0] is empty/None")
                self.stop()
                return
            graph = (filter_str or "").replace("\n", "").strip()
            if not graph:
                self.logger.error("[MPV-CMD] Refusing to play: empty filter graph")
                self.stop()
                return
            extras = []
            for p in (inputs[1:] if len(inputs) > 1 else []):
                if not p:
                    continue
                s = str(p).strip()
                if not s or s.lower() == "none":
                    continue
                extras.append(s)
            try:
                self.mpv["lavfi-complex"] = graph
            except Exception:
                self.mpv.command("set", "lavfi-complex", graph)
            if main_input_used_for_video:
                self.mpv.command("loadfile", main_input, "replace")
            else:
                self.mpv.command("loadfile", main_input, "replace", "novideo")
            if extras:
                extra_str = ",".join(extras)
                try:
                    self.mpv["external-files"] = extra_str
                except Exception:
                    self.mpv.command("set", "external-files", extra_str)
            else:
                try:
                    self.mpv["external-files"] = ""
                except:
                    pass
            self.mpv.pause = False
            self._playing = True
        except Exception as e:
            self.logger.error(f"MPV Graph Load Failed: {e}", exc_info=True)

    def get_time(self) -> float:
        return self.mpv.time_pos or 0.0

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
        except Exception as e:
            self.logger.error(f"Crop application failed: {e}")
            self.mpv.vf = ""

    def cleanup(self):
        try:
            self.mpv.terminate()
        except Exception:
            pass
