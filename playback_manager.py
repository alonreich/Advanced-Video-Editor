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
        if not self.is_dirty and self.player.get_time() > 0:
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            return
        self._rebuild_and_play(proxy_enabled, track_vols, track_mutes)

    def _rebuild_and_play(self, proxy_enabled, track_vols, track_mutes):
        """Rebuilds the FFmpeg filter graph and sends it to the player."""
        self.logger.debug("Rebuilding filter graph for playback...")
        current_time = self.timeline.playhead_pos
        state = self.timeline.get_state()
        if not state:
            self.player.stop()
            self.state_changed.emit(False)
            self.logger.warning("No clips on timeline, stopping playback.")
            return
        gen = FilterGraphGenerator(
            state,
            width=self.canvas_width,
            height=self.canvas_height,
            volumes=track_vols,
            mutes=track_mutes
        )
        inputs, complex_filter, v_pad, a_pad, main_input_used = gen.build(
            start_time=current_time,
            duration=self.timeline.get_content_end(),
            is_export=False
        )
        try:
            self.player.play_filter_graph(complex_filter, inputs, main_input_used)
            self.player.play()
            self.player.seek(current_time)
            self.is_dirty = False
            self.timer.start()
            self.state_changed.emit(True)
            self.logger.info(f"Playback started with filter graph at {current_time:.2f}s.")
        except Exception as e:
            self.logger.error(f"[FFMPEG-PLAYBACK] Failed to load complex filter: {e}", exc_info=True)
            self.player.stop()
            self.state_changed.emit(False)

    def _sync_playhead(self):
        """Main loop: Syncs UI playhead from player time."""
        if self.timeline.timeline_view.is_dragging_playhead:
            return
        if not self.player.is_playing():
            return
        try:
            current_player_time = self.player.get_time()
        except Exception as e:
            self.logger.error(f"[MPV] Playback core stopped: {e}")
            self.player.stop()
            self.timer.stop()
            self.state_changed.emit(False)
            return
        self.playhead_updated.emit(current_player_time)
        max_end = self.timeline.get_content_end()
        if max_end > 0 and current_player_time >= max_end:
            self.player.pause()
            self.timer.stop()
            self.playhead_updated.emit(max_end)
            self.state_changed.emit(False)
