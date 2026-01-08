from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QGridLayout, QPushButton
from PyQt5.QtCore import Qt

class ShortcutsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setFixedSize(400, 350)
        self.setStyleSheet("""
            QDialog { background-color: #1A1A1A; color: #E0E0E0; }
            QLabel { font-size: 13px; padding: 5px; }
            .key { color: #4A90E2; font-weight: bold; font-family: 'Consolas'; }
            .desc { color: #AAA; }
        """)
        layout = QVBoxLayout(self)
        title = QLabel("Command Reference")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white; margin-bottom: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        grid = QGridLayout()
        shortcuts = [
            ("C", "Toggle Interactive Crop Mode"),
            ("V (Hold)", "Record Voiceover at Playhead"),
            ("Ctrl + K", "Split Selected Clip"),
            ("Delete", "Remove (Leave Gap)"),
            ("Shift + Delete", "Ripple Delete (Close Gap)"),
            ("[", "Trim Start to Playhead"),
            ("]", "Trim End to Playhead"),
            ("Arrows", "Frame Step"),
            ("Ctrl + Arrows", "Aggressive Seek (3s)"),
            ("Space", "Play / Pause")
        ]
        for i, (key, desc) in enumerate(shortcuts):
            k_lbl = QLabel(key)
            k_lbl.setProperty("class", "key")
            k_lbl.setStyleSheet("color: #4A90E2; font-weight: bold;")
            d_lbl = QLabel(desc)
            d_lbl.setStyleSheet("color: #AAA;")
            grid.addWidget(k_lbl, i, 0)
            grid.addWidget(d_lbl, i, 1)
        layout.addLayout(grid)
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("margin-top: 15px; background: #333; color: white; padding: 8px;")
        layout.addWidget(btn_close)