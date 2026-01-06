import logging
import re
import mpv
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from binary_manager import BinaryManager
class MPVPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        BinaryManager.ensure_env()
        self.mpv = None
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self._playing = False

    def initialize_mpv(self, wid):
        if self.mpv:
            return
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
        _orig_command = self.mpv.command

        def _logged_command(*args):
            try:
                self.logger.info("[MPV-CMD] mpv.command(" + ", ".join(repr(a) for a in args) + ")")
            except Exception:
                pass
            return _orig_command(*args)
        self.mpv.command = _logged_command

    def _on_mpv_log(self, level, component, message):
        try:
            self.logger.debug(f"[mpv:{level}:{component}] {message}")
        except Exception:
            pass

    def load(self, path: str):
        if not self.mpv or not path:
            return
        self.mpv.command("loadfile", path, "replace")
        self._playing = False

    def play(self):
        if not self.mpv:
            return
        self.mpv.pause = False
        self._playing = True

    def pause(self):
        if not self.mpv:
            return
        self.mpv.pause = True
        self._playing = False

    def stop(self):
        if not self.mpv:
            return
        try:
            self.mpv.command("stop")
        except Exception:
            pass
        self._playing = False

    def seek(self, seconds: float):
        if not self.mpv:
            return
        try:
            self.mpv.command("seek", float(seconds), "absolute")
        except Exception:
            pass

    def seek_relative(self, seconds: float):
        if not self.mpv:
            return
        try:
            self.mpv.command("seek", float(seconds), "relative")
        except Exception:
            pass

    def set_volume(self, volume: float):
        if not self.mpv:
            return
        try:
            self.mpv.volume = max(0.0, float(volume))
        except Exception as e:
            self.logger.error(f"Live volume update failed: {e}")

    def update_live_speed(self, speed: float):
        if not self.mpv:
            return
        try:
            self.mpv.speed = max(0.1, float(speed))
        except Exception as e:
            self.logger.error(f"Live speed update failed: {e}")

    def update_filter_param(self, label, param, value):
        if not self.mpv:
            return
        try:
            self.mpv.command("vf-command", label, param, str(value))
        except Exception:
            pass

    def is_playing(self) -> bool:
        return self._playing

    def get_time(self) -> float:
        if not self.mpv:
            return 0.0
        try:
            return float(self.mpv.time_pos or 0.0)
        except Exception:
            self._playing = False
            return 0.0

    def _ffmpeg_labels_to_mpv(self, graph: str) -> str:
        def repl_v(m):
            idx = int(m.group(1))
            return f"[vid{idx + 1}]"

        def repl_a(m):
            idx = int(m.group(1))
            return f"[aid{idx + 1}]"
        graph = re.sub(r"\[(\d+):v\]", repl_v, graph)
        graph = re.sub(r"\[(\d+):a\]", repl_a, graph)
        return graph

    def play_filter_graph(self, filter_str: str, inputs: list, main_input_used_for_video: bool):
        if not self.mpv:
            self.logger.error("MPV not initialized, cannot play filter graph.")
            return
        clean_inputs = [i for i in inputs if i and isinstance(i, str) and i.strip()]
        if not clean_inputs:
            self.logger.error("[MPV] No valid input files provided to play_filter_graph. Aborting.")
            self.stop()
            return
        graph = (filter_str or "").replace("\n", "").strip()
        if not graph:
            self.logger.error("[MPV] An empty filter graph was provided. Aborting.")
            self.stop()
            return
        main_input = clean_inputs[0]
        external_files = clean_inputs[1:]
        graph = self._ffmpeg_labels_to_mpv(graph)
        try:
            self.mpv.pause = True
            self._playing = False
            try:
                self.mpv.command("set", "lavfi-complex", "")
            except Exception:
                pass
            try:
                self.mpv.external_files = external_files if external_files else []
            except Exception:
                if external_files:
                    self.mpv.command("set", "external-files", ",".join(external_files))
                else:
                    try:
                        self.mpv.command("set", "external-files", "")
                    except Exception:
                        pass
            self.logger.info(f"Loading main input: {main_input}")
            self.mpv.command("loadfile", main_input, "replace")
            self.logger.info(f"Setting lavfi-complex: {graph}")
            self.mpv.command("set", "lavfi-complex", graph)
            self.mpv.pause = False
            self._playing = True
            self.logger.info("Playback of filter graph initiated.")
        except Exception as e:
            self.logger.error(f"Failed to load and play complex filter graph: {e}", exc_info=True)
            self.stop()

    def apply_crop(self, clip_model):
        if not self.mpv:
            return
        try:
            x1 = float(getattr(clip_model, "crop_x1", 0.0))
            y1 = float(getattr(clip_model, "crop_y1", 0.0))
            x2 = float(getattr(clip_model, "crop_x2", 1.0))
            y2 = float(getattr(clip_model, "crop_y2", 1.0))
            w_expr = f"iw*({x2 - x1})"
            h_expr = f"ih*({y2 - y1})"
            x_expr = f"iw*({x1})"
            y_expr = f"ih*({y1})"
            self.mpv.vf = f"crop={w_expr}:{h_expr}:{x_expr}:{y_expr}"
        except Exception as e:
            self.logger.error(f"Crop application failed: {e}")
            self.mpv.vf = ""

    def cleanup(self):
        if not self.mpv:
            return
        try:
            self.mpv.terminate()
        except Exception:
            pass