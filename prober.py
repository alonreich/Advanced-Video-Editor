import subprocess
import json
import os
import traceback
import logging
from PyQt5.QtCore import QThread, pyqtSignal

class ProbeWorker(QThread):
    result = pyqtSignal(dict)
    
    def __init__(self, path):
        super().__init__()
        self.path = path

    def run(self):
        try:
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                self.path
            ]
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output(cmd, startupinfo=si)
            data = json.loads(output)
            
            # Safe extraction helper to handle "N/A" and missing keys
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
                    # Only update dimensions if we found a video stream with valid size
                    w = get_val(s, 'width', int, 0)
                    h = get_val(s, 'height', int, 0)
                    if w > 0: info['width'] = w
                    if h > 0: info['height'] = h
                elif s.get('codec_type') == 'audio':
                    info['has_audio'] = True
            
            self.result.emit(info)
        except Exception as e:
            logging.getLogger("Advanced_Video_Editor").error(f"Probe Failed:\n{traceback.format_exc()}")
            self.result.emit({'error': str(e)})

import hashlib

class WaveformWorker(QThread):
    finished = pyqtSignal(str, str)

    def __init__(self, audio_path, uid, project_dir):
        super().__init__()
        self.path = audio_path
        self.uid = uid
        
        # Use MD5 hash of the file path for caching. 
        # Same file = Same waveform image. No redundant rendering.
        path_hash = hashlib.md5(audio_path.encode('utf-8')).hexdigest()
        
        cache_dir = os.path.join(project_dir, "cache", "waveforms")
        os.makedirs(cache_dir, exist_ok=True)
        
        # Map hash to filename
        self.out = os.path.join(cache_dir, f"{path_hash}.png")

    def run(self):
        # Cache Hit: Serve immediately
        if os.path.exists(self.out):
            self.finished.emit(self.uid, self.out)
            return

        # Cache Miss: Generate High-Res Waveform (4000px width)
        # Colors: Cyber-Cyan (#00FFFF) to Deep Blue (#0088FF)
        cmd = [
            'ffmpeg', '-y', '-i', self.path,
            '-filter_complex', 'showwavespic=s=4000x240:colors=#00FFFF|#0088FF:split_channels=1',
            '-frames:v', '1',
            self.out
        ]
        try:
            # Creation flags to hide console window on Windows
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, 
                           startupinfo=si, check=True)
            self.finished.emit(self.uid, self.out)
        except Exception:
            logging.getLogger("Advanced_Video_Editor").error(f"Waveform Generation Failed for {self.path}:\n{traceback.format_exc()}")
