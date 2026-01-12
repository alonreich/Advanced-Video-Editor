import pyaudio
import wave
import audioop
from PyQt5.QtCore import QThread, pyqtSignal

class VoiceWorker(QThread):
    finished = pyqtSignal(str)
    level_signal = pyqtSignal(int)

    def __init__(self, output_path):
        super().__init__()
        self.output_path = output_path
        self.recording = True
        self._paused = False
        self.threshold = 500
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100

    def set_threshold(self, value):
        self.threshold = value
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100

    def run(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=self.format, channels=self.channels,
                        rate=self.rate, input=True,
                        frames_per_buffer=self.chunk)
        frames = []
        current_gain = 1.0
        while self.recording:
            try:
                raw_data = stream.read(self.chunk)
                rms = audioop.rms(raw_data, 2)
                level = min(100, int(rms / 327)) 
                self.level_signal.emit(level)
                if self._paused:
                    continue
                target = 1.0 if rms >= self.threshold else 0.0
                step = 0.15 if target > current_gain else 0.06
                current_gain += (target - current_gain) * step
                data = audioop.mul(raw_data, 2, current_gain)
                frames.append(data)
            except Exception:
                break

    def toggle_pause(self, state):
        """Thread-safe toggle for the recording loop."""
        self._paused = state

    def finalize_recording(self, p, stream, frames):
        stream.stop_stream()
        stream.close()
        p.terminate()
        wf = wave.open(self.output_path, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(p.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        self.finished.emit(self.output_path)

    def stop(self):
        self.recording = False
