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

    def get_gpu_encoder(self):
        """Detects the best available hardware encoder."""
        try:
            ffmpeg_bin = BinaryManager.get_executable('ffmpeg')
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            output = subprocess.check_output([ffmpeg_bin, '-encoders'], startupinfo=si, stderr=subprocess.STDOUT).decode()
            if 'h264_nvenc' in output:
                self.logger.info("[RENDER] NVIDIA GPU detected. Using h264_nvenc.")
                return 'h264_nvenc'
            if 'h264_qsv' in output:
                self.logger.info("[RENDER] Intel QuickSync detected. Using h264_qsv.")
                return 'h264_qsv'
            if 'h264_amf' in output:
                self.logger.info("[RENDER] AMD GPU detected. Using h264_amf.")
                return 'h264_amf'
        except Exception as e:
            self.logger.warning(f"[RENDER] HW detection failed: {e}")
        self.logger.warning("[RENDER] No GPU encoder found. Falling back to libx264.")
        return 'libx264'

    def run(self):
        try:
            w, h = (1080, 1920) if "Portrait" in self.res else (1920, 1080)
            if "2560" in self.res: w, h = 2560, 1440
            elif "3840" in self.res: w, h = 3840, 2160
            gen = FilterGraphGenerator(self.clips, w, h, self.vols, self.mutes)
            inputs, f_str, v_map, a_map = gen.build(is_export=True)
            gpu_codec = self.get_gpu_encoder()
            cmd = [BinaryManager.get_executable('ffmpeg'), '-y', '-hide_banner']
            for inp in inputs:
                cmd.extend(['-i', inp])
            cmd.extend(['-filter_complex', f_str])
            cmd.extend(['-map', v_map, '-map', a_map])
            if gpu_codec != 'libx264':
                cmd.extend(['-c:v', gpu_codec, '-pix_fmt', 'yuv420p', '-preset', 'p4', '-rc', 'vbr', '-cq', '23'])
            else:
                cmd.extend(['-c:v', 'libx264', '-preset', 'fast', '-crf', '23'])
            cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
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
