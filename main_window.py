import os
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QFileDialog, QDockWidget, QAction, QMessageBox, QComboBox, QHBoxLayout, QLabel
from PyQt5.QtCore import QTimer, Qt

from project import ProjectManager
from player import MPVPlayer
from prober import ProbeWorker
from exporter import FFmpegBuilder, RenderWorker
from timeline_view import TimelineView
from preview import PreviewWidget
from inspector import InspectorWidget
from history import UndoStack

class MainWindow(QMainWindow):
    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self.pm = ProjectManager(base_dir)
        self.history = UndoStack()
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
        self.resize(1600, 900)
        self.player_node = MPVPlayer(self)
        self.preview = PreviewWidget(self.player_node)
        self.setCentralWidget(self.preview)
        self.dock_timeline = QDockWidget("Timeline", self)
        self.timeline = TimelineView()
        self.timeline.time_updated.connect(self.user_seek)
        self.timeline.clip_selected.connect(self.on_clip_selected)
        self.timeline.file_dropped.connect(self.handle_timeline_drop)
        self.dock_timeline.setWidget(self.timeline)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)
        self.dock_inspector = QDockWidget("Inspector", self)
        self.inspector = InspectorWidget()
        self.inspector.param_changed.connect(self.on_param_changed)
        self.dock_inspector.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_inspector)
        tb = self.addToolBar("Main")
        act_imp = QAction("Import Media", self)
        act_imp.triggered.connect(self.import_file)
        tb.addAction(act_imp)
        act_exp = QAction("Export", self)
        act_exp.triggered.connect(self.start_export)
        tb.addAction(act_exp)
        tb.addSeparator()
        act_undo = QAction("Undo", self)
        act_undo.setShortcut("Ctrl+Z")
        act_undo.triggered.connect(self.undo)
        tb.addAction(act_undo)
        act_split = QAction("Split Clip", self)
        act_split.setShortcut("Ctrl+K")
        act_split.triggered.connect(self.split_current_clip)
        tb.addAction(act_split)
        act_del = QAction("Delete", self)
        act_del.setShortcut("Del")
        act_del.triggered.connect(self.delete_current_clip)
        tb.addAction(act_del)
        self.combo_res = QComboBox()
        self.combo_res.addItems([
            "Landscape 1920x1080 (HD)", "Landscape 3840x2160 (4K)",
            "Portrait 1080x1920 (Mobile HD)", "Portrait 1440x2560 (Mobile QHD)"
        ])
        self.combo_res.currentTextChanged.connect(self.update_res_mode)
        tb.addWidget(QLabel("  Output: "))
        tb.addWidget(self.combo_res)
        tb.addSeparator()
        act_play = QAction("Play/Pause", self)
        act_play.setShortcut("Space")
        act_play.triggered.connect(self.toggle_play)
        tb.addAction(act_play)

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
    def split_current_clip(self):
        item = self.timeline.get_selected_item()
        if not item: return
        ph = self.timeline.playhead_pos
        if not (item.start < ph < item.start + item.duration):
            return 
        self.save_state_for_undo()
        split_point_relative = ph - item.start
        right_dur = item.duration - split_point_relative
        right_start = ph
        left_dur = split_point_relative
        item.duration = left_dur
        item.setRect(0, 0, left_dur * 50, 90)
        new_data = {
            'uid': str(os.urandom(4).hex()),
            'name': item.name,
            'path': item.name,
            'start': right_start,
            'dur': right_dur,
            'track': item.track
        }
        self.timeline.add_clip(new_data)

    def delete_current_clip(self):
        if self.timeline.get_selected_item():
            self.save_state_for_undo()
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
    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import")
        if not path: return
        self.process_import(path, track=0, start_time=self.timeline.playhead_pos)

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
            'track': target['track']
        }
        self.timeline.add_clip(clip_data)
        if len(self.timeline.get_state()) == 1:
            self.player_node.load(info['path'])

    def on_clip_selected(self, clip_data):
        self.inspector.set_clip(clip_data)

    def on_clip_selected(self, clip_item):
        if clip_item:
            self.inspector.set_clip(clip_item.model)
        else:
            self.inspector.set_clip(None)

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
