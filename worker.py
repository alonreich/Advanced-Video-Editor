import subprocess
import os
import traceback
import logging
import queue
from PyQt5.QtCore import QThread, pyqtSignal

class ThumbnailWorker(QThread):
    thumbnail_generated = pyqtSignal(str, str, str)

    def __init__(self, project_dir):
        super().__init__()
        self.project_dir = project_dir
        self.queue = queue.Queue()
        self.running = True
        self.logger = logging.getLogger("Advanced_Video_Editor")

    def add_task(self, path, uid, duration):
        self.queue.put({'path': path, 'uid': uid, 'dur': duration})

    def stop(self):
        self.running = False
        self.queue.put(None)

    def run(self):
        while self.running:
            try:
                task = self.queue.get()
                if task is None: 
                    break
                self.process_task(task)
                self.queue.task_done()
            except Exception as e:
                self.logger.error(f"Thumbnail Queue Error: {e}")

    def process_task(self, task):
        uid = task['uid']
        path = task['path']
        dur = task['dur']
        cache_dir = os.path.join(self.project_dir, "cache", "thumbnails")
        os.makedirs(cache_dir, exist_ok=True)
        out_start = os.path.join(cache_dir, f"{uid}_start.jpg")
        out_end = os.path.join(cache_dir, f"{uid}_end.jpg")
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        if not os.path.exists(out_start):
            cmd = [
                'ffmpeg', '-y', '-ss', '0', '-i', path,
                '-vf', 'scale=-2:120', '-vframes', '1', '-q:v', '5', 
                out_start
            ]
            self.run_ffmpeg(cmd, si)
        if not os.path.exists(out_end):
            seek_t = max(0, dur - 0.5)
            cmd = [
                'ffmpeg', '-y', '-ss', str(seek_t), '-i', path,
                '-vf', 'scale=-2:120', '-vframes', '1', '-q:v', '5', 
                out_end
            ]
            self.run_ffmpeg(cmd, si)
        self.thumbnail_generated.emit(uid, out_start, out_end)

    def run_ffmpeg(self, cmd, startup_info):
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                           startupinfo=startup_info, check=True)
        except Exception:
            pass
