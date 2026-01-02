from PyQt5.QtWidgets import QProgressDialog
import os
from exporter import FFmpegBuilder, RenderWorker
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QFileDialog, QDockWidget, QAction, QMessageBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QListView, QActionGroup, QMenu, QToolButton, QInputDialog
from PyQt5.QtWidgets import QSizePolicy, QPushButton
from PyQt5.QtCore import QTimer, Qt, QUrl, QMimeData, QByteArray
from PyQt5.QtGui import QPixmap, QDrag

from system import ConfigManager
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
        import logging
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.base_dir = base_dir
        self.pm = ProjectManager(base_dir)
        self.history = UndoStack()
        self.waveform_workers = []
        self.thumb_manager = ThumbnailWorker(self.base_dir)
        self.thumb_manager.thumbnail_generated.connect(self.on_thumbnail_done)
        self.thumb_manager.start()
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
        self.preview_offset = 0.0
        self.cached_start = -1.0
        self.cached_end = -1.0
        self.is_dirty = True

    def setup_ui(self):
        self.setWindowTitle("Advanced Video Editor")
        self.setStyleSheet("""
            QMainWindow::separator { background-color: #444; width: 4px; height: 4px; }
            QToolTip { font: 12pt 'Segoe UI'; background: #333; color: white; border: 1px solid #555; }
        """)
        self.resize(1600, 900)
        self.player_node = MPVPlayer(self)
        self.preview = PreviewWidget(self.player_node)
        self.preview.param_changed.connect(self.on_param_changed)
        self.preview.play_requested.connect(self.toggle_play)
        self.preview.seek_requested.connect(self.seek_relative)
        self.setCentralWidget(self.preview)
        self.dock_timeline = QDockWidget("Timeline", self)
        self.dock_timeline.setObjectName("TimelineDock")
        self.dock_timeline.setWidget(TimelineContainer())
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)
        self.timeline = self.dock_timeline.widget()
        self.timeline.seek_request.connect(self.seek_relative)
        self.timeline.timeline_view.data_changed.connect(self.mark_dirty)
        self.dock_inspector = QDockWidget("Inspector", self)
        self.dock_inspector.setObjectName("InspectorDock")
        self.inspector = InspectorWidget()
        self.dock_inspector.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_inspector)
        self.dock_media_pool = QDockWidget("Media Pool", self)
        self.dock_media_pool.setObjectName("MediaPoolDock")
        self.media_pool = MediaPoolWidget()
        self.media_pool.setDragEnabled(True)
        self.dock_media_pool.setWidget(self.media_pool)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_media_pool)
        self.timeline.time_updated.connect(self.user_seek)
        self.timeline.clip_selected.connect(self.on_clip_selected)
        self.timeline.file_dropped.connect(self.handle_timeline_drop)
        self.timeline.clip_split_requested.connect(self.split_clip_at)
        self.inspector.param_changed.connect(self.on_param_changed)
        self.inspector.resolution_changed.connect(self.update_res_mode)
        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.setMovable(False)
        tb.setStyleSheet("""
            QToolBar { background-color: #2A2A2A; border-bottom: 2px solid #555; spacing: 10px; min-height: 50px; }
            QToolButton { background: transparent; color: white; font-weight: bold; padding: 5px 10px; }
            QToolButton:hover { background: #444; border-radius: 4px; }
        """)
        tb.addAction("Import Media", self.import_file).setToolTip("Import media files")
        tb.addAction("Export", self.start_export).setToolTip("Export video")
        tb.addSeparator()
        tb.addAction("Undo (Ctrl+Z)", self.undo)
        tb.addAction("Split (Ctrl+K)", self.split_current_clip)
        tb.addAction("Delete (Del)", self.delete_current_clip)
        tb.addSeparator()
        ag = QActionGroup(self)
        act_ptr = tb.addAction("Pointer")
        act_ptr.setCheckable(True)
        act_ptr.setChecked(True)
        act_ptr.triggered.connect(lambda: self.timeline.set_mode(Mode.POINTER))
        ag.addAction(act_ptr)
        act_raz = tb.addAction("Razor")
        act_raz.setCheckable(True)
        act_raz.triggered.connect(lambda: self.timeline.set_mode(Mode.RAZOR))
        ag.addAction(act_raz)
        act_crop = tb.addAction("Crop Tool")
        act_crop.triggered.connect(lambda: self.preview.overlay.toggle_crop_mode())
        
        tb.addSeparator()
        self.act_proxy = tb.addAction("🚀 Proxy")
        self.act_proxy.setCheckable(True)
        self.act_proxy.setToolTip("Enable Fast Preview (Half Resolution)")
        self.act_proxy.setChecked(False)  # Off by default

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.btn_proj_list = QToolButton()
        self.btn_proj_list.setText("Project List")
        self.btn_proj_list.setPopupMode(QToolButton.InstantPopup)
        self.btn_proj_list.setStyleSheet("""
            QToolButton {
                background: #333; color: #FFF; border: 1px solid #555; padding: 5px 15px; font-weight: bold; border-radius: 4px;
            }
            QToolButton:hover { background: #444; }
            QToolButton::menu-indicator { image: none; }
        """)
        self.proj_menu = QMenu(self)
        self.proj_menu.aboutToShow.connect(self.populate_project_menu)
        self.btn_proj_list.setMenu(self.proj_menu)
        tb.addWidget(self.btn_proj_list)
        tb.addWidget(QLabel("  "))
        btn_style = """
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #B71C1C, stop:1 #7F0000);
                color: white; border: 1px solid #500; border-radius: 4px; padding: 5px; min-width: 80px; font-weight: bold;
                border-style: outset;
            }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #D32F2F, stop:1 #8E0000); }
            QPushButton:pressed { border-style: inset; background: #500; }
        """
        btn_reset = QPushButton("Reset Project")
        btn_reset.setStyleSheet(btn_style)
        btn_reset.clicked.connect(self.reset_project)
        tb.addWidget(btn_reset)
        tb.addWidget(QLabel(" ")) 
        btn_layout = QPushButton("Reset Layout")
        btn_layout.setStyleSheet(btn_style)
        btn_layout.clicked.connect(self.reset_layout)
        tb.addWidget(btn_layout)
        tb.addWidget(QLabel(" "))
        btn_del_all = QPushButton("Delete All Projects")
        btn_del_all.setStyleSheet(btn_style)
        btn_del_all.clicked.connect(self.delete_all_projects_confirm)
        tb.addWidget(btn_del_all)
        self.config = ConfigManager(os.path.join(self.base_dir, "layout.json"))
        self.initial_layout_state = self.saveState()
        self.initial_geometry = self.saveGeometry()
        saved_geom = self.config.get("geometry")
        saved_state = self.config.get("state")
        if saved_geom: self.restoreGeometry(QByteArray.fromHex(saved_geom.encode()))
        if saved_state: self.restoreState(QByteArray.fromHex(saved_state.encode()))

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
        reply = QMessageBox.question(self, 'Reset Layout', 
                                     "Are you sure you want to reset the UI layout to default?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.restoreState(self.initial_layout_state)
            self.restoreGeometry(self.initial_geometry)
            self.config.set("geometry", self.initial_geometry.toHex().data().decode())
            self.config.set("state", self.initial_layout_state.toHex().data().decode())

    def closeEvent(self, event):
        self.thumb_manager.stop()
        self.config.set("geometry", self.saveGeometry().toHex().data().decode())
        self.config.set("state", self.saveState().toHex().data().decode())
        super().closeEvent(event)

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
            'source_in': item.model.source_in + split_point_relative,
            'source_duration': item.model.source_duration,  # Preserve total length
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

        # SAVE STATE before modifying!
        # Check if the value actually changed to avoid spamming undo stack
        current_val = getattr(item.model, param, None)
        if current_val != value:
            self.save_state_for_undo()

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
        last_dir = self.config.get("last_import_dir", self.base_dir)
        paths, _ = QFileDialog.getOpenFileNames(self, "Import", last_dir)
        if not paths: return
        self.config.set("last_import_dir", os.path.dirname(paths[0]))
        for path in paths:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.media_pool.addItem(item)

    def handle_timeline_drop(self, path, track_idx, start_time):
        self.logger.info(f"Handling timeline drop -> Path: {path} | Track: {track_idx} | Time: {start_time}")
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
            'source_in': 0.0,
            'source_duration': info['duration'],
            'track': target['track'],
            'width': info.get('width', 1920),
            'height': info.get('height', 1080),
            'bitrate': info.get('bitrate', 0)
        }
        self.timeline.add_clip(clip_data)
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
        self.thumb_manager.add_task(clip_data['path'], clip_data['uid'], clip_data['dur'])

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
        try:
            if self.player_node.is_playing():
                t = self.player_node.get_time()
                real_time = t + self.preview_offset
                self.timeline.set_time(real_time)
                max_end = 0
                for item in self.timeline.scene.items():
                    if isinstance(item, ClipItem):
                        if (item.start + item.duration) > max_end:
                            max_end = item.start + item.duration
                if max_end > 0 and t >= max_end + 0.1:
                    self.logger.info(f"Playback reached end of content ({max_end:.2f}s). Pausing.")
                    self.player_node.pause()
                    self.player_node.seek(max_end)
                    self.timeline.set_time(max_end)
        except Exception:
            self.timer.stop()

    def mark_dirty(self):
        self.is_dirty = True
        self.logger.info("Timeline marked dirty. Next play will re-render.")

    def toggle_play(self):
        if self.player_node.is_playing():
            self.player_node.pause()
            return
        current_time = self.timeline.playhead_pos
        if not self.is_dirty and self.cached_start <= current_time < (self.cached_end - 0.5):
            self.logger.info("Cache Hit! Reuse existing preview.")
            rel_seek = max(0.0, current_time - self.cached_start)
            self.player_node.seek(rel_seek)
            self.player_node.play()
            return
        self.logger.info("Cache Miss or Dirty. Generating new preview...")
        state = self.timeline.get_state()
        if not state: return
        start_time = current_time
        max_end = 0
        for item in self.timeline.scene.items():
            if isinstance(item, ClipItem):
                 max_end = max(max_end, item.start + item.duration)
        duration = max(30.0, max_end - start_time + 2.0)
        duration = min(duration, 300.0)
        cache_dir = os.path.join(self.base_dir, "cache")
        os.makedirs(cache_dir, exist_ok=True)
        preview_path = os.path.join(cache_dir, "preview.mp4")
        res_mode = self.inspector.combo_res.currentText()
        
        # Pass proxy state to builder
        use_proxy = self.act_proxy.isChecked()
        if use_proxy: self.logger.info("Building Preview in PROXY mode (Half-Res)")
            
        builder = FFmpegBuilder(state, preview_path, res_mode, start_time=start_time, duration=duration, proxy=use_proxy)
        self._pending_cache_start = start_time
        self._pending_cache_end = start_time + duration
        self.preview_worker = RenderWorker(builder)
        self.preview_worker.finished.connect(lambda: self.on_preview_ready(preview_path, start_time))
        self.preview_worker.error.connect(lambda e: self.logger.error(f"Preview Failed: {e}"))
        self.preview_worker.start()

    def on_preview_ready(self, path, start_time):
        self.logger.info(f"Preview Ready (Start: {start_time}). Playing.")
        self.cached_start = self._pending_cache_start
        self.cached_end = self._pending_cache_end
        self.preview_offset = start_time
        self.is_dirty = False
        self.player_node.load(path)
        self.player_node.play()

    def seek_relative(self, delta):
        t = self.player_node.get_time()
        new_t = max(0.0, t + delta)
        self.player_node.seek(new_t)
        self.timeline.set_time(new_t)

    def update_res_mode(self, text):
        w, h = 1920, 1080
        if "1080x1920" in text: w, h = 1080, 1920
        self.preview.set_mode(w, h, text)

    # C:\Fortnite_Video_Software\advanced\main_window.py

# Add this import at the top
from PyQt5.QtWidgets import QProgressDialog

# Replace the start_export method (Source 170)
    def start_export(self):
        state = self.timeline.get_state()
        if not state: return
        
        last_dir = self.config.get("last_export_dir", self.base_dir)
        out, _ = QFileDialog.getSaveFileName(self, "Export", last_dir, filter="MP4 (*.mp4)")
        if not out: return
        
        self.config.set("last_export_dir", os.path.dirname(out))
        res_mode = self.inspector.combo_res.currentText()
        
        # Disable Player
        self.player_node.pause()
        
        # Create Builder
        builder = FFmpegBuilder(state, out, res_mode)
        
        # Setup Modal Progress Dialog
        self.progress_dlg = QProgressDialog("Exporting Video...", "Cancel", 0, 100, self)
        self.progress_dlg.setWindowModality(Qt.WindowModal)
        self.progress_dlg.setAutoClose(True)
        self.progress_dlg.setAutoReset(True)
        self.progress_dlg.show()
        
        self.render_worker = RenderWorker(builder)
        self.render_worker.progress.connect(self.progress_dlg.setValue)
        
        # Handle Finish
        self.render_worker.finished.connect(lambda: QMessageBox.information(self, "Done", "Export Successful"))
        self.render_worker.finished.connect(self.progress_dlg.close)
        
        # Handle Error
        self.render_worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.render_worker.error.connect(self.progress_dlg.close)
        
        # Handle Cancel (Kill FFmpeg)
        self.progress_dlg.canceled.connect(self.render_worker.terminate)
        
        self.render_worker.start()

    def delete_all_projects_confirm(self):
        reply = QMessageBox.warning(self, "DELETE ALL", 
                                    "This will PERMANENTLY DELETE ALL PROJECTS, CACHE, and restart the app!\nAre you sure?", 
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            import shutil
            import sys
            folders = ["cache", "projects", "__pycache__"]
            for f in folders:
                path = os.path.join(self.base_dir, f)
                if os.path.exists(path):
                    try:
                        shutil.rmtree(path)
                    except Exception as e:
                        self.logger.error(f"Failed to delete {path}: {e}")
            os.execl(sys.executable, sys.executable, *sys.argv)

    def populate_project_menu(self):
        self.proj_menu.clear()
        act_rename = QAction(f"Rename: {self.pm.project_name}", self)
        act_rename.triggered.connect(self.rename_current_project)
        self.proj_menu.addAction(act_rename)
        act_save_as = QAction("Save Project As...", self)
        act_save_as.triggered.connect(self.save_project_as_dialog)
        self.proj_menu.addAction(act_save_as)
        self.proj_menu.addSeparator()
        projects = self.pm.get_all_projects()
        for p in projects:
            date_str = p['last_saved'].split('.')[0]
            display_text = f"{p['name']}  [{date_str}]"
            action = QAction(display_text, self)
            if p['id'] == self.pm.project_id:
                action.setEnabled(False)
                action.setText(f"✓ {display_text}")
            else:
                action.triggered.connect(lambda checked, d=p['dir']: self.switch_project(d))
            self.proj_menu.addAction(action)

    def rename_current_project(self):
        new_name, ok = QInputDialog.getText(self, "Rename Project", "Enter new project name:", text=self.pm.project_name)
        if ok and new_name:
            self.pm.set_project_name(new_name)
            self.save_state_for_undo()
            self.setWindowTitle(f"Advanced Video Editor - {new_name}")

    def save_project_as_dialog(self):
        new_name, ok = QInputDialog.getText(self, "Save Project As", 
                                            "Enter name for the copy:", 
                                            text=f"{self.pm.project_name} - Copy")
        if ok and new_name:
            self.save_state_for_undo() 
            current_state = self.timeline.get_state()
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                new_dir = self.pm.save_project_as(new_name, current_state)
            finally:
                QApplication.restoreOverrideCursor()
            if new_dir:
                self.switch_project(new_dir)
                QMessageBox.information(self, "Success", f"Project saved as '{new_name}' and switched to it.")

    def switch_project(self, project_dir):
        self.save_state_for_undo()
        data = self.pm.load_project_from_dir(project_dir)
        if data:
            self.timeline.load_state(data.get('timeline', []))
            self.media_pool.clear()
            self.setWindowTitle(f"Advanced Video Editor - {self.pm.project_name}")
