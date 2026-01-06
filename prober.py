import subprocess
import json
import os
import traceback
import logging
import shutil
import hashlib
from PyQt5.QtCore import QRunnable, QObject, pyqtSignal, QThread
class ProbeSignals(QObject):
    result = pyqtSignal(dict)

class ProbeWorker(QRunnable):
    def __init__(self, path, track_id=0, insert_time=0.0):
        super().__init__()
        self.path = path
        self.track_id = track_id
        self.insert_time = insert_time
        self.signals = ProbeSignals()
        self.setAutoDelete(True)

    def _get_cache_path(self):
        """Generates a unique cache filename based on file path, size, and mtime."""
        try:
            stat = os.stat(self.path)
            fingerprint = f"{self.path}_{stat.st_mtime}_{stat.st_size}"
            h = hashlib.md5(fingerprint.encode('utf-8')).hexdigest()
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, "projects", "cache", "probes")
            os.makedirs(cache_dir, exist_ok=True)
            return os.path.join(cache_dir, f"{h}.json")
        except Exception:
            return None

    def run(self):
        cache_file = self._get_cache_path()
        logger = logging.getLogger("Advanced_Video_Editor")
        info = {
            'path': self.path,
            'track_id': self.track_id,
            'insert_time': self.insert_time
        }
        if cache_file and os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    info.update(cached_data)
                self.signals.result.emit(info)
                return
            except Exception:
                logger.warning(f"[PROBE-CACHE] Corrupt cache file, regenerating: {cache_file}")
        try:
            ffprobe_bin = shutil.which('ffprobe') or 'ffprobe'
            cmd = [
                ffprobe_bin,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                self.path
            ]
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=si, check=True, encoding='utf-8')
            output = result.stdout
            data = json.loads(output)
            
            def get_val(d, key, type_func, default):
                val = d.get(key, default)
                if val == 'N/A' or val is None: return default
                try: return type_func(val)
                except: return default
            fmt = data.get('format', {})
            streams = data.get('streams', [])
            phys_data = {
                'duration': get_val(fmt, 'duration', float, 0.0),
                'bitrate': get_val(fmt, 'bit_rate', int, 0),
                'width': 0,
                'height': 0,
                'has_audio': False,
                'has_video': False
            }
            for s in streams:
                if s.get('codec_type') == 'video':
                    phys_data['has_video'] = True
                    w = get_val(s, 'width', int, 0)
                    h = get_val(s, 'height', int, 0)
                    if w > 0: phys_data['width'] = w
                    if h > 0: phys_data['height'] = h
                elif s.get('codec_type') == 'audio':
                    phys_data['has_audio'] = True
            if cache_file:
                try:
                    with open(cache_file, 'w') as f:
                        json.dump(phys_data, f)
                except Exception as e:
                    logger.warning(f"[PROBE-CACHE] Failed to write cache: {e}")
            info.update(phys_data)
            self.signals.result.emit(info)
        except subprocess.CalledProcessError as e:
            logger.error(f"[BINARY FAILURE] Probe failed for {self.path}. Exit code: {e.returncode}")
            info['error'] = str(e)
            self.signals.result.emit(info)
        except Exception as e:
            logger.error(f"Probe Failed:\n{traceback.format_exc()}")
            info['error'] = str(e)
            self.signals.result.emit(info)
import queue

class WaveformWorker(QThread):
    finished = pyqtSignal(str, str)

    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = base_dir
        self.queue = queue.Queue()
        self.running = True
        self.logger = logging.getLogger("Advanced_Video_Editor")

    def add_task(self, audio_path, uid):
        self.queue.put((audio_path, uid))

    def stop(self):
        self.running = False
        self.queue.put(None)

    def run(self):
        while self.running:
            try:
                task = self.queue.get()
                if task is None: break
                path, uid = task
                try:
                    stat = os.stat(path)
                    fingerprint = f"{path}_{stat.st_mtime}_{stat.st_size}"
                except FileNotFoundError:
                    fingerprint = path 
                path_hash = hashlib.md5(fingerprint.encode('utf-8')).hexdigest()
                cache_dir = os.path.join(self.base_dir, "cache", "waveforms")
                os.makedirs(cache_dir, exist_ok=True)
                out = os.path.join(cache_dir, f"{path_hash}.png")
                if os.path.exists(out) and os.path.getsize(out) > 0:
                    self.finished.emit(uid, out)
                    self.queue.task_done()
                    continue
                ffmpeg_bin = shutil.which('ffmpeg') or 'ffmpeg'
                cmd = [
                    ffmpeg_bin, '-y', '-i', path,
                    '-filter_complex', 'aformat=channel_layouts=mono,compand,showwavespic=s=4000x240:colors=#00FFFF|#0088FF:split_channels=1:scale=sqrt',
                    '-frames:v', '1', out
                ]
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                subprocess.run(cmd, capture_output=True, text=True, startupinfo=si, check=True, encoding='utf-8')
                self.finished.emit(uid, out)
                self.queue.task_done()
            except Exception as e:
                self.logger.error(f"[WAVEFORM] Generation failed: {e}")