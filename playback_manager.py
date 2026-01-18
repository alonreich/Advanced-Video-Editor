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
        self._seek_timer.setInterval(16)
        self._seek_timer.timeout.connect(self._execute_seek)
        self._seeking = False
        self._pending_seek_time = 0.0

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
        current_time = self.player.get_time() + self.start_offset
        max_end = self.timeline.get_content_end()
        at_end = max_end > 0 and current_time >= max_end - 0.1
        if at_end:
            self.seek_and_sync(0)

            from PyQt5.QtCore import QTimer
            QTimer.singleShot(50, lambda: self._play_from_start(proxy_enabled, track_vols, track_mutes))
        elif not self.is_dirty and self.player.get_time() > 0:
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            self._throttle_background_tasks()
        else:
            self._rebuild_and_play(proxy_enabled, track_vols, track_mutes)
    
    def _play_from_start(self, proxy_enabled=False, track_vols=None, track_mutes=None):
        """Helper to play from start after seeking to 0."""
        if not self.is_dirty:
            self.player.play()
            self.timer.start()
            self.state_changed.emit(True)
            self._throttle_background_tasks()
        else:
            self._rebuild_and_play(proxy_enabled, track_vols, track_mutes, start_time=0.0)

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
        timeline_end = self.timeline.get_content_end()
        playback_duration = max(0.1, timeline_end - current_time) if timeline_end > current_time else 10.0
        inputs, complex_filter, v_pad, a_pad, main_input_used = gen.build(
            start_time=current_time,
            duration=playback_duration,
            is_export=False
        )
        if is_scrubbing:
            complex_filter = complex_filter.replace("null[vo]", "select=not(mod(n\\,5)),setpts=N/FRAME_RATE/TB[vo]")
        self.logger.info(f"[PLAYBACK] lavfi supported? {self.player.lavfi_supported()}")
        self.logger.info(f"[PLAYBACK] complex_filter length: {len(complex_filter)}")
        if not self.player.lavfi_supported():
            self.logger.warning("[PLAYBACK] lavfi not supported, falling back to direct file playback.")
            # Find the topmost visible video clip at current_time
            visible_clips = []
            for clip in state:
                clip_start = clip.get('start', 0)
                clip_duration = clip.get('dur', clip.get('duration', 0))
                clip_end = clip_start + clip_duration
                if clip_start <= current_time < clip_end and clip.get('width', 0) > 0:  # Video clip
                    visible_clips.append(clip)
            # Sort by track descending (higher track = topmost)
            visible_clips.sort(key=lambda x: -x['track'])
            
            clip_to_play = None
            time_until_start = 0
            
            if visible_clips:
                clip_to_play = visible_clips[0]  # Topmost visible video clip
                self.logger.info(f"[PLAYBACK-FALLBACK] Selected topmost video clip track={clip_to_play.get('track')}, path={clip_to_play.get('path')}")
                time_until_start = 0
            else:
                # Fallback to original logic if no visible video at current time
                upcoming_clips = []
                for clip in state:
                    clip_start = clip.get('start', 0)
                    clip_duration = clip.get('dur', clip.get('duration', 0))
                    clip_end = clip_start + clip_duration
                    if clip_start <= current_time < clip_end:
                        upcoming_clips.append((0, clip))
                    elif clip_start > current_time:
                        time_until_start = clip_start - current_time
                        upcoming_clips.append((time_until_start, clip))
                if upcoming_clips:
                    upcoming_clips.sort(key=lambda x: (x[0] != 0, x[0]))
                    time_until_start, clip_to_play = upcoming_clips[0]
            
            if not clip_to_play:
                self.logger.info(f"No clips on timeline at or after {current_time:.2f}s. Stopping playback.")
                self.player.stop()
                self.timer.stop()
                self.state_changed.emit(False)
                self.is_dirty = False
                return
                
            clip_path = clip_to_play.get('path', '')
            if not clip_path or not os.path.exists(clip_path):
                self.logger.warning(f"Clip path not found or invalid: {clip_path}")
                self.player.stop()
                self.timer.stop()
                self.state_changed.emit(False)
                self.is_dirty = False
                return
                
            if time_until_start == 0:
                clip_start = clip_to_play.get('start', 0)
                clip_source_in = clip_to_play.get('source_in', 0)
                position_in_clip = clip_source_in + (current_time - clip_start)
                self.player.load(clip_path)
                
                import time
                time.sleep(0.1)
                seek_success = False
                for attempt in range(5):
                    try:
                        self.player.seek(position_in_clip)
                        time.sleep(0.05)
                        player_time = self.player.get_time()
                        if player_time is not None and abs(player_time - position_in_clip) < 0.5:
                            seek_success = True
                            self.logger.debug(f"Seek successful on attempt {attempt+1}: {player_time:.2f}s (clip time), timeline time: {current_time:.2f}s")
                            break
                        else:
                            self.logger.debug(f"Seek attempt {attempt+1} failed: got {player_time}, expected {position_in_clip}")
                    except Exception as e:
                        self.logger.debug(f"Seek attempt {attempt+1} exception: {e}")
                    time.sleep(0.05)
                if not seek_success:
                    self.logger.warning(f"Failed to seek to {position_in_clip}s (clip time) after 5 attempts")
                fade_in = clip_to_play.get('fade_in', 0.0)
                fade_out = clip_to_play.get('fade_out', 0.0)
                if fade_in > 0 or fade_out > 0:
                    try:
                        clip_duration = clip_to_play.get('dur', clip_to_play.get('duration', 0))
                        time_in_clip = current_time - clip_start
                        remaining_in_clip = clip_duration - time_in_clip
                        fade_factor = 1.0
                        if fade_in > 0 and time_in_clip < fade_in:
                            fade_factor = time_in_clip / fade_in
                        elif fade_out > 0 and remaining_in_clip < fade_out:
                            fade_factor = remaining_in_clip / fade_out
                        # Apply volume adjustment
                        track_idx = clip_to_play.get('track', 0)
                        base_volume = 100.0
                        if track_vols and isinstance(track_vols, dict) and track_idx in track_vols:
                            base_volume = track_vols[track_idx]
                        elif track_vols and isinstance(track_vols, list) and track_idx < len(track_vols):
                            base_volume = track_vols[track_idx]
                        target_volume = max(0.0, min(100.0, base_volume * fade_factor))
                        self.player.set_volume(target_volume)
                        self.logger.debug(f"Applied fade volume: {target_volume:.1f} (factor {fade_factor:.2f})")
                    except Exception as e:
                        self.logger.debug(f"Could not apply fade effects: {e}")
                try:
                    if hasattr(self.player, 'apply_crop'):
                        from model import ClipModel
                        clip_model = ClipModel.from_dict(clip_to_play)
                        self.player.apply_crop(clip_model)
                except Exception as e:
                    self.logger.debug(f"Could not apply clip transformations: {e}")
                if play_now:
                    self.player.play()
                    time.sleep(0.05)
                    if self.player.is_playing():
                        self.timer.start()
                        self.state_changed.emit(True)
                        self._throttle_background_tasks()
                    else:
                        self.logger.error("Play command failed - player not playing")
                        self.player.play()
                        time.sleep(0.05)
                        if self.player.is_playing():
                            self.timer.start()
                            self.state_changed.emit(True)
                            self._throttle_background_tasks()
                else:
                    self.player.pause()
                    self.timer.stop()
                    self.state_changed.emit(False)
                self.is_dirty = False
                self.logger.info(f"Direct playback of clip started at timeline {current_time:.2f}s (clip time: {position_in_clip:.2f}s).")
                return
            else:
                clip_start = clip_to_play.get('start', 0)
                self.logger.info(f"No clip visible at {current_time:.2f}s. Next clip starts in {time_until_start:.2f}s.")
                clip_source_in = clip_to_play.get('source_in', 0)
                self.player.load(clip_path)
                
                import time
                time.sleep(0.1)
                self.player.seek(clip_source_in)
                if play_now:
                    self.player.pause()
                    self.timer.stop()
                    self.state_changed.emit(False)
                    self.logger.info(f"Clip loaded but paused. Starts at timeline {clip_start:.2f}s (in {time_until_start:.2f}s).")
                else:
                    self.player.pause()
                    self.timer.stop()
                    self.state_changed.emit(False)
                self.is_dirty = False
                return
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
        end_margin = 0.016
        if max_end > 0 and abs_time >= max_end - end_margin:
            if self.player.is_playing():
                self.player.pause()
                self.timer.stop()
                self.state_changed.emit(False)
                self._resume_background_tasks()
                # Seek to beginning (time 0) and stop
                self.seek_and_sync(0.0)
                self.logger.debug(f"[PLAYBACK] Reached end of timeline at {abs_time:.3f}s, stopped at beginning")

    def seek_and_sync(self, time_sec):
        """Standardizes fast seeking by bypassing the blocking sync checks."""
        max_dur = self.timeline.get_content_end()
        if max_dur > 0:
            clamped_time = max(0.0, min(time_sec, max_dur - 0.001))
        else:
            clamped_time = max(0.0, time_sec)
        self.logger.debug(f"[SEEK] seek_and_sync called with {time_sec:.3f}s, clamped to {clamped_time:.3f}s")
        self.playhead_updated.emit(clamped_time)
        if self._seek_timer.isActive():
            self._seek_timer.stop()
        self._pending_seek_time = time_sec
        self._seek_timer.start()
        
    def _execute_seek(self):
        """Executes the pending seek after debounce delay."""
        if getattr(self, '_seeking', False): 
            return
        self._seeking = True
        try:
            time_sec = getattr(self, '_pending_seek_time', 0.0)
            should_keep_playing = self.player.is_playing()
            max_dur = self.timeline.get_content_end()
            if max_dur > 0:
                target_time = max(0.0, min(time_sec, max_dur - 0.001))
            else:
                target_time = max(0.0, time_sec)
            self.logger.debug(f"[SEEK] _execute_seek: target_time={target_time:.3f}, start_offset={self.start_offset:.3f}, lavfi_supported={self.player.lavfi_supported()}")
            needs_rebuild = False
            if not self.player.lavfi_supported():
                if target_time < self.start_offset or target_time > (self.start_offset + 300.0):
                    needs_rebuild = True
                    self.logger.debug(f"[SEEK] lavfi unsupported, needs_rebuild because target_time out of range")
                else:
                    needs_rebuild = False
            elif target_time < self.start_offset or target_time > (self.start_offset + 300.0):
                needs_rebuild = True
                self.logger.debug(f"[SEEK] lavfi supported, needs_rebuild because target_time out of range")
            if needs_rebuild:
                self.logger.debug(f"[SEEK] Rebuilding for target_time {target_time:.3f}")
                if self.player.is_playing():
                    self.player.pause()
                    self.timer.stop()
                self._rebuild_and_play(
                    False, 
                    self.mw.track_volumes, 
                    self.mw.track_mutes, 
                    start_time=target_time,
                    play_now=should_keep_playing
                )
            else:
                self.logger.debug(f"[SEEK] Seeking within existing clip: offset={target_time - self.start_offset:.3f}")
                was_playing = self.player.is_playing()
                self.player.seek(target_time - self.start_offset)
                # Verify seek succeeded
                import time
                time.sleep(0.05)
                player_time = self.player.get_time()
                if player_time is not None:
                    expected = target_time - self.start_offset
                    if abs(player_time - expected) > 0.5:
                        self.logger.warning(f"[SEEK] Seek verification failed: got {player_time:.3f}, expected {expected:.3f}. Triggering rebuild.")
                        # Seek failed, rebuild
                        if self.player.is_playing():
                            self.player.pause()
                            self.timer.stop()
                        self._rebuild_and_play(
                            False,
                            self.mw.track_volumes,
                            self.mw.track_mutes,
                            start_time=target_time,
                            play_now=was_playing
                        )
                        self.playhead_updated.emit(target_time)
                        overlay = getattr(self.mw.preview, 'overlay', None)
                        if overlay:
                            overlay.is_loading = False
                            overlay.update()
                        return
                if was_playing and not self.timer.isActive():
                    self.timer.start()
            self.playhead_updated.emit(target_time)
            overlay = getattr(self.mw.preview, 'overlay', None)
            if overlay:
                overlay.is_loading = False
                overlay.update()
        except Exception as e:
            self.logger.error(f"[SEEK] Error during seek execution: {e}")
        finally:
            self._seeking = False

    def set_loop(self, start, end, enabled=True):
        """Sets the active loop region boundaries."""
        self.loop_in = max(0.0, start)
        self.loop_out = max(self.loop_in + 0.1, end)
        self.loop_enabled = enabled
        self.logger.info(f"[LOOP] Configured: {self.loop_in:.2f}s -> {self.loop_out:.2f}s")
