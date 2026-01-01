import subprocess
import os
import logging
import platform
from PyQt5.QtCore import QThread, pyqtSignal

class FFmpegBuilder:
    def __init__(self, all_clips, output_path, resolution_mode="Landscape 1080p"):
        self.all_clips = all_clips
        self.out = output_path
        self.mode = resolution_mode
# ... existing code ...
    def build_cmd(self, encoder="libx264"):
        inputs = []
        filter_complex = []
        file_map = {}
        input_args = []
        for clip in self.all_clips:
            if clip['path'] not in file_map:
                file_map[clip['path']] = len(inputs)
                inputs.append(clip['path'])
                input_args.extend(['-i', clip['path']])
        total_dur = max([c['start'] + c['dur'] for c in self.all_clips]) if self.all_clips else 10
        filter_complex.append(f"color=c=black:s={self.width}x{self.height}:d={total_dur:.3f}[base]")
        last_layer = "[base]"
        self.all_clips.sort(key=lambda x: (x['track'], x['start']))
        for i, clip in enumerate(self.all_clips):
            inp_idx = file_map[clip['path']]
# ... existing code ...
            f_chain = [
                f"[{inp_idx}:v]trim=start={clip['source_in']}:duration={clip['dur'] * clip['speed']}",
                "setpts=PTS-STARTPTS",
                f"setpts=PTS*{pts_speed}"
            ]
            
            # Crop
            crop = clip.get('crop_x2', 1.0) - clip.get('crop_x1', 0.0) < 1.0 or clip.get('crop_y2', 1.0) - clip.get('crop_y1', 0.0) < 1.0
            if crop:
                f_chain.append(f"crop=iw*({clip['crop_x2']}-{clip['crop_x1']}):ih*({clip['crop_y2']}-{clip['crop_y1']}):iw*{clip['crop_x1']}:ih*{clip['crop_y1']}")

            # Scale
            f_chain.append(f"scale={self.width}*{clip['scale_x']}:{self.height}*{clip['scale_y']}")

            f_chain.append(f"setsar=1[{lbl}_pre]")
            start_t = clip['start']
            end_t = start_t + clip['dur']
            next_layer = f"[bg{i}]"
            
            # Position
            x_pos = (self.width - self.width * clip['scale_x']) / 2 + self.width * clip['pos_x']
            y_pos = (self.height - self.height * clip['scale_y']) / 2 - self.height * clip['pos_y']

            overlay_filter = (
                f"{last_layer}[{lbl}_pre]overlay="
                f"x={x_pos}:y={y_pos}:"
                f"enable='between(t,{start_t},{end_t})':"
                f"eof_action=pass[{next_layer}]"
            )
            filter_complex.append(",".join(f_chain))
            filter_complex.append(overlay_filter)
            last_layer = next_layer
        cmd = ['ffmpeg', '-y'] + input_args
        cmd.extend(['-filter_complex', ";".join(filter_complex)])
        cmd.extend(['-map', last_layer])
        if "nvenc" in encoder:
            cmd.extend(['-c:v', encoder, '-preset', 'p4', '-rc', 'vbr'])
        elif "amf" in encoder:
             cmd.extend(['-c:v', encoder, '-usage', 'transcoding'])
        else:
            cmd.extend(['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'])
        cmd.append(self.out)
        return cmd

class RenderWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, builder, parent=None):
        super().__init__(parent)
        self.builder = builder
        self.logger = logging.getLogger("ProEditor")

    def detect_hw(self):
        check = lambda enc: subprocess.call(['ffmpeg', '-v', 'quiet', '-f', 'lavfi', '-i', 'color', '-c:v', enc, '-t', '1', '-f', 'null', '-']) == 0
        if check('h264_nvenc'): return 'h264_nvenc'
        if check('h264_amf'): return 'h264_amf'
        if check('h264_qsv'): return 'h264_qsv'
        return 'libx264'

    def run(self):
        try:
            enc = self.detect_hw()
            self.logger.info(f"Selected Encoder: {enc}")
            cmd = self.builder.build_cmd(enc)
            self.logger.info(f"CMD: {' '.join(cmd)}")
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, startupinfo=si)
            for line in proc.stdout:
                if "time=" in line:
                    self.progress.emit(50) 
            if proc.wait() == 0:
                self.finished.emit()
            else:
                self.error.emit("Render exited with error code.")
        except Exception as e:
            self.error.emit(str(e))
