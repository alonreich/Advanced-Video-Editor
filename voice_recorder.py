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
        while self.recording:
            try:
                data = stream.read(self.chunk)
                frames.append(data)
                rms = audioop.rms(data, 2)
                level = min(100, int(rms / 327)) 
                self.level_signal.emit(level)
            except Exception:
                break
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
