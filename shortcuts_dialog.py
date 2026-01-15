import json
import logging
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QGridLayout, QPushButton, QFileDialog, QKeySequenceEdit,
                             QScrollArea, QWidget, QDesktopWidget)

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence

class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mw = parent
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.setWindowTitle("Custom Keyboard Shortcut Keys")
        self.setFixedSize(700, 800)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self._center_on_screen()
        self.setStyleSheet("""
            QDialog { background-color: #121212; color: #E0E0E0; }
            QLabel { font-size: 14px; color: #CCC; font-weight: bold; }
            QScrollArea { border: none; background-color: transparent; }
            QKeySequenceEdit { 
                background: #1E1E1E; color: #4A90E2; border: 1px solid #333; 
                padding: 5px; font-weight: bold; font-family: 'Consolas';
            }
            QPushButton { 
                background: #333; color: white; padding: 10px; 
                border-radius: 4px; font-weight: bold; min-width: 120px;
            }
            QPushButton:hover { background: #444; }
            #ResetBtn {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #8b0000, stop:1 #4a0000);
                border: 1px solid #ff4444;
                color: #ffcccc;
            }
            #ResetBtn:hover { background: #a50000; }
        """)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("Custom Keyboard Shortcut Keys")
        title.setStyleSheet("font-size: 22px; color: white; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.grid = QGridLayout(self.scroll_content)
        self.grid.setVerticalSpacing(15)
        self.grid.setColumnStretch(0, 1)
        self.scroll.setWidget(self.scroll_content)
        self.main_layout.addWidget(self.scroll)
        self.defaults = {
            "Toggle Interactive Crop Mode": "C",
            "Record Voiceover": "V",
            "Split Selected Clip": "Ctrl+K",
            "Remove (Leave Gap)": "Del",
            "Ripple Delete": "Shift+Del",
            "Trim Start": "[",
            "Trim End": "]",
            "Frame Step": "Right",
            "Aggressive Seek": "Ctrl+Right",
            "Play / Pause": "Space"
        }
        self.edit_widgets = {}
        self.load_and_populate()
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.btn_import = QPushButton("Import Keybinds")
        self.btn_export = QPushButton("Export Keybinds")
        self.btn_reset = QPushButton("Reset to Default")
        self.btn_reset.setObjectName("ResetBtn")
        self.btn_save = QPushButton("Apply")
        for b in [self.btn_import, self.btn_export, self.btn_reset, self.btn_save]:
            b.setCursor(Qt.PointingHandCursor)
            btn_layout.addWidget(b)
        self.main_layout.addLayout(btn_layout)
        self.btn_import.clicked.connect(self.import_bindings)
        self.btn_export.clicked.connect(self.export_bindings)
        self.btn_reset.clicked.connect(self.reset_to_defaults)
        self.btn_save.clicked.connect(self.save_and_close)

    def _center_on_screen(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def load_and_populate(self):
        """Loads shortcuts from config and populates the scrollable grid."""
        current_data = self.mw.shortcuts_config.get("shortcuts", self.defaults)
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setParent(None)
        for i, (desc, key) in enumerate(current_data.items()):
            lbl = QLabel(desc)
            edit = QKeySequenceEdit(QKeySequence(key))
            edit.setFixedWidth(200)
            self.grid.addWidget(lbl, i, 0)
            self.grid.addWidget(edit, i, 1)
            self.edit_widgets[desc] = edit

    def reset_to_defaults(self):
        """Resets UI to the initial application hardcoded shortcuts."""
        for desc, edit in self.edit_widgets.items():
            if desc in self.defaults:
                edit.setKeySequence(QKeySequence(self.defaults[desc]))
        self.logger.info("[UI] Shortcuts UI reset to factory defaults.")

    def save_and_close(self):
        final_map = {desc: w.keySequence().toString() for desc, w in self.edit_widgets.items()}
        self.mw.shortcuts_config.set("shortcuts", final_map)
        self.accept()

    def export_bindings(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Shortcuts", "", "JSON Files (*.json)")
        if path:
            current_map = {desc: w.keySequence().toString() for desc, w in self.edit_widgets.items()}
            with open(path, 'w') as f:
                json.dump(current_map, f, indent=4)

    def import_bindings(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Shortcuts", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, 'r') as f:
                    new_data = json.load(f)
                self.mw.config.set("shortcuts", new_data)
                self.load_and_populate()
            except Exception as e:
                self.logger.error(f"Import failed: {e}")