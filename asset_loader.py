import os
from PyQt5.QtWidgets import QFileDialog, QListWidgetItem
from PyQt5.QtCore import Qt, QObject
from PyQt5.QtGui import QPixmap
from prober import ProbeWorker, WaveformWorker
from worker import ThumbnailWorker
from clip_item import ClipItem

class AssetLoader(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.mw = main_window
        self.base_dir = main_window.base_dir
        self.thumb_worker = ThumbnailWorker(self.base_dir)
        self.thumb_worker.thumbnail_generated.connect(self.on_thumb_done)
        self.thumb_worker.start()
        self.wave_workers = []

    def import_dialog(self):
        last = self.mw.config.get("last_import", self.base_dir)
        paths, _ = QFileDialog.getOpenFileNames(self.mw, "Import", last)
        if paths:
            self.mw.config.set("last_import", os.path.dirname(paths[0]))
            for p in paths:
                item = QListWidgetItem(os.path.basename(p))
                item.setData(Qt.UserRole, p)
                self.mw.media_pool.addItem(item)

    def handle_drop(self, path, track, time):
        local_path = self.mw.pm.import_asset(path)
        worker = ProbeWorker(local_path)
        worker.target = (track, time)
        worker.result.connect(self.on_probe_done)
        worker.start()
        self.mw._keep_worker = worker

    def on_probe_done(self, info):
        track, time = getattr(self.sender(), 'target', (0, 0.0))
        data = {
            'uid': os.urandom(4).hex(),
            'name': os.path.basename(info['path']),
            'path': info['path'],
            'start': time,
            'dur': info['duration'],
            'track': track,
            'width': info.get('width', 0),
            'has_audio': info.get('has_audio', True),
            'media_type': 'audio' if not info.get('has_video') else 'video'
        }
        self.mw.timeline.add_clip(data)
        self.regenerate_assets(data)

    def regenerate_assets(self, data):
        if data.get('has_audio'):
            w = WaveformWorker(data['path'], data['uid'], self.base_dir)
            w.finished.connect(self.on_wave_done)
            self.wave_workers.append(w)
            w.start()
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
                if start_p: i.thumbnail_start = QPixmap(start_p)
                if end_p: i.thumbnail_end = QPixmap(end_p)
                i.update_cache()
                i.update()

    def cleanup(self):
        self.thumb_worker.stop()
