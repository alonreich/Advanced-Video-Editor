from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QProgressBar, QPushButton, QFileDialog
from render_worker import RenderWorker

class ExportDialog(QDialog):
    def __init__(self, timeline_state, track_vols, track_mutes, res_mode, parent=None):
        super().__init__(parent)
        self.state = timeline_state
        self.vols = track_vols
        self.mutes = track_mutes
        self.res_mode = res_mode
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Export Video")
        self.resize(500, 400)
        l = QVBoxLayout(self)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        l.addWidget(self.console)
        self.bar = QProgressBar()
        l.addWidget(self.bar)
        btn = QPushButton("Start Export")
        btn.clicked.connect(self.start_export)
        l.addWidget(btn)

    def log(self, t):
        self.console.append(t)

    def start_export(self):
        out, _ = QFileDialog.getSaveFileName(self, "Save Video", "", "Video (*.mp4)")
        if not out: return
        self.worker = RenderWorker(self.state, out, self.res_mode, self.vols, self.mutes)
        self.worker.progress.connect(self.bar.setValue)
        self.worker.finished.connect(lambda: self.log("Done!"))
        self.worker.error.connect(lambda e: self.log(f"Error: {e}"))
        self.worker.start()
        self.log(f"Exporting to {out}...")
