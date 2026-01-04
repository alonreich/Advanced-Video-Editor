import subprocess
import json
import os
import traceback
import logging
import shutil
import hashlib
from PyQt5.QtCore import QThread, pyqtSignal

class ProbeWorker(QThread):
    result = pyqtSignal(dict)
    
    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
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
            logger = logging.getLogger("Advanced_Video_Editor")
            log_cmd = ' '.join(f'"{c}"' if ' ' in c else c for c in cmd)
            logger.info(f"[BINARY EXEC] CMD: {log_cmd}")
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(cmd, capture_output=True, text=True, startupinfo=si, check=True, encoding='utf-8')
            output = result.stdout
            logger.info(f"[BINARY SUCCESS] ffprobe executed successfully for: {self.path}")
            data = json.loads(output)
            def get_val(d, key, type_func, default):
                val = d.get(key, default)
                if val == 'N/A' or val is None: return default
                try: return type_func(val)
                except: return default
            fmt = data.get('format', {})
            streams = data.get('streams', [])
            info = {
                'path': self.path,
                'duration': get_val(fmt, 'duration', float, 0.0),
                'bitrate': get_val(fmt, 'bit_rate', int, 0),
                'width': 0,
                'height': 0,
                'has_audio': False,
                'has_video': False
            }
            for s in streams:
                if s.get('codec_type') == 'video':
                    info['has_video'] = True
                    w = get_val(s, 'width', int, 0)
                    h = get_val(s, 'height', int, 0)
                    if w > 0: info['width'] = w
                    if h > 0: info['height'] = h
                elif s.get('codec_type') == 'audio':
                    info['has_audio'] = True
            self.result.emit(info)
        except subprocess.CalledProcessError as e:
            logger = logging.getLogger("Advanced_Video_Editor")
            logger.error(f"[BINARY FAILURE] Probe failed for {self.path}. Exit code: {e.returncode}")
            logger.error(f"  Command: {' '.join(e.cmd)}")
            logger.error(f"  Stdout: {e.stdout}")
            logger.error(f"  Stderr: {e.stderr}")
            self.result.emit({'error': str(e)})
        except Exception as e:
            logging.getLogger("Advanced_Video_Editor").error(f"Probe Failed:\n{traceback.format_exc()}")
            self.result.emit({'error': str(e)})

class WaveformWorker(QThread):
    finished = pyqtSignal(str, str)

    def __init__(self, audio_path, uid, project_dir):
        super().__init__()
        self.path = audio_path
        self.uid = uid
        path_hash = hashlib.md5(audio_path.encode('utf-8')).hexdigest()
        cache_dir = os.path.join(project_dir, "cache", "waveforms")
        os.makedirs(cache_dir, exist_ok=True)
        self.out = os.path.join(cache_dir, f"{path_hash}.png")

    def run(self):
        if os.path.exists(self.out):
            self.finished.emit(self.uid, self.out)
            return
        ffmpeg_bin = shutil.which('ffmpeg') or 'ffmpeg'
        cmd = [
            ffmpeg_bin, '-y', '-i', self.path,
            '-filter_complex', 'aformat=channel_layouts=mono,compand,showwavespic=s=4000x240:colors=#00FFFF|#0088FF:split_channels=1:scale=sqrt',
            '-frames:v', '1',
            self.out
        ]
        try:
            logger = logging.getLogger("Advanced_Video_Editor")
            logger.info(f"[BINARY EXEC] CMD: {' '.join(cmd)}")
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            subprocess.run(cmd, capture_output=True, text=True, 
                           startupinfo=si, check=True, encoding='utf-8')
            logger.info(f"[BINARY SUCCESS] Waveform generated: {self.out}")
            self.finished.emit(self.uid, self.out)
        except subprocess.CalledProcessError as e:
            logger = logging.getLogger("Advanced_Video_Editor")
            logger.error(f"[BINARY FAILURE] Waveform generation failed for {self.path}. Exit code: {e.returncode}")
            logger.error(f"  Command: {' '.join(e.cmd)}")
            logger.error(f"  Stdout: {e.stdout}")
            logger.error(f"  Stderr: {e.stderr}")
        except Exception as e:
            logging.getLogger("Advanced_Video_Editor").error(f"Waveform Generation Failed for {self.path}:\n{traceback.format_exc()}")