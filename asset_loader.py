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
                if occupied_tracks:
                    track = max(occupied_tracks) + 1
            else:
                track = 0
                while track in occupied_tracks:
                    track += 1
        is_internal = False
        if self.mw.pm.assets_dir and os.path.abspath(path).startswith(os.path.abspath(self.mw.pm.assets_dir)):
            is_internal = True
        if is_internal:
            local_path = path
        else:
            local_path = self.mw.pm.import_asset(path)
        if local_path in self._pending_probes:
            self.mw.logger.warning(f"Ignored duplicate drop event for: {local_path}")
            return
        self._pending_probes.add(local_path)
        worker = ProbeWorker(local_path, track_id=track, insert_time=time)
        worker.signals.result.connect(self.on_probe_done)
        self.thread_pool.start(worker)

    def on_probe_done(self, info):
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
            'track': track,
            'path': info['path'],
            'width': info.get('width', 0),
            'has_audio': info.get('has_audio', True),
            'media_type': 'video' if info.get('has_video') else 'audio',
            'linked_uid': a_uid
        }
        self.mw.timeline.add_clip(video_data)
        self.regenerate_assets(video_data)

    def regenerate_assets(self, data):
        self._regen_queue[data['uid']] = data
        self._regen_timer.start()

    def _process_regen_queue(self):
        while self._regen_queue:
            uid, data = self._regen_queue.popitem()
            if data.get('has_audio'):
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
                i.update_cache()
                i.update()

    def cleanup(self):
        self.thumb_worker.stop()
        self.wave_worker.stop()
        self.proxy_worker.stop()
        self.thread_pool.waitForDone(100)

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