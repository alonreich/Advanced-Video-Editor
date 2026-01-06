import sys
import os
import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QFrame
from PyQt5.QtCore import Qt
import vlc

class VLCPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.instance = vlc.Instance("--no-xlib --quiet")
        self.mediaplayer = self.instance.media_player_new()
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_frame)
        self.setLayout(layout)
        if sys.platform.startswith("linux"):
            self.mediaplayer.set_xwindow(self.video_frame.winId())
        elif sys.platform == "win32":
            self.mediaplayer.set_hwnd(self.video_frame.winId())
        elif sys.platform == "darwin":
            self.mediaplayer.set_nsobject(int(self.video_frame.winId()))

    def load(self, path):
        media = self.instance.media_new(path)
        self.mediaplayer.set_media(media)

    def play(self):
        self.mediaplayer.play()

    def pause(self):
        self.mediaplayer.pause()

    def stop(self):
        self.mediaplayer.stop()

    def is_playing(self):
        return self.mediaplayer.is_playing()

    def set_time(self, ms):
        self.mediaplayer.set_time(int(ms))

    def get_time(self):
        return self.mediaplayer.get_time() / 1000.0

    def seek(self, seconds):
        self.set_time(seconds * 1000)

    def seek_relative(self, delta):
        current = self.get_time()
        self.seek(current + delta)

    def set_volume(self, volume):
        self.mediaplayer.audio_set_volume(int(volume))

    def set_speed(self, speed):
        self.mediaplayer.set_rate(speed)
        
    def update_live_speed(self, speed):
        """Updates speed without reloading."""
        self.mediaplayer.set_rate(speed)

    def apply_crop(self, clip_data):
        """
        Goal 10: Apply crop geometry to the VLC video output.
        VLC uses a string format 'W:H:X:Y' for crop geometry.
        """
        try:
            if not any(k.startswith('crop_') for k in clip_data):
                self.mediaplayer.video_set_crop_geometry(None)
                return
            x1 = clip_data.get('crop_x1', 0.0)
            y1 = clip_data.get('crop_y1', 0.0)
            x2 = clip_data.get('crop_x2', 1.0)
            y2 = clip_data.get('crop_y2', 1.0)
            w = self.mediaplayer.video_get_width()
            h = self.mediaplayer.video_get_height()
            if w <= 0 or h <= 0:
                return
            crop_x = int(x1 * w)
            crop_y = int(y1 * h)
            crop_w = int((x2 - x1) * w)
            crop_h = int((y2 - y1) * h)
            if crop_w <= 0 or crop_h <= 0:
                self.mediaplayer.video_set_crop_geometry(None)
                return
            geometry = f"{crop_w}x{crop_h}+{crop_x}+{crop_y}"
            self.mediaplayer.video_set_crop_geometry(geometry)
        except Exception as e:
            self.logger.error(f"[VLC] Apply crop failed: {e}")