import traceback
import logging
import subprocess
import shutil
from PyQt5.QtCore import QThread, pyqtSignal, QProcess
from binary_manager import BinaryManager
from ffmpeg_generator import FilterGraphGenerator

class RenderWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, clips, output_path, resolution_mode, track_vols, track_mutes):
        super().__init__()
        self.clips = clips
        self.out = output_path
        self.res = resolution_mode
        self.vols = track_vols
        self.mutes = track_mutes
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.process = None

    def run(self):
        try:
            w, h = (1080, 1920) if "Portrait" in self.res else (1920, 1080)
            if "2560" in self.res: w, h = 2560, 1440
            elif "3840" in self.res: w, h = 3840, 2160
            gen = FilterGraphGenerator(self.clips, w, h, self.vols, self.mutes)
            inputs, f_str, v_map, a_map = gen.build(is_export=True)
            gpu_codec = BinaryManager.get_best_encoder(self.logger)
            cmd = [BinaryManager.get_executable('ffmpeg'), '-y', '-hide_banner']
            for inp in inputs:
                cmd.extend(['-i', inp])
            cmd.extend(['-filter_complex', f_str])
            cmd.extend(['-map', v_map, '-map', a_map])
            if gpu_codec != 'libx264':
                is_modern = gpu_codec in ['av1_nvenc', 'hevc_nvenc']
                preset = 'p7' if is_modern else 'p4'
                cq_value = '18' if is_modern else '21'
                cmd.extend(['-c:v', gpu_codec, '-pix_fmt', 'p010le' if is_modern else 'yuv420p'])
                cmd.extend(['-preset', preset, '-tier', 'high', '-rc', 'vbr', '-cq', cq_value, '-b:v', '0', '-rc-lookahead', '32'])
                if gpu_codec == 'hevc_nvenc':
                    cmd.extend(['-spatial-aq', '1', '-temporal-aq', '1'])
            else:
                cmd.extend(['-c:v', 'libx264', '-preset', 'medium', '-crf', '18'])
            cmd.extend(['-c:a', 'aac', '-b:a', '320k'])
            cmd.append(self.out)
            self.logger.info(f"Render CMD: {' '.join(cmd)}")
            self.process = QProcess()
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.read_log)
            self.process.start(cmd[0], cmd[1:])
            self.process.waitForFinished(-1)
            if self.process.exitCode() == 0:
                self.finished.emit()
            else:
                self.error.emit(f"FFmpeg Exit Code: {self.process.exitCode()}")
        except Exception as e:
            self.error.emit(str(e))

    def read_log(self):
        line = self.process.readAllStandardOutput().data().decode(errors='ignore').strip()
        if "time=" in line:
            self.logger.debug(line)