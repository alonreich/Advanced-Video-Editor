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
        if self.mpv or not wid or wid <= 0:
            return
        self.mpv = mpv.MPV(
            wid=wid,
            osc=False,
            input_default_bindings=False,
            input_vo_keyboard=False,
            keep_open=True,
            pause=True,
            log_handler=self._on_mpv_log,
            loglevel="error",
            hwdec='auto',
            vo='gpu',
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

    def seek(self, seconds: float, fast=False):
        """Goal 8: Adaptive seeking. Use fast=True to hit keyframes only."""
        if not self.mpv:
            return
        try:
            mode = "absolute+keyframes" if fast else "absolute+exact"
            self.mpv.command("seek", str(seconds), mode)
        except Exception as e:
            if "-12" in str(e):
                self.logger.warning(f"[MPV] Seek ignored: Backend not ready.")
            else:
                self.logger.error(f"Seek failed: {e}")

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

    def play_filter_graph(self, filter_str: str, inputs: list, main_input_used_for_video: bool):
        if not self.mpv:
            self.logger.error("MPV not initialized, cannot play filter graph.")
            return
        clean_inputs = [i for i in inputs if i and isinstance(i, str) and i.strip()]
        if not clean_inputs:
            self.logger.warning("[MPV] No valid input files found for current range. Playback idle.")
            self.stop()
            return
        graph = (filter_str or "").replace("\n", "").strip()
        if not graph:
            self.logger.error("[MPV] Filter graph is empty. Aborting playback.")
            self.stop()
            return

        source_defs = []
        created_pads = set()

        def input_replacer(match):
            idx = int(match.group(1))
            stream_type = match.group(2)
            if idx >= len(clean_inputs): 
                return f"[{idx}:{stream_type}]"
            path = clean_inputs[idx].replace('\\', '/').replace("'", "'\\''").replace(":", "\\:")
            pad_name = f"src_{idx}_{stream_type}"
            if pad_name not in created_pads:
                filter_name = "movie" if stream_type == 'v' else "amovie"
                source_defs.append(f"{filter_name}='{path}':loop=0[{pad_name}]")
                created_pads.add(pad_name)
            return f"[{pad_name}]"

        try:
            self.mpv.pause = True
            self._playing = False
            final_graph = re.sub(r"\[(\d+):([va])\]", input_replacer, graph)
            full_command = f"{';'.join(source_defs)};{final_graph}"
            self.logger.info(f"[MPV] Loading self-contained graph via lavfi://")
    
            self.mpv.command("loadfile", f"lavfi://[{full_command}]", "replace")
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