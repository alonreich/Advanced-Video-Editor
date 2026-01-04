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
        max_end = 0.0
        for c in state:
            try:
                end_t = float(c.get("start", 0.0)) + float(c.get("duration", 0.0))
                if end_t > max_end:
                    max_end = end_t
            except Exception:
                continue
        current_time = float(getattr(self.timeline, "playhead_pos", 0.0))
        if max_end > 0.0 and (current_time < 0.0 or current_time > max_end):
            self.logger.info(
                f"[PLAYHEAD] Out of range ({current_time:.3f}s > {max_end:.3f}s). Snapping to 0.0s"
            )
            current_time = 0.0
            try:
                self.timeline.playhead_pos = 0.0
            except Exception:
                pass
            try:
                self.playhead_updated.emit(0.0)
            except Exception:
                pass
        res_txt = self.inspector.combo_res.currentText()
        w, h = (1080, 1920) if "Portrait" in res_txt else (1920, 1080)
        if "2560" in res_txt:
            w, h = 2560, 1440
        elif "3840" in res_txt:
            w, h = 3840, 2160
        if proxy_enabled:
            w //= 2
            h //= 2
        preroll = 2.0
        start_win = max(0.0, current_time - preroll)
        if max_end > 0.0 and start_win >= max_end:
            start_win = max(0.0, max_end - 0.001)
        preview_dur = 60.0
        start_win = round(start_win, 4) 
        self.logger.info(
            f"[PLAYBACK] Rebuilding Graph at {current_time:.4f}s (Window: {start_win}s)..."
        )
        gen = FilterGraphGenerator(state, w, h, track_vols, track_mutes)
        try:
            inputs, f_str, _, _, main_input_used_for_video = gen.build(start_time=start_win, duration=preview_dur)
            self.player.play_filter_graph(f_str, inputs, main_input_used_for_video)
            seek_target = max(0.0, current_time - start_win)
            self.player.seek(round(seek_target, 4))
            self.is_dirty = False
            self.timer.start()
        except Exception as e:
            self.logger.error("[PLAYBACK] Failed to rebuild graph", exc_info=True)
            self.timer.stop()
            self.state_changed.emit(False)

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
