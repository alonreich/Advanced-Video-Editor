import os
import sys
import logging
from PyQt5.QtWidgets import QFrame

# Add local binaries folder to path for libmpv
bin_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'binaries')

# Explicitly add the binaries path to the system's PATH
os.environ['PATH'] = bin_path + os.pathsep + os.environ['PATH']

# Also set MPV_HOME, which the python-mpv library might use
os.environ['MPV_HOME'] = bin_path

import mpv
class MPVPlayer(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("ProEditor")
        opts = {
            "input_default_bindings": True,
            "input_vo_keyboard": True,
            "osc": True,
            "keep_open": "yes",
            "hr_seek": "yes",
            "hwdec": "auto",
            "vd_lavc_threads": 4
        }
        try:
            self.mpv = mpv.MPV(wid=str(int(self.winId())), **opts)
        except Exception as e:
            self.logger.critical(f"MPV Init Failed: {e}")
            raise

    def load(self, path):
        if not os.path.exists(path):
            self.logger.error(f"File not found: {path}")
            return
        self.mpv.play(path)
        self.mpv.pause = True

    def play(self): self.mpv.pause = False
    def pause(self): self.mpv.pause = True
    def stop(self): self.mpv.stop()
    
    def seek(self, time_s):
        self.mpv.seek(time_s, reference="absolute", precision="exact")
    
    def get_time(self):
        t = self.mpv.time_pos
        return t if t is not None else 0.0

    def is_playing(self):
        return not self.mpv.pause

    def set_speed(self, speed):
        self.mpv.speed = float(speed)

    def set_volume(self, vol):
        self.mpv.volume = int(vol)

    def apply_crop(self, clip_model):
        if clip_model and (clip_model.crop_x1 != 0.0 or clip_model.crop_y1 != 0.0 or clip_model.crop_x2 != 1.0 or clip_model.crop_y2 != 1.0):
            w = clip_model.width * (clip_model.crop_x2 - clip_model.crop_x1)
            h = clip_model.height * (clip_model.crop_y2 - clip_model.crop_y1)
            x = clip_model.width * clip_model.crop_x1
            y = clip_model.height * clip_model.crop_y1
            vf_str = f"crop={w}:{h}:{x}:{y}"
            self.mpv.vf = vf_str
        else:
            self.mpv.vf = ""

    def destroy(self):
        self.mpv.terminate()
