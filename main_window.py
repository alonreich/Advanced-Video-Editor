import os
import logging
import json
import time
from PyQt5.QtWidgets import (QMainWindow, QDockWidget, QAction, QToolButton, QMenu, 
                             QWidget, QSizePolicy, QPushButton, QLabel, QMessageBox, 
                             QActionGroup, QDesktopWidget, QSplitter, QListWidgetItem)
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
from player_vlc import VLCPlayer
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
        self.player_node = VLCPlayer()
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
        self.inspector.track_mute_toggled.connect(lambda t, m: (self.track_mutes.update({t:m}), self.mark_dirty()))
        self.inspector.param_changed.connect(self.clip_ctrl.on_param_changed)
        self.inspector.resolution_changed.connect(self.on_resolution_switched)
        self.media_pool.media_double_clicked.connect(self.on_media_pool_double_click)

    def on_resolution_switched(self, res_text):
        """Goal 10: Handle Landscape/Portrait toggle across the UI."""
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
        vlc_status = "VLC-READY" if os.environ.get("PYTHON_VLC_MODULE_PATH") else "VLC-MISSING"
        self.setWindowTitle(f"Advanced Video Editor [{vlc_status}]")
        self.setWindowIcon(QIcon(os.path.join(self.base_dir, "icon", "Gemini_Generated_Image_prevzwprevzwprev.png")))
        self.resize(1825, 945)
        screen = QDesktopWidget().screenGeometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
        self.setDockOptions(QMainWindow.AllowNestedDocks | QMainWindow.AnimatedDocks)
        self.setStyleSheet("""
            QMainWindow::separator {
                background-color: #CCCCCC;
                width: 7px;
                height: 7px;
            }
            QMainWindow::separator:hover {
                background-color: #4A90E2;
            }
        """)
        self.preview = PreviewWidget(None)
        self.setCentralWidget(self.preview)
        self.dock_timeline = QDockWidget("Timeline", self)
        self.dock_timeline.setObjectName("TimelineDock")
        self.timeline = TimelineContainer(main_window=self)
        self.dock_timeline.setWidget(self.timeline)
        self.dock_timeline.setMinimumHeight(150)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.dock_timeline)
        timeline_title_bar = CustomTitleBar("Timeline")
        self.dock_timeline.setTitleBarWidget(timeline_title_bar)
        self.dock_timeline.resizeEvent = lambda event: timeline_title_bar.update_title(f"Timeline ({event.size().width()}x{event.size().height()})")
        self.dock_insp = QDockWidget("Inspector", self)
        self.dock_insp.setObjectName("InspectorDock")
        self.inspector = InspectorWidget()
        self.dock_insp.setWidget(self.inspector)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock_insp)
        inspector_title_bar = CustomTitleBar("Inspector")
        self.dock_insp.setTitleBarWidget(inspector_title_bar)
        self.dock_insp.resizeEvent = lambda event: inspector_title_bar.update_title(f"Inspector ({event.size().width()}x{event.size().height()})")
        self.dock_pool = QDockWidget("Media Pool", self)
        self.dock_pool.setObjectName("MediaPoolDock")
        self.media_pool = MediaPoolWidget()
        self.dock_pool.setWidget(self.media_pool)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_pool)
        media_pool_title_bar = CustomTitleBar("Media Pool")
        self.dock_pool.setTitleBarWidget(media_pool_title_bar)
        self.dock_pool.resizeEvent = lambda event: media_pool_title_bar.update_title(f"Media Pool ({event.size().width()}x{event.size().height()})")
        self.dock_pool.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.dock_insp.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable | QDockWidget.DockWidgetClosable)
        self.dock_timeline.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self.dock_pool.widget().setMinimumWidth(100)
        self.dock_insp.widget().setMinimumWidth(250)
        self.resizeDocks([self.dock_pool, self.dock_insp], [228, 250], Qt.Horizontal)
        self.resizeDocks([self.dock_timeline], [180], Qt.Vertical)
        self.setup_toolbar()
        if g := self.config.get("geometry"): 
            self.restoreGeometry(QByteArray.fromHex(g.encode()))
        if s := self.config.get("state"): 
            self.restoreState(QByteArray.fromHex(s.encode()))
        self.resizeEvent = lambda event: self.setWindowTitle(f"Advanced Video Editor ({event.size().width()}x{event.size().height()})")

    def setup_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setObjectName("MainToolbar")
        tb.addAction("Import", self.import_media)
        tb.addAction("Add Music", self.import_music)
        tb.addSeparator()
        tb.addAction("Export", self.open_export)
        tb.addSeparator()
        tb.addAction("Undo", self.undo_action)
        tb.addAction("Split", lambda: self.clip_ctrl.split_current())
        tb.addAction("Delete", lambda: self.clip_ctrl.delete_current())
        self.act_snap = tb.addAction("🧲")
        self.act_snap.setCheckable(True)
        self.act_snap.setChecked(True)
        self.act_snap.toggled.connect(lambda e: setattr(self.timeline.timeline_view, 'snapping_enabled', e))
        self.act_ripple = tb.addAction("🌊")
        self.act_ripple.setToolTip("Ripple Edit (Auto-Close Gaps)")
        self.act_ripple.setCheckable(True)
        self.act_ripple.setChecked(True)
        self.act_crop = tb.addAction("Crop")
        self.act_crop.setCheckable(True)
        self.act_crop.toggled.connect(self.toggle_crop_mode)
        self.act_proxy = tb.addAction("Proxy")
        self.act_proxy.setCheckable(True)
        self.act_proxy.setChecked(True)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        btn_p = QToolButton()
        btn_p.setText("Project List")
        btn_p.setPopupMode(QToolButton.InstantPopup)
        self.p_menu = QMenu(self)
        btn_p.setMenu(self.p_menu)
        self.p_menu.aboutToShow.connect(lambda: self.proj_ctrl.populate_menu(self.p_menu))
        tb.addWidget(btn_p)
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
        btn_reset.clicked.connect(self.proj_ctrl.reset_project)
        tb.addWidget(btn_reset)
        tb.addWidget(QLabel(" "))
        btn_layout = QPushButton("Reset Layout")
        btn_layout.setStyleSheet(btn_style)
        btn_layout.clicked.connect(self.reset_layout)
        tb.addWidget(btn_layout)
        tb.addWidget(QLabel(" "))
        btn_del_all = QPushButton("Delete All Projects")
        btn_del_all.setStyleSheet(btn_style)
        btn_del_all.clicked.connect(self.proj_ctrl.delete_all_projects)
        tb.addWidget(btn_del_all)
        tb.addSeparator()
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

    def toggle_crop_mode(self, checked):
        self.preview.overlay.toggle_crop_mode()

    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key_C:
            if not self.recorder.is_recording:
                path = self.pm.get_voiceover_target()
                self.player_node.pause()
                self.recording_start_time = self.timeline.playhead_pos
                self.recorder.start_recording(path)
            else:
                self.recorder.stop_recording()
            event.accept()
            return
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Z:
                self.undo_action()
            elif event.key() == Qt.Key_Y:
                self.redo_action()
        super().keyPressEvent(event)

    def on_recording_started(self):
        self.statusBar().showMessage("🔴 RECORDING VOICEOVER... (Press 'C' to Stop)")
        self.timeline.setFocus()

    def on_recording_finished(self, path):
        self.statusBar().showMessage(f"Voiceover saved: {os.path.basename(path)}", 5000)
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        self.media_pool.addItem(item)
        if hasattr(self, 'asset_loader'):
            self.asset_loader.handle_drop(path, -1, self.recording_start_time)

    def reset_layout(self):
        if QMessageBox.question(self, 'Reset Layout', "Reset UI layout to default?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self.restoreState(self.initial_layout_state)
            self.restoreGeometry(self.initial_geometry)
            self.config.set("geometry", self.initial_geometry.toHex().data().decode())
            self.config.set("state", self.initial_layout_state.toHex().data().decode())

    def import_media(self): 
        self.asset_loader.import_dialog()

    def import_music(self): 
        self.asset_loader.import_dialog(music_only=True)

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
        if s := self.history.undo(None): 
            self.timeline.load_state(s)

    def redo_action(self):
        if s := self.history.redo(None):
            self.timeline.load_state(s)

    def undo_lock_acquire(self):
        """Captures initial state before interaction begins."""
        self._pre_interaction_state = self.timeline.get_state()
        self.undo_lock = True

    def undo_lock_release(self):
        """Commits the final delta after interaction ends."""
        self.undo_lock = False
        if hasattr(self, '_pre_interaction_state'):
            self.history.push(self.timeline.get_state(), force=True)
            self.mark_dirty()
            del self._pre_interaction_state

    def on_selection(self, item):
        self.inspector.set_clip(item.model if item else None, self.track_mutes.get(item.track if item else 0, False))
        self.preview.overlay.set_selected_clip(item.model if item else None)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        super().dropEvent(event)

    def closeEvent(self, e):
        self.asset_loader.cleanup()
        self.logger.info(f"closeEvent triggered.")
        timeline_state = self.timeline.get_state()
        ui = {
            "playhead": self.timeline.playhead_pos,
            "zoom": self.timeline.scale_factor,
            "scroll_x": self.timeline.horizontalScrollBar().value(),
            "scroll_y": self.timeline.verticalScrollBar().value(),
            "resolution": self.inspector.combo_res.currentText()
        }
        self.proj_ctrl.pm.save_state(timeline_state, ui, is_autosave=False)
        self.config.set("geometry", self.saveGeometry().toHex().data().decode())
        self.config.set("state", self.saveState().toHex().data().decode())
        self.config.set("inspector_width", self.dock_insp.width())
        self.config.set("media_pool_width", self.dock_pool.width())
        super().closeEvent(e)

    def save_crash_backup(self):
        """Goal 9: Attempt to restore last valid state via emergency sidecar log."""
        self.logger.critical("CORE CRASH: Initializing Goal 9 Recovery...")
        try:
            current_state = self.timeline.get_state()
            self.pm.save_state(current_state, is_emergency=True)
        except Exception as e:
            self.logger.critical(f"Goal 9 Recovery FAILED: {e}")