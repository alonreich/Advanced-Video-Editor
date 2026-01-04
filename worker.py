import subprocess
import os
import traceback
import logging
import queue
import shutil
from PyQt5.QtCore import QThread, pyqtSignal

class ThumbnailWorker(QThread):
    thumbnail_generated = pyqtSignal(str, str, str)

    def __init__(self, project_dir):
        super().__init__()
        self.project_dir = project_dir
        self.queue = queue.Queue()
        self.running = True
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.hwaccel_args = []
        self.scale_filter = 'scale'
        self.checked_hwaccel = False

    def add_task(self, path, uid, duration):
        self.queue.put({'path': path, 'uid': uid, 'dur': duration})

    def stop(self):
        self.running = False
        self.queue.put(None)

    def get_hwaccel_args(self):
        """Goal 14: Dynamic GPU hijacking for lightning-fast previews."""
        if self.checked_hwaccel:
            return self.hwaccel_args, self.scale_filter
        self.checked_hwaccel = True
        try:
            from render_worker import RenderWorker
            dummy_worker = RenderWorker([], "", "", {}, {})
            gpu_codec = dummy_worker.get_gpu_encoder()
            if gpu_codec == 'h264_nvenc':
                self.hwaccel_args = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
                self.scale_filter = 'scale_cuda'
            elif gpu_codec == 'h264_qsv':
                self.hwaccel_args = ['-hwaccel', 'qsv']
                self.scale_filter = 'vpp_qsv'
            else:
                self.hwaccel_args, self.scale_filter = [], 'scale'
            self.logger.info(f"[THUMB-GPU] Hijacked GPU for thumbnails. Using: {gpu_codec}")
        except Exception as e:
            self.logger.error(f"[THUMB-GPU] GPU Hijack failed, falling back: {e}")
            self.hwaccel_args, self.scale_filter = [], 'scale'
        return self.hwaccel_args, self.scale_filter

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
        
        import hashlib
        h = hashlib.md5(f"{path}_{dur}".encode()).hexdigest()
        cache_dir = os.path.join(self.project_dir, "cache", "thumbnails")
        os.makedirs(cache_dir, exist_ok=True)
        out_start = os.path.join(cache_dir, f"{h}_start.jpg")
        out_end = os.path.join(cache_dir, f"{h}_end.jpg")
        self._generate_thumb(path, out_start, 0)
        self._generate_thumb(path, out_end, max(0, dur - 0.5))
        self.thumbnail_generated.emit(uid, out_start, out_end)

    def _generate_thumb(self, in_path, out_path, seek_time):
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        hw_args, s_filter = self.get_hwaccel_args()
        if hw_args:
            cmd = ['ffmpeg', '-hide_banner', *hw_args, '-threads', '1', '-ss', str(seek_time), '-i', in_path,
                   '-vf', f'{s_filter}=-2:120,hwdownload,format=nv12', '-vframes', '1', '-y', out_path]
            if self.run_ffmpeg(cmd, si): return
        self.logger.warning(f"[THUMB] Falling back to software for {os.path.basename(in_path)}")
        cmd = ['ffmpeg', '-hide_banner', '-ss', str(seek_time), '-i', in_path,
               '-vf', 'scale=-2:120', '-vframes', '1', '-y', out_path]
        self.run_ffmpeg(cmd, si)

    def run_ffmpeg(self, cmd, startup_info):
        try:
            bin_full = shutil.which(cmd[0]) or cmd[0]
            cmd[0] = bin_full
            self.logger.info(f"[BINARY EXEC] CMD: {' '.join(cmd)}")
            subprocess.run(cmd, capture_output=True, text=True, 
                           startupinfo=startup_info, check=True, encoding='utf-8')
            self.logger.info("[BINARY SUCCESS] Thumbnail ffmpeg command finished.")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"[BINARY FAILURE] Thumbnail ffmpeg command failed. Exit code: {e.returncode}")
            self.logger.error(f"  Command: {' '.join(e.cmd)}")
            self.logger.error(f"  Stdout: {e.stdout}")
            self.logger.error(f"  Stderr: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"[BINARY FAILURE] Thumbnail ffmpeg command failed: {e}")
            return False
