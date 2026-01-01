import subprocess
import os
from PyQt5.QtCore import QThread, pyqtSignal

class ThumbnailWorker(QThread):
    finished = pyqtSignal(str, str, str)

    def __init__(self, video_path, uid, project_dir):
        super().__init__()
        self.path = video_path
        self.uid = uid
        cache_dir = os.path.join(project_dir, "cache", "thumbnails")
        os.makedirs(cache_dir, exist_ok=True)
        self.out_start = os.path.join(cache_dir, f"{uid}_start.png")
        self.out_end = os.path.join(cache_dir, f"{uid}_end.png")

    def run(self):
        if not os.path.exists(self.out_start):
            cmd_start = [
                'ffmpeg', '-y', '-i', self.path,
                '-vframes', '1',
                self.out_start
            ]
            try:
                subprocess.run(cmd_start, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error generating start thumbnail: {e}")
                self.out_start = None

        if not os.path.exists(self.out_end):
            cmd_end = [
                'ffmpeg', '-y', '-sseof', '-1', '-i', self.path,
                '-vframes', '1',
                self.out_end
            ]
            try:
                subprocess.run(cmd_end, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error generating end thumbnail: {e}")
                self.out_end = None
        
        self.finished.emit(self.uid, self.out_start, self.out_end)
