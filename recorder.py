import os
import struct
import time
from PyQt5.QtCore import QObject, pyqtSignal, QFile, QIODevice
from PyQt5.QtMultimedia import QAudioInput, QAudioFormat, QAudioDeviceInfo

class VoiceoverRecorder(QObject):
    recording_started = pyqtSignal()
    recording_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.audio_input = None
        self.file = None
        self.current_path = None
        self.is_recording = False

    def start_recording(self, output_path):
        if self.is_recording: return
        self.current_path = output_path
        self.file = QFile(output_path)
        if not self.file.open(QIODevice.WriteOnly | QIODevice.Truncate):
            self.error_occurred.emit("Could not open file for writing.")
            return
        self.file.write(b'\x00' * 44)
        format = QAudioFormat()
        format.setSampleRate(44100)
        format.setChannelCount(1)
        format.setSampleSize(16)
        format.setCodec("audio/pcm")
        format.setByteOrder(QAudioFormat.LittleEndian)
        format.setSampleType(QAudioFormat.SignedInt)
        info = QAudioDeviceInfo.defaultInputDevice()
        if not info.isFormatSupported(format):
            format = info.nearestFormat(format)
        self.audio_input = QAudioInput(info, format)
        self.audio_input.start(self.file)
        self.is_recording = True
        self.recording_started.emit()

    def stop_recording(self):
        if not self.is_recording: return
        self.audio_input.stop()
        self.file.close()
        self.is_recording = False
        self._write_wav_header(self.current_path)
        self.recording_finished.emit(self.current_path)

    def _write_wav_header(self, path, max_retries=5, delay_s=0.1):
        """Fixes the WAV header so FFmpeg/VLC can read the PCM data."""
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