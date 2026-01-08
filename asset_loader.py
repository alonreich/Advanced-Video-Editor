import os
from PyQt5.QtWidgets import QFileDialog, QListWidgetItem
from PyQt5.QtCore import Qt, QObject, QThreadPool
from PyQt5.QtGui import QPixmap
from prober import ProbeWorker, WaveformWorker
from worker import ThumbnailWorker
from clip_item import ClipItem

class AssetLoader(QObject):

    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self._shutting_down = False
        self.base_dir = main_window.base_dir
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(os.cpu_count() or 4)
        self.thumb_worker = ThumbnailWorker(self.base_dir)
        self.thumb_worker.thumbnail_generated.connect(self.on_thumb_done)
        self.thumb_worker.start()
        self.wave_worker = WaveformWorker(self.base_dir)
        self.wave_worker.finished.connect(self.on_wave_done)
        self.wave_worker.start()
        from worker import ProxyWorker
        self.proxy_worker = ProxyWorker(self.base_dir)
        self.proxy_worker.proxy_finished.connect(self.on_proxy_done)
        self.proxy_worker.start()
        from PyQt5.QtCore import QTimer
        self._regen_timer = QTimer()
        self._regen_timer.setSingleShot(True)
        self._regen_timer.setInterval(200)
        self._regen_timer.timeout.connect(self._process_regen_queue)
        self._regen_queue = {}
        self._pending_probes = set()

    def import_dialog(self, music_only=False):
        last = self.mw.config.get("last_import", self.base_dir)
        if music_only:
            paths, _ = QFileDialog.getOpenFileNames(self.mw, "Import Music", last, "Audio Files (*.mp3 *.wav *.aac *.flac)")
        else:
            paths, _ = QFileDialog.getOpenFileNames(self.mw, "Import", last)
        if paths:
            self.mw.config.set("last_import", os.path.dirname(paths[0]))
            next_track = 0
            if self.mw.timeline.timeline_view.scene:
                for item in self.mw.timeline.timeline_view.scene.items():
                    if isinstance(item, ClipItem):
                        next_track = max(next_track, item.track + 1)
            next_track = max(1, next_track)
            for i, p in enumerate(paths):
                local_path = self.mw.pm.import_asset(p)
                item = QListWidgetItem(os.path.basename(local_path))
                item.setData(Qt.UserRole, local_path)
                self.mw.media_pool.addItem(item)
                if music_only:
                    self.handle_drop(local_path, next_track + i, 0)
        if False:
                    self.handle_drop(local_path, next_track + i, 0)

    def handle_drop(self, path, track, time):
        is_audio = any(path.lower().endswith(x) for x in ['.mp3', '.wav', '.aac', '.flac', '.m4a'])
        if track == -1:
            occupied_tracks = set()
            if self.mw.timeline.timeline_view.scene:
                for item in self.mw.timeline.timeline_view.scene.items():
                    if hasattr(item, 'track'):
                        occupied_tracks.add(item.track)
            if is_audio:
                track = 1
                while track in occupied_tracks and track < 49:
                    track += 1
            else:
                track = 0
                while track in occupied_tracks and track < 49:
                    track += 1
        is_internal = False
        if self.mw.pm.assets_dir and os.path.abspath(path).startswith(os.path.abspath(self.mw.pm.assets_dir)):
            is_internal = True
        if is_internal:
            local_path = path
        else:
            local_path = self.mw.pm.import_asset(path)
        if local_path in self._pending_probes:
            self.mw.logger.warning(f"[LOADER] Blocking duplicate import for: {local_path}")
            return
        in_pool = False
        for i in range(self.mw.media_pool.count()):
            if self.mw.media_pool.item(i).data(Qt.UserRole) == local_path:
                in_pool = True
                break
        if not in_pool:
            item = QListWidgetItem(os.path.basename(local_path))
            item.setData(Qt.UserRole, local_path)
            self.mw.media_pool.addItem(item)
        self._pending_probes.add(local_path)
        worker = ProbeWorker(local_path, track_id=track, insert_time=time)
        worker.signals.result.connect(self.on_probe_done)
        self.thread_pool.start(worker)

    def on_probe_done(self, info):
        if self._shutting_down: 
            return
        track = info.get('track_id', 0)
        time = info.get('insert_time', 0.0)
        if 'path' in info and info['path'] in self._pending_probes:
            self._pending_probes.discard(info['path'])
        if 'error' in info:
            self.mw.logger.error(f"Failed to probe file: {info.get('error')}")
            return
        self.mw.logger.info(f"on_probe_done: Adding clip to track {track}")
        v_uid = os.urandom(4).hex()
        a_uid = os.urandom(4).hex() if info.get('has_audio') and info.get('has_video') else None
        video_data = {
            'uid': v_uid,
            'name': os.path.basename(info['path']),
            'start': time,
            'dur': info['duration'],
            'duration': info['duration'],
            'track': track,
            'path': info['path'],
            'width': info.get('width', 0),
            'has_audio': info.get('has_audio', True),
            'media_type': 'video' if info.get('has_video') else 'audio',
            'linked_uid': a_uid
        }
        new_item = self.mw.timeline.add_clip(video_data)
        self.mw.timeline.timeline_view.check_for_gaps(track, max(0, time - 0.05))
        self.mw.timeline.update_tracks()
        self.mw.timeline.fit_to_view()
        self.mw.save_state_for_undo()
        self.regenerate_assets(video_data)
        new_item.update_cache()

    def regenerate_assets(self, data):
        self._regen_queue[data['uid']] = data
        self._regen_timer.start()

    def _process_regen_queue(self):
        while self._regen_queue:
            uid, data = self._regen_queue.popitem()
            if data.get('media_type') == 'audio':
                self.wave_worker.add_task(data['path'], data['uid'])
            if data.get('media_type') == 'video':
                self.thumb_worker.add_task(data['path'], data['uid'], data['dur'])

    def on_wave_done(self, uid, path):
        for i in self.mw.timeline.scene.items():
            if isinstance(i, ClipItem) and i.uid == uid:
                i.waveform_pixmap = QPixmap(path)
                i.update_cache()
                i.update()
                
    def on_thumb_done(self, uid, start_p, end_p):
        for i in self.mw.timeline.scene.items():
            if isinstance(i, ClipItem) and i.uid == uid:
                if start_p and os.path.exists(start_p):
                    i.thumbnail_start = QPixmap(start_p)
                if end_p and os.path.exists(end_p):
                    i.thumbnail_end = QPixmap(end_p)
                i._last_render_time = 0 
                i.update_cache()
                i.update()
                i.thumbnail_end = QPixmap(end_p)
                i.update_cache()
                i.update()

    def cleanup(self):
        """Goal 19: Safe shutdown sequence to prevent race conditions."""
        self._shutting_down = True
        self.mw.logger.info("[SHUTDOWN] Initiating safe teardown...")
        self.thumb_worker.stop()
        self.wave_worker.stop()
        self.proxy_worker.stop()
        self.mw.logger.info("[SHUTDOWN] Waiting for ThreadPool tasks...")
        if not self.thread_pool.waitForDone(3000):
            self.mw.logger.warning("[SHUTDOWN] ThreadPool timed out. Active probes may crash.")
        workers = [self.thumb_worker, self.wave_worker, self.proxy_worker]
        for w in workers:
            if not w.wait(2000):
                self.mw.logger.warning(f"[SHUTDOWN] Worker {type(w).__name__} failed to exit gracefully.")

    def request_proxy(self, uid, path):
        self.mw.logger.info(f"[ASSET] Requesting proxy for {uid}")
        self.proxy_worker.add_task(path, uid)

    def on_proxy_done(self, uid, proxy_path):
        self.mw.logger.info(f"[ASSET] Proxy ready for {uid}: {proxy_path}")
        for item in self.mw.timeline.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == uid:
                item.model.proxy_path = proxy_path
                item.update_cache()
                item.update()