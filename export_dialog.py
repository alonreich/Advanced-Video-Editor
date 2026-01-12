from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTextEdit, QProgressBar, QPushButton, QFileDialog
from PyQt5.QtCore import Qt
from render_worker import RenderWorker
import constants

class ExportDialog(QDialog):

    def __init__(self, timeline_state, track_vols, track_mutes, res_mode, audio_analysis_results, parent=None):
        super().__init__(parent)
        self.state = timeline_state
        self.vols = track_vols
        self.mutes = track_mutes
        self.res_mode = res_mode
        self.audio_analysis_results = audio_analysis_results
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Export Video")
        self.resize(500, 400)
        l = QVBoxLayout(self)
        self.lbl_estimate = QLabel()
        self.lbl_estimate.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {constants.COLOR_PRIMARY.name()}; padding: 10px; border: 1px solid #333; border-radius: 4px;")
        l.addWidget(self.lbl_estimate)
        self.update_ui_estimate()
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setStyleSheet("background-color: #000; color: #0F0; font-family: 'Consolas';")
        l.addWidget(self.console)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        l.addWidget(self.bar)
        self.btn_start = QPushButton("Start Export")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.setToolTip("Start the video export process")
        self.btn_start.clicked.connect(self.start_export)
        l.addWidget(self.btn_start)

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
        self.btn_start.setEnabled(False)
        self.btn_start.setText("Rendering...")
        self.bar.setValue(0)
        self.worker = RenderWorker(self.state, out, self.res_mode, self.vols, self.mutes, self.audio_analysis_results)
        self.worker.progress.connect(self.bar.setValue)
        
        def on_finished():
            self.log("Export Successful!")
            self.btn_start.setEnabled(True)
            self.btn_start.setText("Start Export")
            
        def on_error(e):
            self.log(f"CRITICAL ERROR: {e}")
            self.btn_start.setEnabled(True)
            self.btn_start.setText("Retry Export")
        self.worker.finished.connect(on_finished)
        self.worker.error.connect(on_error)
        self.worker.start()
        self.log(f"Export initiated: {out}")

    def update_ui_estimate(self):
        """Goal 21: Live bitrate math with Discord safety threshold."""
        text = self.calculate_estimate()
        self.lbl_estimate.setText(text)
        try:
            size_mb = float(text.split("~")[1].split()[0])
            if size_mb > 500:
                self.lbl_estimate.setStyleSheet("font-size: 13px; font-weight: bold; color: #E74C3C; padding: 10px; border: 1px solid #E74C3C;")
            else:
                self.lbl_estimate.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {constants.COLOR_PRIMARY.name()}; padding: 10px; border: 1px solid #333;")
        except: pass