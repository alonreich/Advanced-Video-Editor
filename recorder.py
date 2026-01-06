import os
import struct
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

    def _write_wav_header(self, path):
        """Fixes the WAV header so FFmpeg/VLC can read the PCM data."""
        if not os.path.exists(path): return
        file_size = os.path.getsize(path)
        data_size = file_size - 44
        with open(path, 'r+b') as f:
            f.write(b'RIFF')
            f.write(struct.pack('<I', file_size - 8))
            f.write(b'WAVE')
            f.write(b'fmt ')
            f.write(struct.pack('<I', 16))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<H', 1))
            f.write(struct.pack('<I', 44100))
            f.write(struct.pack('<I', 44100 * 1 * 2))
            f.write(struct.pack('<H', 2))
            f.write(struct.pack('<H', 16))
            f.write(b'data')
            f.write(struct.pack('<I', data_size))