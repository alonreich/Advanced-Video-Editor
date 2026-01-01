import os
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QFileDialog, QDockWidget, QAction, QMessageBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QListView, QActionGroup
from PyQt5.QtCore import QTimer, Qt, QUrl, QMimeData
from PyQt5.QtGui import QPixmap, QDrag

from project import ProjectManager
from player import MPVPlayer
from prober import ProbeWorker, WaveformWorker
from exporter import FFmpegBuilder, RenderWorker
from timeline_container import TimelineContainer
from preview import PreviewWidget
from inspector import InspectorWidget
from history import UndoStack
from clip_item import ClipItem
from worker import ThumbnailWorker
from timeline_view import Mode

class MediaPoolWidget(QListWidget):
    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item:
            mime_data = QMimeData()
            path = item.data(Qt.UserRole)
            mime_data.setUrls([QUrl.fromLocalFile(path)])
            
            drag = QDrag(self)
            drag.setMimeData(mime_data)
            drag.exec_(supportedActions)

class MainWindow(QMainWindow):
    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self.pm = ProjectManager(base_dir)
        self.history = UndoStack()
        self.waveform_workers = []
        self.thumbnail_workers = []
        last_data = self.pm.load_latest()
        if not last_data:
            self.pm.create_project()
        self.setup_ui()
        self.setup_player()
        if last_data:
            self.timeline.load_state(last_data.get('timeline', []))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync_playhead)
        self.timer.start(50)

    def setup_ui(self):
        self.setWindowTitle("ProEditor v2 - Semi Pro")
        self.setStyleSheet("QMainWindow::separator { background-color: #666; width: 2px; height: 2px; }"
                           "QToolTip { font: 12pt Arial; }")
        self.resize(1600, 900)
        
        # Central Widget
        self.player_node = MPVPlayer(self)
        self.preview = PreviewWidget(self.player_node)
        self.preview.param_changed.connect(self.on_param_changed)
        self.setCentralWidget(self.preview)

        # Docks
        self.dock_timeline = QDockWidget("Timeline", self)
        self.dock_timeline.setObjectName("TimelineDock")
        self.timeline = TimelineContainer()
        self.dock_timeline.setWidget(self.timeline)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)

        self.dock_inspector = QDockWidget("Inspector", self)
        self.dock_inspector.setObjectName("InspectorDock")
        self.inspector = InspectorWidget()
        self.dock_inspector.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_inspector)

        self.dock_media_pool = QDockWidget("Media Pool", self)
        self.dock_media_pool.setObjectName("MediaPoolDock")
        self.media_pool = MediaPoolWidget()
        self.dock_media_pool.setWidget(self.media_pool)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_media_pool)
        
        # Connections
        self.timeline.time_updated.connect(self.user_seek)
        self.timeline.clip_selected.connect(self.on_clip_selected)
        self.timeline.file_dropped.connect(self.handle_timeline_drop)
        self.timeline.clip_split_requested.connect(self.split_clip_at)
        self.inspector.param_changed.connect(self.on_param_changed)

        # Toolbar
        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.setStyleSheet("background-color: #2A2A2A; border-bottom: 1px solid #666;")
        
        act_imp = QAction("Import Media", self)
        act_imp.setToolTip("Import media files into the Media Pool.")
        act_imp.triggered.connect(self.import_file)
        tb.addAction(act_imp)
        
        act_exp = QAction("Export", self)
        act_exp.setToolTip("Export the timeline to a video file.")
        act_exp.triggered.connect(self.start_export)
        tb.addAction(act_exp)

        act_reset = QAction("Reset Project", self)
        act_reset.setToolTip("Start a new empty project.")
        act_reset.triggered.connect(self.reset_project)
        tb.addAction(act_reset)

        act_reset_layout = QAction("Reset Layout", self)
        act_reset_layout.setToolTip("Reset the layout of all panels to the default.")
        act_reset_layout.triggered.connect(self.reset_layout)
        tb.addAction(act_reset_layout)

        tb.addSeparator()
        
        act_undo = QAction("Undo", self)
        act_undo.setShortcut("Ctrl+Z")
        act_undo.setToolTip("Undo the last action (Ctrl+Z).")
        act_undo.triggered.connect(self.undo)
        tb.addAction(act_undo)
        
        act_split = QAction("Split Clip", self)
        act_split.setShortcut("Ctrl+K")
        act_split.setToolTip("Split the selected clip at the playhead (Ctrl+K).")
        act_split.triggered.connect(self.split_current_clip)
        tb.addAction(act_split)
        
        act_del = QAction("Delete", self)
        act_del.setShortcut("Del")
        act_del.setToolTip("Delete the selected clip (Del).")
        act_del.triggered.connect(self.delete_current_clip)
        tb.addAction(act_del)
        
        tb.addSeparator()
        
        ag = QActionGroup(self)
        ag.setExclusive(True)
        
        act_pointer = QAction("Pointer", self)
        act_pointer.setCheckable(True)
        act_pointer.setChecked(True)
        act_pointer.setToolTip("Switch to Pointer tool for selecting and moving clips.")
        act_pointer.triggered.connect(lambda: self.timeline.set_mode(Mode.POINTER))
        ag.addAction(act_pointer)
        tb.addAction(act_pointer)
        
        act_razor = QAction("Razor", self)
        act_razor.setCheckable(True)
        act_razor.setToolTip("Switch to Razor tool for splitting clips.")
        act_razor.triggered.connect(lambda: self.timeline.set_mode(Mode.RAZOR))
        ag.addAction(act_razor)
        tb.addAction(act_razor)
        
        act_crop = QAction("Crop", self)
        act_crop.setShortcut("C")
        act_crop.setToolTip("Toggle Crop mode (C).")
        act_crop.triggered.connect(lambda: self.preview.overlay.toggle_crop_mode())
        tb.addAction(act_crop)

        self.combo_res = QComboBox()
        self.combo_res.setToolTip("Select the output video resolution and aspect ratio.")
        self.combo_res.addItems([
            "Landscape 1920x1080 (HD)", "Landscape 2560x1440 (QHD)", "Landscape 3840x2160 (4K)",
            "Portrait 1080x1920 (Mobile HD)", "Portrait 1440x2560 (Mobile QHD)"
        ])
        self.combo_res.currentTextChanged.connect(self.update_res_mode)
        tb.addWidget(QLabel("  Output: "))
        tb.addWidget(self.combo_res)
        tb.addSeparator()
        
        act_play = QAction("Play/Pause", self)
        act_play.setShortcut("Space")
        act_play.setToolTip("Play or pause the timeline preview (Space).")
        act_play.triggered.connect(self.toggle_play)
        tb.addAction(act_play)

        self.initial_layout_state = self.saveState()

    def reset_project(self):
        reply = QMessageBox.question(self, 'Reset Project', 
                                     "Are you sure you want to start a new project? All unsaved changes will be lost.",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.timeline.load_state([])
            self.media_pool.clear()
            self.pm.create_project()
            self.player_node.stop()

    def reset_layout(self):
        self.restoreState(self.initial_layout_state)

    def setup_player(self):
        pass
        
    def save_state_for_undo(self):
        state = self.timeline.get_state()
        self.history.push(state)
        self.pm.save_state(state)

    def undo(self):
        current = self.timeline.get_state()
        prev = self.history.undo(current)
        if prev is not None:
            self.timeline.load_state(prev)

    def split_clip_at(self, item, time):
        if not (item.start < time < item.start + item.duration):
            return 
        self.save_state_for_undo()
        
        split_point_relative = time - item.start
        
        right_dur = item.duration - split_point_relative
        right_start = time
        
        left_dur = split_point_relative
        item.duration = left_dur
        item.model.duration = left_dur
        item.setRect(0, 0, left_dur * item.scale, 50)
        
        new_data = {
            'uid': str(os.urandom(4).hex()),
            'name': item.name,
            'path': item.model.path,
            'start': right_start,
            'dur': right_dur,
            'track': item.track,
            'width': item.model.width,
            'height': item.model.height,
            'bitrate': item.model.bitrate
        }
        self.timeline.add_clip(new_data)
        
        if item.waveform_pixmap:
            self.start_waveform_worker(new_data)
        if item.thumbnail_start:
            self.start_thumbnail_worker(new_data)

    def split_current_clip(self):
        item = self.timeline.get_selected_item()
        if not item: return
        ph = self.timeline.playhead_pos
        self.split_clip_at(item, ph)

    def delete_current_clip(self):
        selected_item = self.timeline.get_selected_item()
        if selected_item:
            self.save_state_for_undo()

            deleted_clip_track = selected_item.track
            deleted_clip_start = selected_item.start
            deleted_clip_duration = selected_item.duration

            items_to_shift = []
            for item in self.timeline.scene.items():
                if isinstance(item, ClipItem) and item != selected_item and item.track == deleted_clip_track and item.start > deleted_clip_start:
                    items_to_shift.append(item)
            
            items_to_shift.sort(key=lambda x: x.start)

            for item in items_to_shift:
                new_start = item.start - deleted_clip_duration
                item.start = new_start
                item.model.start = new_start
                item.setX(new_start * item.scale)

            self.timeline.remove_selected_clips()
            self.inspector.set_clip(None)

    def on_param_changed(self, param, value):
        item = self.timeline.get_selected_item()
        if not item: return
        if param == "speed":
            item.set_speed(value)
            if self.player_node.is_playing():
                self.player_node.set_speed(value)
        elif param == "volume":
            item.set_volume(value)
            if self.player_node.is_playing():
                self.player_node.set_volume(value)
        elif "crop" in param:
            setattr(item.model, param, value)
            self.preview.overlay.update()
            if self.player_node.is_playing():
                self.player_node.apply_crop(item.model)
        elif "pos" in param:
            setattr(item.model, param, value)
            self.preview.overlay.update()
        
    def import_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Import")
        if not paths: return
        for path in paths:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.media_pool.addItem(item)

    def handle_timeline_drop(self, path, track_idx, start_time):
        self.process_import(path, track=track_idx, start_time=start_time)

    def process_import(self, path, track, start_time):
        self.save_state_for_undo()
        local_path = self.pm.import_asset(path)
        worker = ProbeWorker(local_path)
        worker.drop_target = {'track': track, 'time': start_time}
        worker.result.connect(self.on_probe_done)
        self._current_worker = worker 
        worker.start()

    def on_probe_done(self, info):
        target = getattr(self.sender(), 'drop_target', {'track': 0, 'time': 0.0})
        clip_data = {
            'uid': str(os.urandom(4).hex()),
            'name': os.path.basename(info['path']),
            'path': info['path'],
            'start': target['time'],
            'dur': info['duration'],
            'track': target['track'],
            'width': info.get('width', 1920),
            'height': info.get('height', 1080),
            'bitrate': info.get('bitrate', 0)
        }
        self.timeline.add_clip(clip_data)

        # Check if we need to add a new track
        clips = self.timeline.get_state()
        if clips:
            max_track = max(c['track'] for c in clips)
            num_tracks = len(self.timeline.track_headers.headers)
            if max_track >= num_tracks - 2 and num_tracks < 20:
                self.timeline.add_track()
        
        if info.get('has_audio'):
            self.start_waveform_worker(clip_data)
        
        if info.get('has_video'):
            self.start_thumbnail_worker(clip_data)

        if len(self.timeline.get_state()) == 1:
            self.player_node.load(info['path'])

    def start_waveform_worker(self, clip_data):
        worker = WaveformWorker(clip_data['path'], clip_data['uid'], self.base_dir)
        worker.finished.connect(self.on_waveform_done)
        self.waveform_workers.append(worker)
        worker.start()
        
    def start_thumbnail_worker(self, clip_data):
        thumb_worker = ThumbnailWorker(clip_data['path'], clip_data['uid'], self.base_dir)
        thumb_worker.finished.connect(self.on_thumbnail_done)
        self.thumbnail_workers.append(thumb_worker)
        thumb_worker.start()

    def on_waveform_done(self, uid, path):
        for item in self.timeline.scene.items():
            if isinstance(item, ClipItem) and item.uid == uid:
                pixmap = QPixmap(path)
                item.waveform_pixmap = pixmap
                item.update()
                break

    def on_thumbnail_done(self, uid, thumb_start_path, thumb_end_path):
        for item in self.timeline.scene.items():
            if isinstance(item, ClipItem) and item.uid == uid:
                if thumb_start_path:
                    item.thumbnail_start = QPixmap(thumb_start_path)
                if thumb_end_path:
                    item.thumbnail_end = QPixmap(thumb_end_path)
                item.update()
                break

    def on_clip_selected(self, clip_item):
        if clip_item:
            self.inspector.set_clip(clip_item.model)
            self.preview.overlay.set_selected_clip(clip_item.model)
        else:
            self.inspector.set_clip(None)
            self.preview.overlay.set_selected_clip(None)

    def user_seek(self, sec):
        self.player_node.seek(sec)

    def sync_playhead(self):
        if self.player_node.is_playing():
            t = self.player_node.get_time()
            self.timeline.set_time(t)

    def toggle_play(self):
        if self.player_node.is_playing():
            self.player_node.pause()
        else:
            self.player_node.play()

    def update_res_mode(self, text):
        w, h = 1920, 1080
        if "1080x1920" in text: w, h = 1080, 1920
        self.preview.set_mode(w, h, text)

    def start_export(self):
        state = self.timeline.get_state()
        if not state: return
        out, _ = QFileDialog.getSaveFileName(self, "Export", filter="MP4 (*.mp4)")
        if not out: return
        res_mode = self.combo_res.currentText()
        builder = FFmpegBuilder(state, out, res_mode)
        self.render_worker = RenderWorker(builder)
        self.render_worker.finished.connect(lambda: QMessageBox.information(self, "Done", "Export Successful"))
        self.render_worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.render_worker.start()