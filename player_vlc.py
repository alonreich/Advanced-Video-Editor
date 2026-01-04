import vlc
import sys
import logging
from PyQt5.QtWidgets import QWidget

class VLCPlayer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.instance = vlc.Instance('--no-xlib', '--quiet')
        self.player = self.instance.media_player_new()
        if sys.platform == "win32":
            self.player.set_hwnd(int(self.winId()))
        else:
            self.player.set_xwindow(int(self.winId()))

    def play_filter_graph(self, filter_str, inputs, main_input_used_for_video=False):
        if inputs:
            media = self.instance.media_new(inputs[0])
            self.player.set_media(media)
            self.player.play()

    def seek_relative(self, delta):
        new_time = self.player.get_time() + int(delta * 1000)
        self.player.set_time(max(0, new_time))

    def get_time(self):
        return self.player.get_time() / 1000.0

    def is_playing(self):
        return self.player.is_playing()
