from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, QGroupBox, 
                             QSlider, QHBoxLayout, QGridLayout, QComboBox, QToolButton, QSpinBox)
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon

class InspectorWidget(QWidget):
    param_changed = pyqtSignal(str, float)
    resolution_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QWidget { background-color: #2E2E2E; color: #E0E0E0; font-family: 'Segoe UI'; }
            QGroupBox { border: 1px solid #444; border-radius: 4px; margin-top: 20px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top left; padding: 0 5px; left: 10px; color: #AAA; }
            QAbstractSpinBox { background: #1E1E1E; border: 1px solid #444; border-radius: 2px; padding: 4px; color: white; selection-background-color: #4A90E2; }
            QAbstractSpinBox:hover { border: 1px solid #666; }
            QAbstractSpinBox::up-button, QAbstractSpinBox::down-button { background: #333; width: 15px; }
            QAbstractSpinBox::up-arrow { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-bottom: 6px solid #AAA; margin: 2px; }
            QAbstractSpinBox::down-arrow { width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #AAA; margin: 2px; }
            QSlider::groove:horizontal { border: 1px solid #444; height: 6px; background: #1E1E1E; border-radius: 3px; }
            QSlider::handle:horizontal { background: #4A90E2; border: 1px solid #4A90E2; width: 18px; height: 18px; margin: -7px 0; border-radius: 9px; }
            QSlider::sub-page:horizontal { background: #4A90E2; border-radius: 3px; }
            QComboBox { background: #1E1E1E; border: 1px solid #444; padding: 4px; color: white; }
            QToolButton { background: transparent; border: none; color: #888; }
            QToolButton:hover { color: #FFF; }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.lbl_title = QLabel("No Selection")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF; margin-bottom: 10px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.lbl_title)
        self.layout.addWidget(self.create_slider_group("Speed", "speed", 0.1, 5.0, 1.0))
        self.layout.addWidget(self.create_slider_group("Volume", "volume", 0.0, 200.0, 100.0))
        self.create_crop_group()
        gb_info = QGroupBox("Information")
        info_l = QVBoxLayout(gb_info)
        self.lbl_res = QLabel("Resolution: N/A")
        self.lbl_bitrate = QLabel("Bitrate: N/A")
        info_l.addWidget(self.lbl_res)
        info_l.addWidget(self.lbl_bitrate)
        self.layout.addWidget(gb_info)
        self.layout.addStretch()
        gb_proj = QGroupBox("Project Settings")
        proj_l = QVBoxLayout(gb_proj)
        self.combo_res = QComboBox()
        self.combo_res.addItems([
            "Landscape 1920x1080 (HD)", "Landscape 2560x1440 (QHD)", "Landscape 3840x2160 (4K)",
            "Portrait 1080x1920 (Mobile HD)", "Portrait 1440x2560 (Mobile QHD)"
        ])
        self.combo_res.currentTextChanged.connect(self.resolution_changed.emit)
        proj_l.addWidget(QLabel("Output Resolution:"))
        proj_l.addWidget(self.combo_res)
        self.layout.addWidget(gb_proj)

    # C:\Fortnite_Video_Software\advanced\inspector.py

# Replace create_slider_group method (Source 97-103)
    def create_slider_group(self, title, param_name, min_val, max_val, default):
        gb = QGroupBox(title)
        l = QHBoxLayout(gb)
        
        slider = QSlider(Qt.Horizontal)
        
        if param_name == "volume":
            slider.setRange(0, 200)
            slider.setValue(int(default))
            spin = QSpinBox()
            spin.setRange(0, 200)
            spin.setValue(int(default))
            
            self.chk_mute = QToolButton()
            self.chk_mute.setText("Mute")
            self.chk_mute.setCheckable(True)
            self.chk_mute.toggled.connect(lambda c: self.param_changed.emit("mute", 1.0 if c else 0.0))
            l.addWidget(self.chk_mute)

        else:
            slider.setRange(int(min_val*100), int(max_val*100))
            slider.setValue(int(default*100))
            spin = QDoubleSpinBox()
            spin.setRange(min_val, max_val)
            spin.setValue(default)
            spin.setSingleStep(0.1)

        # LINKING
        # 1. Spin -> Slider (Update UI only)
        if param_name == "volume":
            spin.valueChanged.connect(lambda v: slider.setValue(int(v)))
            # SpinBox editingFinished -> Undoable Action
            spin.editingFinished.connect(lambda: self.param_changed.emit(param_name, float(spin.value())))
        else:
            spin.valueChanged.connect(lambda v: slider.setValue(int(v*100)))
            spin.editingFinished.connect(lambda: self.param_changed.emit(param_name, spin.value()))

        # 2. Slider -> Spin (Update UI only while dragging)
        if param_name == "volume":
            slider.valueChanged.connect(spin.setValue)
        else:
            slider.valueChanged.connect(lambda v: spin.setValue(v/100))

        # 3. Slider RELEASE -> Undoable Action (The Fix)
        if param_name == "volume":
            slider.sliderReleased.connect(lambda: self.param_changed.emit(param_name, float(slider.value())))
        else:
            slider.sliderReleased.connect(lambda: self.param_changed.emit(param_name, slider.value()/100))

        btn_reset = QToolButton()
        btn_reset.setText("↺")
        btn_reset.clicked.connect(lambda: spin.setValue(default))
        btn_reset.clicked.connect(lambda: self.param_changed.emit(param_name, float(default))) # Ensure reset commits
        
        setattr(self, f"spin_{param_name}", spin)
        setattr(self, f"slider_{param_name}", slider)
        
        l.addWidget(slider)
        l.addWidget(spin)
        l.addWidget(btn_reset)
        return gb

    def create_crop_group(self):
        gb = QGroupBox("Crop")
        l = QGridLayout(gb)
        self.spin_crop_x1 = self.make_crop_spin()
        self.spin_crop_y1 = self.make_crop_spin()
        self.spin_crop_x2 = self.make_crop_spin()
        self.spin_crop_y2 = self.make_crop_spin()
        self.spin_crop_x1.valueChanged.connect(lambda v: self.param_changed.emit("crop_x1", v/100))
        self.spin_crop_y1.valueChanged.connect(lambda v: self.param_changed.emit("crop_y1", v/100))
        self.spin_crop_x2.valueChanged.connect(lambda v: self.param_changed.emit("crop_x2", v/100))
        self.spin_crop_y2.valueChanged.connect(lambda v: self.param_changed.emit("crop_y2", v/100))
        l.addWidget(QLabel("Top-Left %"), 0, 0, 1, 2)
        l.addWidget(self.spin_crop_x1, 1, 0)
        l.addWidget(self.spin_crop_y1, 1, 1)
        l.addWidget(QLabel("Btm-Right %"), 2, 0, 1, 2)
        l.addWidget(self.spin_crop_x2, 3, 0)
        l.addWidget(self.spin_crop_y2, 3, 1)
        btn_reset = QToolButton()
        btn_reset.setText("Reset Crop")
        btn_reset.clicked.connect(self.reset_crop)
        l.addWidget(btn_reset, 4, 0, 1, 2)
        self.layout.addWidget(gb)

    def make_crop_spin(self):
        s = QDoubleSpinBox()
        s.setRange(0, 100)
        s.setButtonSymbols(QDoubleSpinBox.NoButtons)
        s.setAlignment(Qt.AlignCenter)
        return s

    def reset_crop(self):
        self.spin_crop_x1.setValue(0)
        self.spin_crop_y1.setValue(0)
        self.spin_crop_x2.setValue(100)
        self.spin_crop_y2.setValue(100)

    def set_clip(self, clip_model):
        self.blockSignals(True)
        if not clip_model:
            self.lbl_title.setText("No Selection")
            self.spin_speed.setEnabled(False)
            self.spin_volume.setEnabled(False)
        else:
            self.lbl_title.setText(f"Clip: {clip_model.name}")
            self.spin_speed.setEnabled(True)
            self.spin_volume.setEnabled(True)
            self.spin_speed.setValue(getattr(clip_model, 'speed', 1.0))
            self.spin_volume.setValue(getattr(clip_model, 'volume', 100.0))
            self.spin_crop_x1.setValue(getattr(clip_model, 'crop_x1', 0.0) * 100)
            self.spin_crop_y1.setValue(getattr(clip_model, 'crop_y1', 0.0) * 100)
            self.spin_crop_x2.setValue(getattr(clip_model, 'crop_x2', 1.0) * 100)
            self.spin_crop_y2.setValue(getattr(clip_model, 'crop_y2', 1.0) * 100)
            w = getattr(clip_model, 'width', 0)
            h = getattr(clip_model, 'height', 0)
            self.lbl_res.setText(f"Resolution: {w}x{h}" if w > 0 else "Resolution: N/A")
            self.lbl_bitrate.setText(f"Bitrate: {getattr(clip_model, 'bitrate', 0)//1000} kbps")
        self.blockSignals(False)
