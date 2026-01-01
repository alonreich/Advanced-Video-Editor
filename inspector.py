from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, QPushButton, QComboBox, QGroupBox
from PyQt5.QtCore import pyqtSignal

class InspectorWidget(QWidget):
    param_changed = pyqtSignal(str, float)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #333; color: white;")
        layout = QVBoxLayout(self)
        self.lbl_title = QLabel("No Selection")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_title)
        gb_speed = QGroupBox("Speed")
        sl = QVBoxLayout(gb_speed)
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.1, 5.0)
        self.spin_speed.setValue(1.0)
        self.spin_speed.valueChanged.connect(lambda v: self.param_changed.emit("speed", v))
        sl.addWidget(self.spin_speed)
        layout.addWidget(gb_speed)
        gb_vol = QGroupBox("Volume")
        vl = QVBoxLayout(gb_vol)
        self.spin_vol = QDoubleSpinBox()
        self.spin_vol.setRange(0, 200)
        self.spin_vol.setValue(100)
        self.spin_vol.valueChanged.connect(lambda v: self.param_changed.emit("volume", v))
        vl.addWidget(self.spin_vol)
        layout.addWidget(gb_vol)
        layout.addStretch()

    def set_clip(self, clip_model):
        if not clip_model:
            self.lbl_title.setText("No Selection")
            self.setEnabled(False)
            self.blockSignals(True)
            self.spin_speed.setValue(1.0)
            self.spin_vol.setValue(100)
            self.blockSignals(False)
            return
        self.lbl_title.setText(f"Clip: {clip_model.name}")
        self.setEnabled(True)
        self.blockSignals(True)
        self.spin_speed.setValue(getattr(clip_model, 'speed', 1.0))
        self.spin_vol.setValue(getattr(clip_model, 'volume', 100.0))
        self.blockSignals(False)
