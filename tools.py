import subprocess
import os
import json
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QImage, QPainter, QColor
class WaveformWorker(QThread):
    finished = pyqtSignal(str, object) 
    def __init__(self, file_path, uid):
        super().__init__()
        self.path = file_path
        self.uid = uid
    def run(self):
        self.finished.emit(self.uid, None)
class ProbeWorker(QThread):
    result = pyqtSignal(dict)
    def __init__(self, path):
        super().__init__()
        self.path = path
    def run(self):
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height', '-of', 'json', self.path]
            out = subprocess.check_output(cmd)
            data = json.loads(out)
            dur = float(data['format']['duration'])
            w = h = 0
            if 'streams' in data:
                for s in data['streams']:
                    if 'width' in s: w, h = s['width'], s['height']
            self.result.emit({'path': self.path, 'duration': dur, 'width': w, 'height': h})
        except Exception as e:
            self.result.emit({'error': str(e)})