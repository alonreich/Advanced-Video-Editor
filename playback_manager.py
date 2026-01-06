import logging
import vlc
import os
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
        self.canvas_width = 1920
        self.canvas_height = 1080
        self.current_playing_uid = None

    def set_resolution(self, w, h):
        """Updates the internal canvas size for the renderer."""
        if self.canvas_width != w or self.canvas_height != h:
            self.canvas_width = w
            self.canvas_height = h
            self.mark_dirty(serious=True)

    def mark_dirty(self, serious=True):
        """Only force a full rebuild for structural timeline changes."""
        if serious:
            self.is_dirty = True
        else:
            pass

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
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            return
        self._rebuild_and_play(proxy_enabled, track_vols, track_mutes)

    def _get_top_clip_at(self, time):
        """Calculates which clip should be visible (Z-Index King) at a specific time."""
        state = self.timeline.get_state()
        if not state: return None
        active_clips = [c for c in state if c['start'] <= time < (c['start'] + c['dur'])]
        visible_clips = [c for c in active_clips if c.get('media_type') == 'video' or c.get('has_video')]
        if not visible_clips: return None
        visible_clips.sort(key=lambda x: x['track'], reverse=True)
        return visible_clips[0]

    def _rebuild_and_play(self, proxy_enabled, track_vols, track_mutes):
        """Loads the top-most clip at the playhead and applies VLC filters."""
        current_time = self.timeline.playhead_pos
        target = self._get_top_clip_at(current_time)
        self.current_playing_uid = target['uid'] if target else None
        target_clips = [target] if target else []
        gen = FilterGraphGenerator(target_clips, width=self.canvas_width, height=self.canvas_height)
        inputs, vlc_filters, v_pad, a_pad, is_vid = gen.build(for_vlc=True, duration=1.0)
        play_path = None
        if target:
            play_path = target['path']
            if proxy_enabled and target.get('proxy_path'):
                if os.path.exists(target['proxy_path']):
                    play_path = target['proxy_path']
                    self.logger.info(f"[PLAYBACK] Using Proxy: {play_path}")
        try:
            if play_path:
                self.player.load(play_path)
                self.player.set_speed(target.get('speed', 1.0))
                self.player.set_volume(target.get('volume', 100.0))
                if any(k.startswith('crop_') for k in target.keys()):
                    self.player.apply_crop(target)
                self.player.play()
                internal_seek = (current_time - target['start']) + target.get('source_in', 0)
                self.player.seek(max(0.0, internal_seek))
                self.is_dirty = False
                self.timer.start()
                self.state_changed.emit(True)
            else:
                self.player.stop()
                self.timer.start()
                self.state_changed.emit(True)
        except Exception as e:
            self.logger.error(f"[VLC-PLAYBACK] Failed: {e}")

    def _sync_playhead(self):
        """Main loop: Syncs UI playhead AND checks for Z-Index changes (Hot Swap)."""
        if self.timeline.timeline_view.is_dragging_playhead: 
            return
        if self.player.is_playing():
            t = self.player.get_time()
            if abs(t - self.timeline.playhead_pos) > 0.05:
                self.playhead_updated.emit(t)
        else:
            t = self.timeline.playhead_pos + 0.033
            self.playhead_updated.emit(t)
        current_t = self.timeline.playhead_pos
        expected_top = self._get_top_clip_at(current_t)
        expected_uid = expected_top['uid'] if expected_top else None
        if expected_uid != self.current_playing_uid:
            self.logger.debug(f"[PLAYBACK] Z-Index Change Detected. Hot swapping to {expected_uid}")
            self.toggle_play()
            self.toggle_play()
        max_end = self.timeline.get_content_end() if hasattr(self.timeline, 'get_content_end') else 1000
        if max_end > 0 and current_t >= max_end:
            self.player.pause()
            self.timer.stop()
            self.player.seek(max_end)
            self.state_changed.emit(False)