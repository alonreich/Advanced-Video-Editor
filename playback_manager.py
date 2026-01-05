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

    def mark_dirty(self, serious=True):
        """Only force a full rebuild for structural timeline changes."""
        if serious:
            self.is_dirty = True
            self.logger.debug("Playback Manager: Structural change detected. Full rebuild required.")
        else:
            self.logger.debug("Playback Manager: Visual parameter change. Using live update.")

    def live_param_update(self, param, value):
        """Routes inspector changes directly to the player without flickering."""
        if param == "volume":
            self.player.set_volume(value)
        elif param == "speed":
            self.player.update_live_speed(value)

    def toggle_play(self, proxy_enabled=False, track_vols=None, track_mutes=None):
        if self.player.is_playing():
            self.player.pause()
            self.timer.stop()
            self.state_changed.emit(False)
            return
        if not self.is_dirty and self.player.is_playing():
            self.logger.info("[PLAYBACK] Clean Resume.")
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            return
        self._rebuild_and_play(proxy_enabled, track_vols, track_mutes)

    def _rebuild_and_play(self, proxy_enabled, track_vols, track_mutes):
        """VLC-Only: Loads the top-most clip at the playhead and applies VLC filters."""
        state = self.timeline.get_state()
        if not state: return
        current_time = self.timeline.playhead_pos
        active_clips = [c for c in state if c['start'] <= current_time <= (c['start'] + c['dur'])]
        active_clips.sort(key=lambda x: x['track'], reverse=True)
        if not active_clips:
            self.player.stop()
            return
        target = active_clips[0]
        gen = FilterGraphGenerator([target])
        inputs, vlc_filters, v_pad, a_pad, is_vid = gen.build(for_vlc=True)
        try:
            self.player.load(target['path'])
            if vlc_filters:
                self.player.player.video_set_logo_string(vlc.VideoLogoOption.enable, 1)
            self.player.set_speed(target.get('speed', 1.0))
            self.player.set_volume(target.get('volume', 100.0))
            self.player.play()
            internal_seek = (current_time - target['start']) + target.get('source_in', 0)
            self.player.seek(max(0.0, internal_seek))
            self.is_dirty = False
            self.timer.start()
            self.state_changed.emit(True)
        except Exception as e:
            self.logger.error(f"[VLC-PLAYBACK] Failed: {e}")

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
