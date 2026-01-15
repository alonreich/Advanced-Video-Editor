import logging
import os
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from ffmpeg_generator import FilterGraphGenerator

class PlaybackManager(QObject):
    playhead_updated = pyqtSignal(float)
    state_changed = pyqtSignal(bool)

    def __init__(self, main_window, player_node, timeline, inspector):
        super().__init__()
        self.mw = main_window
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.player = player_node
        self.timeline = timeline
        self.inspector = inspector
        self.is_dirty = True
        self.start_offset = 0.0
        self.canvas_width = 1920
        self.canvas_height = 1080
        self.loop_enabled = False
        self.loop_in = 0.0
        self.loop_out = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._sync_playhead)
        self._seek_timer = QTimer(self)
        self._seek_timer.setSingleShot(True)
        self._seek_timer.setInterval(50)

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
            self._resume_background_tasks()
            return
        if not self.is_dirty and self.player.get_time() > 0:
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            self._throttle_background_tasks()
            return
        self._rebuild_and_play(proxy_enabled, track_vols, track_mutes)

    def _throttle_background_tasks(self):
        """Goal 20: Throttle background tasks during active playback."""
        if hasattr(self.mw, 'asset_loader'):
            self.mw.asset_loader.thread_pool.setMaxThreadCount(1)
            if hasattr(self.mw.asset_loader, 'proxy_worker'):
                try:
                    self.mw.asset_loader.proxy_worker.pause()
                except:
                    pass
    
    def _resume_background_tasks(self):
        """Resume background tasks after playback stops."""
        if hasattr(self.mw, 'asset_loader'):
            import os
            self.mw.asset_loader.thread_pool.setMaxThreadCount(os.cpu_count() or 4)
            if hasattr(self.mw.asset_loader, 'proxy_worker'):
                try:
                    self.mw.asset_loader.proxy_worker.resume()
                except:
                    pass

    def _rebuild_and_play(self, proxy_enabled, track_vols, track_mutes, start_time=None, play_now=True):
        """Rebuilds the FFmpeg filter graph and sends it to the player."""
        self.logger.debug("Rebuilding filter graph for playback...")
        current_time = start_time if start_time is not None else self.timeline.playhead_pos
        self.start_offset = current_time
        state = self.timeline.get_state()
        if not state:
            self.player.stop()
            self.state_changed.emit(False)
            self.logger.warning("No clips on timeline, stopping playback.")
            return
        if is_scrubbing := self.timeline.timeline_view.is_dragging_playhead:
            for clip in state:
                if clip.get('proxy_path') and os.path.exists(clip['proxy_path']):
                    clip['path'] = clip['proxy_path']
        gen = FilterGraphGenerator(
            state,
            width=self.canvas_width,
            height=self.canvas_height,
            volumes=track_vols,
            mutes=track_mutes,
            audio_analysis=self.mw.audio_analysis_results
        )
        inputs, complex_filter, v_pad, a_pad, main_input_used = gen.build(
            start_time=current_time,
            duration=self.timeline.get_content_end(),
            is_export=False
        )
        if is_scrubbing:
            complex_filter = complex_filter.replace("null[vo]", "select=not(mod(n\\,5)),setpts=N/FRAME_RATE/TB[vo]")
        try:
            self.player.play_filter_graph(complex_filter, inputs, main_input_used)
            if play_now:
                self.player.play()
                self.timer.start()
                self.state_changed.emit(True)
                self._throttle_background_tasks()
            else:
                self.player.pause()
                self.timer.stop()
                self.state_changed.emit(False)
            self.is_dirty = False
            self.logger.info(f"Playback started with filter graph at {current_time:.2f}s.")
        except Exception as e:
            self.logger.error(f"[FFMPEG-PLAYBACK] Failed to load complex filter: {e}", exc_info=True)
            self.player.stop()
            self.state_changed.emit(False)

    def _sync_playhead(self):
        """Main loop: Syncs UI playhead from player time."""
        if self.timeline.timeline_view.is_dragging_playhead or getattr(self, '_seeking', False):
            return
        if not self.player.is_playing():
            return
        try:
            current_player_time = self.player.get_time()
            if current_player_time is None:
                return
        except Exception as e:
            self.logger.error(f"[MPV] Playback core stopped: {e}")
            self.player.stop()
            self.timer.stop()
            self.state_changed.emit(False)
            return
        abs_time = current_player_time + self.start_offset
        if self.loop_enabled and abs_time >= self.loop_out - 0.016:
            self.logger.debug(f"[LOOP] Boundary hit at {abs_time:.2f}s. Snapping back to {self.loop_in:.2f}s.")
            self.player.pause()
            seek_time = self.loop_in + 0.001
            self.seek_and_sync(seek_time)

            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, lambda: self.player.play() if not self.player.is_playing() else None)
            return
        self.playhead_updated.emit(abs_time)
        max_end = self.timeline.get_content_end()
        if max_end > 0 and abs_time >= max_end - 0.016:
            self.player.pause()
            self.timer.stop()
            self.state_changed.emit(False)
            self._resume_background_tasks()

    def seek_and_sync(self, time_sec):
        """Standardizes fast seeking by bypassing the blocking sync checks."""
        if getattr(self, '_seeking', False): return
        self._seeking = True
        should_keep_playing = self.player.is_playing()
        max_dur = self.timeline.get_content_end()
        target_time = max(0.0, min(time_sec, max_dur))
        if self.player.is_playing():
            self.player.pause()
            self.timer.stop()
        if target_time < self.start_offset or target_time > (self.start_offset + 5.0):
            self._rebuild_and_play(
                False, 
                self.mw.track_volumes, 
                self.mw.track_mutes, 
                start_time=target_time,
                play_now=should_keep_playing
            )
        else:
            self.player.seek(target_time - self.start_offset)
            if should_keep_playing:
                self.player.play()
                self.timer.start()
        self.playhead_updated.emit(target_time)
        overlay = getattr(self.mw.preview, 'overlay', None)
        if overlay:
            overlay.is_loading = False
            overlay.update()
        self._seeking = False

    def set_loop(self, start, end, enabled=True):
        """Sets the active loop region boundaries."""
        self.loop_in = max(0.0, start)
        self.loop_out = max(self.loop_in + 0.1, end)
        self.loop_enabled = enabled
        self.logger.info(f"[LOOP] Configured: {self.loop_in:.2f}s -> {self.loop_out:.2f}s")