import subprocess
import json
import os
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
            info = {
                'path': self.path,
                'duration': float(data['format'].get('duration', 0)),
                'width': 0,
                'height': 0,
                'has_audio': False,
                'has_video': False
            }
            for s in data['streams']:
                if s['codec_type'] == 'video':
                    info['has_video'] = True
                    info['width'] = int(s.get('width', 0))
                    info['height'] = int(s.get('height', 0))
                elif s['codec_type'] == 'audio':
                    info['has_audio'] = True
            self.result.emit(info)
        except Exception as e:
            self.result.emit({'error': str(e)})

class WaveformWorker(QThread):
    finished = pyqtSignal(str, str)

    def __init__(self, audio_path, uid, assets_dir):
        super().__init__()
        self.path = audio_path
        self.uid = uid
        self.out = os.path.join(assets_dir, f"{uid}_wave.png")

    def run(self):
        if os.path.exists(self.out):
            self.finished.emit(self.uid, self.out)
            return
        cmd = [
            'ffmpeg', '-y', '-i', self.path,
            '-filter_complex', 'showwavespic=s=600x100:colors=cyan',
            '-frames:v', '1',
            self.out
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.finished.emit(self.uid, self.out)
        except:
            pass
