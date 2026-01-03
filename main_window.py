import os
import logging
from PyQt5.QtWidgets import QMainWindow, QDockWidget, QAction, QToolButton, QMenu, QWidget, QSizePolicy, QPushButton, QLabel, QMessageBox, QActionGroup
from PyQt5.QtCore import Qt, QByteArray
from project_controller import ProjectController
from clip_manager import ClipManager
from asset_loader import AssetLoader
from binary_manager import BinaryManager
from system import ConfigManager
from project import ProjectManager
from player import MPVPlayer
from timeline_container import TimelineContainer
from preview import PreviewWidget
from inspector import InspectorWidget
from history import UndoStack
from media_pool import MediaPoolWidget
from playback_manager import PlaybackManager
from timeline_view import Mode
from export_dialog import ExportDialog

class MainWindow(QMainWindow):
    def __init__(self, base_dir):
        super().__init__()
        BinaryManager.ensure_env()
        self.base_dir = base_dir
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.pm = ProjectManager(base_dir)
        self.history = UndoStack()
        self.config = ConfigManager(os.path.join(base_dir, "layout.json"))
        self.is_dirty = True
        self.undo_lock = False
        self.track_volumes = {}
        self.track_mutes = {}
        self.setup_ui()
        self.setup_controllers()
        self.proj_ctrl.load_initial()

    def setup_controllers(self):
        self.player_node = MPVPlayer(self)
        self.preview.set_player(self.player_node)
        self.proj_ctrl = ProjectController(self)
        self.clip_ctrl = ClipManager(self)
        self.asset_loader = AssetLoader(self)
        self.playback = PlaybackManager(self.player_node, self.timeline, self.inspector)
        self.playback.playhead_updated.connect(self.timeline.set_time)
        self.playback.state_changed.connect(lambda p: None)
        self.timeline.data_changed.connect(self.mark_dirty)
        self.timeline.file_dropped.connect(self.asset_loader.handle_drop)
        self.timeline.clip_selected.connect(self.on_selection)
        self.timeline.seek_request.connect(lambda d: (self.player_node.seek_relative(d), self.timeline.set_time(self.player_node.get_time())))
        self.timeline.clip_split_requested.connect(self.clip_ctrl.split_at)
        self.preview.param_changed.connect(self.clip_ctrl.on_param_changed)
        self.preview.play_requested.connect(self.toggle_play)
        self.preview.interaction_started.connect(self.undo_lock_acquire)
        self.preview.interaction_ended.connect(self.undo_lock_release)
        self.inspector.track_mute_toggled.connect(lambda t, m: (self.track_mutes.update({t:m}), self.mark_dirty()))
        self.inspector.param_changed.connect(self.clip_ctrl.on_param_changed)
        self.media_pool.itemDoubleClicked.connect(lambda i: self.asset_loader.handle_drop(i.data(Qt.UserRole), 0, 0.0))

    def setup_ui(self):
        self.resize(1600, 900)
        self.preview = PreviewWidget(None)
        self.setCentralWidget(self.preview)
        self.dock_timeline = QDockWidget("Timeline", self)
        self.timeline = TimelineContainer()
        self.dock_timeline.setWidget(self.timeline)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)
        self.dock_insp = QDockWidget("Inspector", self)
        self.inspector = InspectorWidget()
        self.dock_insp.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_insp)
        self.dock_pool = QDockWidget("Media Pool", self)
        self.media_pool = MediaPoolWidget()
        self.dock_pool.setWidget(self.media_pool)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_pool)
        self.setup_toolbar()
        if g := self.config.get("geometry"): self.restoreGeometry(QByteArray.fromHex(g.encode()))
        if s := self.config.get("state"): self.restoreState(QByteArray.fromHex(s.encode()))

    def setup_toolbar(self):
        tb = self.addToolBar("Main")
        tb.addAction("Import", self.import_media)
        tb.addAction("Export", self.open_export)
        tb.addSeparator()
        tb.addAction("Undo", self.undo)
        tb.addAction("Split", lambda: self.clip_ctrl.split_current())
        tb.addAction("Delete", lambda: self.clip_ctrl.delete_current())
        self.act_snap = tb.addAction("Magnet")
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(lambda e: setattr(self.timeline.timeline_view, 'snapping_enabled', e))
        self.act_proxy = tb.addAction("Proxy")
        self.act_proxy.setCheckable(True)
        spacer = QWidget(); spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        btn_p = QToolButton(); btn_p.setText("Projects")
        btn_p.setPopupMode(QToolButton.InstantPopup)
        self.p_menu = QMenu(self); btn_p.setMenu(self.p_menu)
        self.p_menu.aboutToShow.connect(lambda: self.proj_ctrl.populate_menu(self.p_menu))
        tb.addWidget(btn_p)

    def import_media(self): self.asset_loader.import_dialog()
    
    def open_export(self):
        dlg = ExportDialog(self.timeline.get_state(), self.track_volumes, self.track_mutes, self.inspector.combo_res.currentText(), self)
        dlg.exec_()

    def toggle_play(self):
        self.playback.toggle_play(self.act_proxy.isChecked(), self.track_volumes, self.track_mutes)

    def mark_dirty(self): self.is_dirty = True
    
    def save_state_for_undo(self):
        self.history.push(self.timeline.get_state())
        self.mark_dirty()

    def undo(self):
        if s := self.history.undo(None): self.timeline.load_state(s)
    
    def undo_lock_acquire(self): self.save_state_for_undo(); self.undo_lock = True
    def undo_lock_release(self): self.undo_lock = False
    
    def on_selection(self, item):
        self.inspector.set_clip(item.model if item else None, self.track_mutes.get(item.track if item else 0, False))
        self.preview.overlay.set_selected_clip(item.model if item else None)

    def closeEvent(self, e):
        self.asset_loader.cleanup()
        self.config.set("geometry", self.saveGeometry().toHex().data().decode())
        self.config.set("state", self.saveState().toHex().data().decode())
        super().closeEvent(e)

    def save_crash_backup(self):
        """Emergency endpoint called by the global exception hook."""
        self.logger.critical("Executing Emergency Crash Backup via ProjectController...")
        try:
            self.proj_ctrl.pm.save_state(self.timeline.get_state(), is_autosave=True)
        except Exception as e:
            self.logger.critical(f"Backup failed: {e}")
