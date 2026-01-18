import logging
import re
import os
import sys
# Ensure binaries path is in PATH before importing mpv
if 'binaries' not in os.path.dirname(__file__):
    # Attempt to locate binaries directory relative to this file
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(base_dir, "binaries")
    if os.path.exists(bin_dir):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        os.environ["MPV_LIBRARY"] = os.path.join(bin_dir, "libmpv-2.dll")
        sys.path.insert(0, bin_dir)
import mpv
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt
from binary_manager import BinaryManager

class MPVPlayer(QWidget):
    def __init__(self, parent=None, binary_manager=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_NativeWindow)
        if binary_manager:
            binary_manager.ensure_env()
        self.mpv = None
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self._playing = False
        self._lavfi_error_detected = False

    def initialize_mpv(self, wid):
        if self.mpv or not wid or wid <= 0:
            return
        self.logger.info(f"[MPV] Initializing MPV with window ID {wid}")
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
        self._lavfi_supported = self._test_lavfi_support()
        if not self._lavfi_supported:
            self.logger.info("[MPV] lavfi protocol not supported, playback will fallback to direct file loading.")
        else:
            self.logger.info("[MPV] lavfi protocol supported.")

    def _test_lavfi_support(self):
        """Test if lavfi protocol is supported by attempting to load a dummy lavfi URL."""
        try:
            self.logger.info("[MPV] Testing lavfi support...")
            self._lavfi_error_detected = False
            self.mpv.command("loadfile", "lavfi://color=c=black:s=2x2:d=0.1", "replace")
            # Wait a short time for error logs to appear
            import time
            time.sleep(0.1)
            self.logger.debug(f"[MPV] lavfi error detected flag: {self._lavfi_error_detected}")
            if self._lavfi_error_detected:
                self.logger.info("[MPV] lavfi test failed (error detected in logs).")
                return False
            self.logger.info("[MPV] lavfi test succeeded.")
            return True
        except Exception as e:
            self.logger.error(f"[MPV] lavfi test failed: {e}", exc_info=True)
            return False

    def lavfi_supported(self):
        """Return whether lavfi protocol is supported."""
        if not hasattr(self, '_lavfi_supported'):
            self._lavfi_supported = False
        if not self._lavfi_supported and self.mpv:
            # Retry test once
            self.logger.info("[MPV] lavfi support not yet determined, running test...")
            self._lavfi_supported = self._test_lavfi_support()
        return self._lavfi_supported

    def _on_mpv_log(self, level, component, message):
        try:
            self.logger.debug(f"[mpv:{level}:{component}] {message}")
            # Detect lavfi protocol errors
            if "lavfi" in message and ("No protocol handler" in message or "unsupported" in message.lower()):
                self._lavfi_error_detected = True
                self.logger.debug(f"[MPV] lavfi error detected: {message}")
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
        except Exception as e:
            self.logger.debug(f"[MPV] Ignored exception in stop: {e}")
        self._playing = False

    def seek(self, seconds: float, fast=False):
        """Goal 8: Adaptive seeking. Use fast=True to hit keyframes only."""
        if not self.mpv:
            return

        import time
        mode = "absolute+keyframes" if fast else "absolute+exact"
        max_attempts = 3
        initial_delay = 0.1
        max_delay = 0.5
        # Wait for player to be ready before first attempt
        ready = False
        for _ in range(10):
            try:
                # Try to get time position; if it doesn't raise, player is ready
                _ = self.mpv.time_pos
                ready = True
                break
            except Exception:
                time.sleep(0.02)
        if not ready:
            self.logger.debug("[MPV] Player not ready after waiting, proceeding anyway.")
        was_playing = self._playing
        if was_playing:
            self.pause()
            time.sleep(0.05)
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    delay = min(initial_delay * (2 ** attempt), max_delay)
                    time.sleep(delay)
                self.mpv.command("seek", str(seconds), mode)
                if was_playing:
                    time.sleep(0.05)
                    self.play()
                return
            except Exception as e:
                error_str = str(e)
                if "-12" in error_str or "backend not ready" in error_str.lower():
                    self.logger.debug(f"[MPV] Seek ignored: Backend not ready (attempt {attempt+1}).")
                else:
                    self.logger.error(f"Seek failed: {e}")
                    break
        self.logger.warning(f"[MPV] Seek failed after {max_attempts} attempts.")
        # If seek failed, try to reload the file with start offset?
        # Not implemented; fallback to rebuild in playback manager.

    def seek_relative(self, seconds: float):
        if not self.mpv:
            return
        import time
        max_attempts = 3
        initial_delay = 0.05
        max_delay = 0.5
        # Wait for player to be ready before first attempt
        ready = False
        for _ in range(5):
            try:
                _ = self.mpv.time_pos
                ready = True
                break
            except Exception:
                time.sleep(0.02)
        if not ready:
            self.logger.debug("[MPV] Player not ready for relative seek, proceeding anyway.")
        for attempt in range(max_attempts):
            try:
                if attempt > 0:
                    delay = min(initial_delay * (2 ** attempt), max_delay)
                    time.sleep(delay)
                self.mpv.command("seek", float(seconds), "relative")
                return
            except Exception as e:
                error_str = str(e)
                if "-12" in error_str or "backend not ready" in error_str.lower():
                    self.logger.debug(f"[MPV] Relative seek ignored: Backend not ready (attempt {attempt+1}).")
                else:
                    self.logger.error(f"Relative seek failed: {e}")
                    break
        self.logger.warning(f"[MPV] Relative seek failed after {max_attempts} attempts.")

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
