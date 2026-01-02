import subprocess
import os
import logging
import platform
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QThread, pyqtSignal

class FFmpegBuilder:
    def __init__(self, all_clips, output_path, resolution_mode="Landscape 1080p", 
                 start_time=0.0, duration=None, proxy=False):
        self.all_clips = all_clips
        self.out = output_path
        self.mode = resolution_mode
        self.start_time = start_time
        self.duration = duration
        self.width = 1920
        self.height = 1080
        if "Portrait" in resolution_mode:
            self.width, self.height = 1080, 1920
        elif "2560" in resolution_mode:
            self.width, self.height = 2560, 1440
        elif "3840" in resolution_mode:
            self.width, self.height = 3840, 2160
        
        # Proxy Mode: Slash resolution by 50% for speed
        if proxy:
            self.width //= 2
            self.height //= 2

    def build_cmd(self, encoder="libx264"):
        # Helper for safe numeric extraction (Handles 'N/A' from ffprobe)
        def get_val(c, key, default=0):
            val = c.get(key, default)
            if val in ['N/A', None]: return default
            try: return int(val)
            except: return default

        inputs = []
        filter_complex = []
        file_map = {}
        input_args = []
        render_end = self.start_time + (self.duration if self.duration else 99999)
        active_clips = [c for c in self.all_clips if (c['start'] < render_end) and (c['start'] + c['dur'] > self.start_time)]
        for clip in active_clips:
            if clip['path'] not in file_map:
                file_map[clip['path']] = len(inputs)
                inputs.append(clip['path'])
                input_args.extend(['-i', clip['path']])
        total_dur = max([c['start'] + c['dur'] for c in active_clips], default=10)
        filter_complex.append(f"color=c=black:s={self.width}x{self.height}:d={total_dur:.3f}[base_v]")
        last_layer_v = "[base_v]"
        
        # Use safe get_val for width check
        video_clips = sorted([c for c in active_clips if get_val(c, 'width') > 0], key=lambda x: (-x['track'], x['start']))
        
        for i, clip in enumerate(video_clips):
            inp_idx = file_map[clip['path']]
            lbl = f"v{i}"
            pts_speed = 1.0 / clip['speed']
            f_chain = [
                f"[{inp_idx}:v]trim=start={clip['source_in']}:duration={clip['dur'] * clip['speed']}",
                "setpts=PTS-STARTPTS",
                f"setpts=PTS*{pts_speed}"
            ]
            if clip.get('fade_in', 0) > 0:
                f_chain.append(f"fade=t=in:st=0:d={clip['fade_in']}")
            if clip.get('fade_out', 0) > 0:
                out_start = (clip['dur'] - clip['fade_out'])
                f_chain.append(f"fade=t=out:st={out_start}:d={clip['fade_out']}")
            crop_w = clip.get('crop_x2', 1.0) - clip.get('crop_x1', 0.0)
            crop_h = clip.get('crop_y2', 1.0) - clip.get('crop_y1', 0.0)
            # Check for < 0.99 to handle slight floating point inaccuracies
            if crop_w < 0.99 or crop_h < 0.99:
                 # Force even dimensions (divisible by 2) to prevent encoder crashes
                 f_chain.append(f"crop='trunc(iw*{crop_w}/2)*2:trunc(ih*{crop_h}/2)*2:trunc(iw*{clip['crop_x1']}/2)*2:trunc(ih*{clip['crop_y1']}/2)*2'")
            f_chain.append(f"scale={self.width}*{clip['scale_x']}:{self.height}*{clip['scale_y']}")
            f_chain.append(f"setsar=1[{lbl}_pre]")
            start_t = clip['start']
            end_t = start_t + clip['dur']
            next_layer = f"[bg{i}]"
            x_pos = (self.width - self.width * clip['scale_x']) / 2 + self.width * clip['pos_x']
            y_pos = (self.height - self.height * clip['scale_y']) / 2 - self.height * clip['pos_y']
            overlay_filter = (
                f"{last_layer_v}[{lbl}_pre]overlay="
                f"x={x_pos}:y={y_pos}:"
                f"enable='between(t,{start_t},{end_t})':"
                f"eof_action=pass{next_layer}"
            )
            filter_complex.append(",".join(f_chain))
            filter_complex.append(overlay_filter)
            last_layer_v = next_layer
        
        # Use safe get_val for bitrate check
        audio_clips = sorted([c for c in active_clips if get_val(c, 'bitrate') > 0], key=lambda x: (x['track'], x['start']))
        
        audio_outputs = []
        for i, clip in enumerate(audio_clips):
            inp_idx = file_map[clip['path']]
            lbl = f"a{i}"
            pts_speed = 1.0 / clip['speed']
            a_chain = [
                f"[{inp_idx}:a]atrim=start={clip['source_in']}:duration={clip['dur'] * clip['speed']}",
                "asetpts=PTS-STARTPTS",
                f"atempo={clip['speed']}"
            ]
            if clip.get('fade_in', 0) > 0:
                a_chain.append(f"afade=t=in:st=0:d={clip['fade_in']}")
            if clip.get('fade_out', 0) > 0:
                out_start = (clip['dur'] - clip['fade_out'])
                a_chain.append(f"afade=t=out:st={out_start}:d={clip['fade_out']}")
            start_t = clip['start']
            end_t = start_t + clip['dur']
            my_track = clip['track']
            occlusions = []
            for other in audio_clips:
                if other['track'] > my_track:
                    o_start = other['start']
                    o_end = o_start + other['dur']
                    if max(start_t, o_start) < min(end_t, o_end):
                        pass
            a_chain.append(f"adelay={int(start_t*1000)}|{int(start_t*1000)}")
            
            # NO MAGIC DUCKING. Use the user's explicit volume setting.
            # Convert 0-200 range to 0.0-2.0 multiplier
            user_vol = clip.get('volume', 100.0) / 100.0
            
            # Handle Mute (if implemented later, usually volume=0)
            if user_vol < 0.01: user_vol = 0.0
            
            a_chain.append(f"volume={user_vol}[{lbl}_out]")
            filter_complex.append(",".join(a_chain))
            audio_outputs.append(f"[{lbl}_out]")
        if audio_outputs:
            filter_complex.append(f"{''.join(audio_outputs)}amix=inputs={len(audio_outputs)}:dropout_transition=0[out_a]")
        cmd = ['ffmpeg', '-y'] + input_args
        cmd.extend(['-filter_complex', ";".join(filter_complex)])
        cmd.extend(['-map', last_layer_v])
        if audio_outputs:
            cmd.extend(['-map', '[out_a]'])
        if self.duration:
            cmd.extend(['-ss', str(self.start_time), '-t', str(self.duration)])
            cmd.extend(['-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '28'])
            if audio_outputs: cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
        else:
            if "nvenc" in encoder:
                cmd.extend(['-c:v', encoder, '-preset', 'p4', '-rc', 'vbr'])
            elif "amf" in encoder:
                 cmd.extend(['-c:v', encoder, '-usage', 'transcoding'])
            else:
                cmd.extend(['-c:v', 'libx264', '-preset', 'medium', '-crf', '23'])
            if audio_outputs: cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
        cmd.append(self.out)
        return cmd

class RenderWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, builder, parent=None):
        super().__init__(parent)
        self.builder = builder
        self.logger = logging.getLogger("Advanced_Video_Editor")

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
            log_lines = []
            for line in proc.stdout:
                log_lines.append(line)
                if "time=" in line:
                    self.progress.emit(50) 
            if proc.wait() == 0:
                self.finished.emit()
            else:
                full_log = "".join(log_lines)
                self.logger.error(f"FFmpeg Failure Dump:\n{full_log}")
                self.error.emit("Render exited with error code. Check logs for FFmpeg dump.")
        except Exception as e:
            err_trace = traceback.format_exc()
            self.logger.error(f"Render Error:\n{err_trace}")
            self.error.emit(f"{str(e)}\nSee logs for details.")
