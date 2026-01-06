import os
import logging
import json
import time
from PyQt5.QtWidgets import (QMainWindow, QDockWidget, QAction, QToolButton, QMenu, 
                             QWidget, QSizePolicy, QPushButton, QLabel, QMessageBox, 
                             QActionGroup, QDesktopWidget, QSplitter, QListWidgetItem, QStyle)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt, QByteArray
from project_controller import ProjectController
from clip_manager import ClipManager
from asset_loader import AssetLoader
from binary_manager import BinaryManager
from system import ConfigManager
from project import ProjectManager
from playback_manager import PlaybackManager
from history import UndoStack
from recorder import VoiceoverRecorder
from player import MPVPlayer
from timeline_container import TimelineContainer
from preview import PreviewWidget
from inspector import InspectorWidget
from media_pool import MediaPoolWidget
from export_dialog import ExportDialog
from custom_title_bar import CustomTitleBar

class MainWindow(QMainWindow):
    def __init__(self, base_dir):
        super().__init__()
        BinaryManager.ensure_env()
        self.base_dir = base_dir
        self.is_dirty = False
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.pm = ProjectManager(base_dir)
        self.history = UndoStack()
        self.config = ConfigManager(os.path.join(base_dir, "..", "config", "advanced_video_editor.conf"))
        self.proj_ctrl = ProjectController(self)
        self.clip_ctrl = ClipManager(self)
        self.asset_loader = AssetLoader(self)
        self.undo_lock = False
        self.track_volumes = {}
        self.track_mutes = {}
        self.player_node = MPVPlayer()
        self.recorder = VoiceoverRecorder()
        self.recorder.recording_started.connect(self.on_recording_started)
        self.recorder.recording_finished.connect(self.on_recording_finished)
        self.recording_start_time = 0.0
        self.setup_ui()
        self.initial_layout_state = self.saveState()
        self.initial_geometry = self.saveGeometry()
        self.finalize_setup()
        self.proj_ctrl.load_initial()

    def on_media_pool_double_click(self, path):
        self.logger.info(f"on_media_pool_double_click called with path: {path}")
        self.asset_loader.handle_drop(path, -1, 0.0)
        try:
            self.timeline.set_time(0.0)
        except Exception:
            pass

    def finalize_setup(self):
        self.preview.set_player(self.player_node)
        self.playback = PlaybackManager(self.player_node, self.timeline, self.inspector)
        self.playback.playhead_updated.connect(self.timeline.set_visual_time)
        self.timeline.time_updated.connect(self.player_node.seek)
        self.playback.state_changed.connect(lambda p: None)
        self.timeline.data_changed.connect(self.mark_dirty)
        self.timeline.file_dropped.connect(self.asset_loader.handle_drop)
        self.timeline.clip_selected.connect(self.on_selection)
        self.timeline.seek_request.connect(lambda d: (self.player_node.seek_relative(d), self.timeline.set_time(self.player_node.get_time())))
        self.timeline.clip_split_requested.connect(self.clip_ctrl.split_at)
        self.preview.param_changed.connect(self.clip_ctrl.on_param_changed)
        self.preview.play_requested.connect(self.toggle_play)
        self.preview.interaction_started.connect(self.clip_ctrl.undo_lock_acquire)
        self.preview.interaction_ended.connect(self.clip_ctrl.undo_lock_release)
        self.timeline.interaction_ended.connect(self.timeline.fit_to_view)
        self.inspector.track_mute_toggled.connect(lambda t, m: (self.track_mutes.update({t:m}), self.mark_dirty()))
        self.inspector.param_changed.connect(self.clip_ctrl.on_param_changed)
        self.inspector.resolution_changed.connect(self.on_resolution_switched)
        self.inspector.crop_toggled.connect(self.toggle_crop_mode)
        self.media_pool.media_double_clicked.connect(self.on_media_pool_double_click)
        self.proj_ctrl.setup_project_menu()

    def on_resolution_switched(self, res_text):
        w, h = (1080, 1920) if "Portrait" in res_text else (1920, 1080)
        if "2560" in res_text: w, h = 2560, 1440
        elif "3840" in res_text: w, h = 3840, 2160
        self.preview.set_mode(w, h, res_text)
        self.playback.set_resolution(w, h)
        self.playback.mark_dirty(serious=True)
        self.logger.info(f"Project switched to {res_text} ({w}x{h})")
        self.is_dirty = True

    def setup_ui(self):
        self.setAcceptDrops(True)
        self.setWindowTitle("Advanced Video Editor")
        self.setWindowIcon(QIcon(os.path.join(self.base_dir, "icon", "Gemini_Generated_Image_prevzwprevzwprev.png")))
        self.resize(1700, 945)
        screen = QDesktopWidget().screenGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AnimatedDocks)
        self.setStyleSheet("""
            QMainWindow::separator { background-color: #CCCCCC; width: 7px; height: 7px; }
            QMainWindow::separator:hover { background-color: #4A90E2; }
        """)
        self.preview = PreviewWidget(self.player_node)
        self.setCentralWidget(self.preview)
        self.dock_timeline = QDockWidget("Timeline", self)
        self.dock_timeline.setObjectName("TimelineDock")
        self.timeline = TimelineContainer(main_window=self)
        self.dock_timeline.setWidget(self.timeline)
        self.dock_timeline.setMinimumHeight(150)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)
        self.dock_insp = QDockWidget("Inspector", self)
        self.dock_insp.setObjectName("InspectorDock")
        self.inspector = InspectorWidget()
        self.dock_insp.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_insp)
        self.dock_pool = QDockWidget("Media Pool", self)
        self.dock_pool.setObjectName("MediaPoolDock")
        self.media_pool = MediaPoolWidget()
        self.dock_pool.setWidget(self.media_pool)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_pool)
        self.dock_pool.widget().setMinimumWidth(100)
        self.dock_insp.widget().setMinimumWidth(250)
        self.resizeDocks([self.dock_pool, self.dock_insp], [228, 250], Qt.Horizontal)
        self.resizeDocks([self.dock_timeline], [180], Qt.Vertical)
        self.setup_toolbar()
        if g := self.config.get("geometry"): self.restoreGeometry(QByteArray.fromHex(g.encode()))
        if s := self.config.get("state"): self.restoreState(QByteArray.fromHex(s.encode()))

    def setup_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.setStyleSheet("QToolButton, QPushButton { font-size: 13px; padding: 5px; }")
        import_action = QAction("📂  Import Media", self)
        import_action.triggered.connect(self.import_media)
        tb.addAction(import_action)
        tb.addSeparator()
        tb.addAction("Export Video", self.open_export)
        tb.addSeparator()
        tb.addAction("Undo", self.undo_action)
        tb.addAction("Split", lambda: self.clip_ctrl.split_current())
        tb.addAction("Delete", lambda: self.clip_ctrl.delete_current())
        self.act_snap = tb.addAction("🧲")
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(lambda e: setattr(self.timeline.timeline_view, 'snapping_enabled', e))
        self.act_ripple = tb.addAction("🌊")
        self.act_ripple.setCheckable(True)
        self.act_ripple.setChecked(True)
        self.act_proxy = tb.addAction("Proxy")
        self.act_proxy.setCheckable(True)
        self.act_proxy.setChecked(True)
        self.btn_projects = QToolButton()
        self.btn_projects.setText(" Projects ")
        self.btn_projects.setPopupMode(QToolButton.InstantPopup)
        self.btn_projects.setAutoRaise(True)
        self.projects_menu = QMenu(self.btn_projects)
        self.projects_menu.aboutToShow.connect(lambda: self.proj_ctrl.populate_project_list(self.projects_menu))
        self.btn_projects.setMenu(self.projects_menu)
        self.btn_projects.setStyleSheet("QToolButton { font-size: 13px; font-weight: normal; color: #E0E0E0; padding: 5px; }")
        tb.addWidget(self.btn_projects)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        btn_reset_layout = QPushButton("Reset Layout")
        btn_reset_layout.clicked.connect(self.reset_layout)
        btn_reset_layout.setStyleSheet("background-color: #D32F2F; color: white; font-weight: bold; border-radius: 3px; padding: 5px; margin-right: 5px;")
        tb.addWidget(btn_reset_layout)
        btn_reset_proj = QPushButton("Reset Project")
        btn_reset_proj.clicked.connect(self.proj_ctrl.reset_project)
        btn_reset_proj.setStyleSheet("background-color: #C62828; color: white; font-weight: bold; border-radius: 3px; padding: 5px; margin-right: 5px;")
        tb.addWidget(btn_reset_proj)
        btn_nuke = QPushButton("DELETE ALL")
        btn_nuke.clicked.connect(self.proj_ctrl.delete_all_projects)
        btn_nuke.setStyleSheet("background-color: #B71C1C; color: white; font-weight: bold; border-radius: 3px; padding: 5px;")
        tb.addWidget(btn_nuke)

    def toggle_crop_mode(self, checked):
        state = checked if isinstance(checked, bool) else not self.preview.overlay.crop_mode
        if state != self.preview.overlay.crop_mode:
            self.preview.overlay.toggle_crop_mode()
        if hasattr(self.inspector, 'btn_crop_toggle'):
            self.inspector.btn_crop_toggle.setChecked(self.preview.overlay.crop_mode)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C:
            self.toggle_crop_mode(not self.preview.overlay.crop_mode)
            event.accept()
            return
        if event.key() == Qt.Key_V:
            if not self.recorder.is_recording:
                path = self.pm.get_voiceover_target()
                self.player_node.pause()
                self.recording_start_time = self.timeline.playhead_pos
                self.recorder.start_recording(path)
            else:
                self.recorder.stop_recording()
            event.accept()
            return
        if self.preview.overlay.crop_mode and event.key() in [Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down]:
            self.preview.overlay.handle_arrow_keys(event)
            event.accept()
            return
        super().keyPressEvent(event)

    def on_recording_started(self):
        self.statusBar().showMessage("🔴 RECORDING VOICEOVER...")

    def on_recording_finished(self, path):
        self.statusBar().showMessage(f"Voiceover saved: {os.path.basename(path)}", 5000)
        self.asset_loader.handle_drop(path, -1, self.recording_start_time)

    def reset_layout(self):
        self.restoreState(self.initial_layout_state)
        self.restoreGeometry(self.initial_geometry)

    def import_media(self): 
        self.asset_loader.import_dialog()

    def open_export(self):
        dlg = ExportDialog(self.timeline.get_state(), self.track_volumes, self.track_mutes, self.inspector.combo_res.currentText(), self)
        dlg.exec_()

    def toggle_play(self):
        self.playback.toggle_play(self.act_proxy.isChecked(), self.track_volumes, self.track_mutes)

    def mark_dirty(self): 
        self.is_dirty = True

    def save_state_for_undo(self):
        self.history.push(self.timeline.get_state())
        self.mark_dirty()

    def undo_action(self):
        if s := self.history.undo(self.timeline.get_state()): self.timeline.load_state(s)

    def redo_action(self):
        if s := self.history.redo(self.timeline.get_state()): self.timeline.load_state(s)

    def on_selection(self, item):
        self.inspector.set_clip(item.model if item else None, self.track_mutes.get(item.track if item else 0, False))
        self.preview.overlay.set_selected_clip(item.model if item else None)

    def closeEvent(self, e):
        self.asset_loader.cleanup()
        self.player_node.cleanup()
        pool_assets = []
        for i in range(self.media_pool.count()):
            item = self.media_pool.item(i)
            path = item.data(Qt.UserRole)
            if path:
                pool_assets.append(path)
        ui = {
            "playhead": self.timeline.playhead_pos,
            "zoom": self.timeline.scale_factor,
            "scroll_x": self.timeline.horizontalScrollBar().value(),
            "scroll_y": self.timeline.verticalScrollBar().value(),
            "resolution": self.inspector.combo_res.currentText()
        }
        self.proj_ctrl.pm.save_state(self.timeline.get_state(), ui, assets=pool_assets)
        self.config.set("geometry", self.saveGeometry().toHex().data().decode())
        self.config.set("state", self.saveState().toHex().data().decode())
        super().closeEvent(e)