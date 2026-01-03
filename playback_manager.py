import logging
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from ffmpeg_generator import FilterGraphGenerator

class PlaybackManager(QObject):
    playhead_updated = pyqtSignal(float)
    state_changed = pyqtSignal(bool)

    def __init__(self, player_node, timeline, inspector):
        super().__init__()
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.player = player_node
        self.timeline = timeline
        self.inspector = inspector
        self.is_dirty = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._sync_playhead)
        self.timer.setInterval(33)

    def mark_dirty(self):
        self.is_dirty = True
        self.logger.debug("Playback Manager: Marked Dirty.")

    def toggle_play(self, proxy_enabled=False, track_vols=None, track_mutes=None):
        if self.player.is_playing():
            self.player.pause()
            self.timer.stop()
            self.state_changed.emit(False)
            return
        if not self.is_dirty and self.player.mpv:
            self.logger.info("[PLAYBACK] Clean Resume.")
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            return
        self._rebuild_and_play(proxy_enabled, track_vols, track_mutes)

    def _rebuild_and_play(self, proxy_enabled, track_vols, track_mutes):
        state = self.timeline.get_state()
        if not state:
            self.logger.warning("[PLAYBACK] Empty State.")
            return
        current_time = self.timeline.playhead_pos
        res_txt = self.inspector.combo_res.currentText()
        w, h = (1080, 1920) if "Portrait" in res_txt else (1920, 1080)
        if "2560" in res_txt: w, h = 2560, 1440
        elif "3840" in res_txt: w, h = 3840, 2160
        if proxy_enabled:
            w //= 2; h //= 2
        self.logger.info(f"[PLAYBACK] Rebuilding Graph at {current_time:.2f}s...")
        gen = FilterGraphGenerator(state, w, h, track_vols, track_mutes)
        try:
            inputs, f_str, _, _ = gen.build(start_time=0.0)
            self.player.play_filter_graph(f_str, inputs)
            self.player.seek(current_time)
            self.is_dirty = False
            self.timer.start()
            self.state_changed.emit(True)
        except Exception as e:
            self.logger.error(f"[PLAYBACK CRASH] {e}", exc_info=True)

    def _sync_playhead(self):
        if not self.player.is_playing(): return
        t = self.player.get_time()
        if abs(t - self.timeline.playhead_pos) > 0.05:
            self.playhead_updated.emit(t)
        max_end = self.timeline.get_content_end() if hasattr(self.timeline, 'get_content_end') else 1000
        if max_end > 0 and t >= max_end:
            self.player.pause()
            self.timer.stop()
            self.player.seek(max_end)
            self.state_changed.emit(False)
