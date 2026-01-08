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
        """Goal 14: Forced GPU hijacking for 40-Series optimization."""
        if self.checked_hwaccel:
            return self.hwaccel_args, self.scale_filter
        from binary_manager import BinaryManager
        BinaryManager.ensure_env()
        gpu_codec = BinaryManager.get_best_encoder(self.logger)
        self.checked_hwaccel = True
        if gpu_codec in ['h264_nvenc', 'hevc_nvenc', 'av1_nvenc']:
            self.hwaccel_args = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
            self.scale_filter = 'scale_cuda'
            self.logger.info(f"[THUMB-GPU] 40-Series NVIDIA GPU detected. Using scale_cuda.")
        elif gpu_codec == 'h264_qsv':
            self.hwaccel_args = ['-hwaccel', 'qsv']
            self.scale_filter = 'vpp_qsv'
            self.logger.info(f"[THUMB-GPU] Intel QSV detected. Using vpp_qsv.")
        else:
            self.hwaccel_args, self.scale_filter = [], 'scale'
            self.logger.info(f"[THUMB-CPU] No compatible GPU found for thumbnails. Falling back to CPU.")
        return self.hwaccel_args, self.scale_filter

    def run(self):
        while self.running:
            try:
                try:
                    task = self.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
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
        """Goal 14: Hardware-accelerated thumbnail generation."""
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        hw_args, s_filter = self.get_hwaccel_args()
        cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error']
        if hw_args and 'cuda' in hw_args:
            vf_chain = f"{s_filter}=-2:120,hwdownload,format=nv12"
            cmd += hw_args + ['-ss', str(seek_time), '-i', in_path, '-vf', vf_chain]
        elif hw_args and 'qsv' in hw_args:
            vf_chain = f"vpp_qsv=w=-2:h=120"
            device_args = ['-init_hw_device', 'qsv=qsv', '-filter_hw_device', 'qsv']
            cmd += hw_args + device_args + ['-ss', str(seek_time), '-i', in_path, '-vf', vf_chain]
        else:
            cmd += ['-ss', str(seek_time), '-i', in_path, '-vf', "scale=-2:120"]
        cmd += ['-vframes', '1', '-y', out_path]
        success, err_msg = self.run_ffmpeg(cmd, si)
        if not success:
            self.logger.warning(f"[THUMB] GPU failed for {os.path.basename(in_path)}, retrying on CPU...")
            fallback_cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', str(seek_time), '-i', in_path, '-vf', 'scale=-1:120', '-vframes', '1', '-y', out_path]
            success, err_msg = self.run_ffmpeg(fallback_cmd, si)
            if not success:
                self.logger.error(f"[THUMB] FFmpeg total failure for {os.path.basename(in_path)}: {err_msg}")

    def run_ffmpeg(self, cmd, startup_info):
        try:
            bin_full = shutil.which(cmd[0]) or cmd[0]
            cmd[0] = bin_full
            res = subprocess.run(cmd, capture_output=True, text=True, startupinfo=startup_info, check=True, encoding='utf-8')
            return True, ""
        except subprocess.CalledProcessError as e:
            return False, e.stderr
        except Exception as e:
            return False, str(e)

class ProxyWorker(QThread):
    proxy_finished = pyqtSignal(str, str)
    progress = pyqtSignal(str, int)

    def __init__(self, project_dir):
        super().__init__()
        self.project_dir = project_dir
        self.queue = queue.Queue()
        self.running = True
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.hwaccel_args = []
        self.codec = 'libx264'
        self.checked_hwaccel = False

    def add_task(self, path, uid):
        self.queue.put({'path': path, 'uid': uid})

    def stop(self):
        self.running = False
        self.queue.put(None)

    def get_encoding_settings(self):
        """Determines best encoder for fast, low-quality proxy generation."""
        if self.checked_hwaccel:
            return self.hwaccel_args, self.codec
        self.checked_hwaccel = True
        try:
            from binary_manager import BinaryManager
            gpu_codec = BinaryManager.get_best_encoder()
            if gpu_codec in ['h264_nvenc', 'hevc_nvenc', 'av1_nvenc']:
                self.logger.info("[PROXY-GPU] 40-Series Detected. Using HEVC_NVENC for high-speed proxies.")
                self.hwaccel_args = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
                self.codec = 'hevc_nvenc' 
            elif gpu_codec == 'h264_qsv':
                self.logger.info("[PROXY-GPU] Using Intel QuickSync.")
                self.hwaccel_args = ['-hwaccel', 'qsv']
                self.codec = 'h264_qsv'
            elif gpu_codec == 'h264_amf':
                self.logger.info("[PROXY-GPU] Using AMD AMF.")
                self.hwaccel_args = ['-hwaccel', 'dxva2']
                self.codec = 'h264_amf'
            else:
                self.hwaccel_args = []
                self.codec = 'libx264'
        except Exception:
            self.hwaccel_args = []
            self.codec = 'libx264'
        return self.hwaccel_args, self.codec

    def run(self):
        while self.running:
            try:
                task = self.queue.get(timeout=0.5)
                if task is None:
                    break
                self.process_task(task)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Proxy Queue Error: {e}")

    def process_task(self, task):
        uid = task['uid']
        path = task['path']
        import hashlib
        h = hashlib.md5(path.encode()).hexdigest()
        cache_dir = os.path.join(self.project_dir, "cache", "proxies")
        os.makedirs(cache_dir, exist_ok=True)
        out_path = os.path.join(cache_dir, f"{h}_proxy.mp4")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
            self.logger.info(f"[PROXY] Found cached proxy for {uid}")
            self.proxy_finished.emit(uid, out_path)
            return
        hw_args, codec = self.get_encoding_settings()
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error']
        cmd.extend(hw_args)
        cmd.extend(['-i', path])
        if 'cuda' in hw_args:
            cmd.extend(['-vf', 'scale_cuda=-2:540'])
        elif 'qsv' in hw_args:
            cmd.extend(['-vf', 'vpp_qsv=h=540'])
        else:
            cmd.extend(['-vf', 'scale=-2:540'])
        cmd.extend(['-c:v', codec])
        if 'nvenc' in codec:
            cmd.extend(['-preset', 'p1', '-cq', '30', '-b:v', '0'])
        elif codec == 'libx264':
            cmd.extend(['-preset', 'ultrafast', '-crf', '28'])
        cmd.extend(['-c:a', 'aac', '-b:a', '96k', '-ac', '2'])
        cmd.append(out_path)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        try:
            self.logger.info(f"[PROXY] Generating: {out_path}")
            bin_full = shutil.which(cmd[0]) or cmd[0]
            cmd[0] = bin_full
            subprocess.run(cmd, startupinfo=si, check=True)
            self.proxy_finished.emit(uid, out_path)
        except subprocess.CalledProcessError as e:
            self.logger.error(f"[PROXY] Generation failed: {e}")