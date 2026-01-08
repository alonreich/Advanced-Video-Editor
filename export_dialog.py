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
        est_text = self.calculate_estimate()
        self.lbl_estimate = QLabel(est_text)
        self.lbl_estimate.setStyleSheet("font-size: 13px; font-weight: bold; color: #4A90E2; padding: 5px;")
        l.addWidget(self.lbl_estimate)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        l.addWidget(self.console)
        self.bar = QProgressBar()
        l.addWidget(self.bar)
        btn = QPushButton("Start Export")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Start the video export process")
        btn.clicked.connect(self.start_export)
        l.addWidget(btn)

    def calculate_estimate(self):
        """Calculates rough file size based on duration and target bitrate."""
        if not self.state:
            return "Duration: 0s | Est. File Size: 0 MB"
        max_duration = 0.0
        for clip in self.state:
            end = clip.get('start', 0.0) + clip.get('dur', 0.0)
            if end > max_duration:
                max_duration = end

        is_high_fps = "60" in self.res_mode or "120" in self.res_mode

        if "2160" in self.res_mode or "3840" in self.res_mode:
            video_mbps = 68 if is_high_fps else 45
        elif "1440" in self.res_mode:
            video_mbps = 24 if is_high_fps else 16
        elif "1080" in self.res_mode:
            video_mbps = 12 if is_high_fps else 8
        else:
            video_mbps = 5
            
        total_mbps = video_mbps + 0.32

        size_mb = (total_mbps * max_duration) / 8
        mins = int(max_duration // 60)
        secs = int(max_duration % 60)
        return f"Duration: {mins:02}:{secs:02} | Target: {self.res_mode} | Est. Size: ~{size_mb:.1f} MB"

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
