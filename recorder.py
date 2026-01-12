import os
import struct
import time
from PyQt5.QtCore import QObject, pyqtSignal
from voice_recorder import VoiceWorker

class VoiceoverRecorder(QObject):
    recording_started = pyqtSignal()
    recording_finished = pyqtSignal(str)
    level_signal = pyqtSignal(int)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__()
        self.audio_input = None
        self.file = None
        self.current_path = None
        self.is_recording = False

    def start_recording(self, output_path, start_time, track_idx, existing_clips):
        """Goal 7: Prevents overwriting and initializes recording state."""
        if self.is_recording: return
        for clip in existing_clips:
            if clip['track'] == track_idx:
                if abs(clip['start'] - start_time) < 0.1:
                    self.error_occurred.emit("LANE BLOCKED: Cannot record over existing clip.")
                    return
        self.current_path = output_path
        self.worker = VoiceWorker(output_path)
        self.worker.level_signal.connect(self.level_signal.emit)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()
        self.is_recording = True
        self.is_paused = False
        self.recording_started.emit()

    def toggle_pause(self):
        """Standard professional pause/resume logic."""
        if not self.is_recording: return
        self.is_paused = not self.is_paused
        self.worker.toggle_pause(self.is_paused)

    def stop_recording(self):
        if not self.is_recording: return
        self.worker.stop()
        self.is_recording = False

    def _on_worker_finished(self, path):
        self.recording_finished.emit(path)

    def _write_wav_header(self, path, max_retries=5, delay_s=0.1):
        """Fixes the WAV header so FFmpeg can read the PCM data."""
        if not os.path.exists(path):
            return
        for i in range(max_retries):
            try:
                file_size = os.path.getsize(path)
                if file_size < 44: return
                data_size = file_size - 44
                with open(path, 'r+b') as f:
                    f.seek(0)
                    f.write(b'RIFF' + struct.pack('<I', file_size - 8) + b'WAVEfmt ')
                    f.write(struct.pack('<IHHIIHH', 16, 1, 1, 44100, 88200, 2, 16))
                    f.write(b'data' + struct.pack('<I', data_size))
                    f.flush()
                    os.fsync(f.fileno())
                return
            except PermissionError:
                time.sleep(delay_s)
                print(f"WAV header patch failed (retry {i+1}/{max_retries}): File locked. Retrying...")
            except Exception as e:
                print(f"Failed to write WAV header to {path}: {e}")
                return
        print(f"Failed to write WAV header to {path} after {max_retries} retries. File remained locked.")