from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, QGroupBox, QSlider, QHBoxLayout, QGridLayout
from PyQt5.QtCore import pyqtSignal, Qt

class InspectorWidget(QWidget):
    param_changed = pyqtSignal(str, float)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #2E2E2E; color: white;")
        layout = QVBoxLayout(self)
        self.lbl_title = QLabel("No Selection")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.lbl_title)
        
        gb_speed = QGroupBox("Speed")
        gb_speed.setStyleSheet("QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        sl = QVBoxLayout(gb_speed)
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setAlignment(Qt.AlignCenter)
        self.spin_speed.setStyleSheet("""
            QDoubleSpinBox::up-button { 
                width: 40px; height: 20px; background-color: #555; 
                border-bottom: 1px solid #333;
            }
            QDoubleSpinBox::up-button:hover { background-color: #666; }
            QDoubleSpinBox::down-button { 
                width: 40px; height: 20px; background-color: #555; 
            }
            QDoubleSpinBox::down-button:hover { background-color: #666; }
        """)
        self.spin_speed.setRange(0.1, 5.0)
        self.spin_speed.setValue(1.0)
        self.spin_speed.setFixedHeight(40)
        self.spin_speed.setToolTip("Adjust the playback speed of the clip.")
        self.spin_speed.valueChanged.connect(lambda v: self.param_changed.emit("speed", v))
        sl.addWidget(self.spin_speed)
        layout.addWidget(gb_speed)
        
        gb_vol = QGroupBox("Volume")
        gb_vol.setStyleSheet("QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        gb_vol.setToolTip("Adjust the volume of the clip.")
        vl = QVBoxLayout(gb_vol)
        
        vol_layout = QHBoxLayout()
        self.slider_vol = QSlider(Qt.Vertical)
        self.slider_vol.setRange(0, 200)
        self.slider_vol.setValue(100)
        
        self.spin_vol = QDoubleSpinBox()
        self.spin_vol.setAlignment(Qt.AlignCenter)
        self.spin_vol.setStyleSheet("""
            QDoubleSpinBox::up-button { 
                width: 40px; height: 20px; background-color: #555; 
                border-bottom: 1px solid #333;
            }
            QDoubleSpinBox::down-button { 
                width: 40px; height: 20px; background-color: #555; 
            }
            QDoubleSpinBox::down-button:hover { background-color: #666; }
        """)
        self.spin_vol.setRange(0, 200)
        self.spin_vol.setValue(100)
        
        self.slider_vol.valueChanged.connect(lambda v: self.spin_vol.setValue(float(v)))
        self.spin_vol.valueChanged.connect(lambda v: self.slider_vol.setValue(int(v)))
        self.spin_vol.valueChanged.connect(lambda v: self.param_changed.emit("volume", v))
        
        vol_layout.addWidget(self.slider_vol)
        vol_layout.addWidget(self.spin_vol)
        vl.addLayout(vol_layout)
        layout.addWidget(gb_vol)

        gb_info = QGroupBox("Information")
        info_layout = QVBoxLayout(gb_info)
        self.lbl_res = QLabel("Resolution: N/A")
        self.lbl_bitrate = QLabel("Bitrate: N/A")
        info_layout.addWidget(self.lbl_res)
        info_layout.addWidget(self.lbl_bitrate)
        layout.addWidget(gb_info)

        gb_crop = QGroupBox("Crop")
        gb_crop.setStyleSheet("QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        crop_layout = QGridLayout(gb_crop)
        
        self.spin_crop_x1 = QDoubleSpinBox()
        self.spin_crop_y1 = QDoubleSpinBox()
        self.spin_crop_x2 = QDoubleSpinBox()
        self.spin_crop_y2 = QDoubleSpinBox()

        no_buttons_style = "QDoubleSpinBox { border: 1px solid #555; } QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { border: none; background: transparent; }"
        for s in [self.spin_crop_x1, self.spin_crop_y1, self.spin_crop_x2, self.spin_crop_y2]:
            s.setRange(0.0, 1.0)
            s.setSingleStep(0.01)
            s.setStyleSheet(no_buttons_style)
            s.setAlignment(Qt.AlignCenter)

        self.spin_crop_x1.valueChanged.connect(lambda v: self.param_changed.emit("crop_x1", v))
        self.spin_crop_y1.valueChanged.connect(lambda v: self.param_changed.emit("crop_y1", v))
        self.spin_crop_x2.valueChanged.connect(lambda v: self.param_changed.emit("crop_x2", v))
        self.spin_crop_y2.valueChanged.connect(lambda v: self.param_changed.emit("crop_y2", v))
        
        crop_layout.addWidget(QLabel("Top Left X,Y"), 0, 0, 1, 2)
        crop_layout.addWidget(self.spin_crop_x1, 1, 0)
        crop_layout.addWidget(self.spin_crop_y1, 1, 1)
        crop_layout.addWidget(QLabel("Bottom Right X,Y"), 2, 0, 1, 2)
        crop_layout.addWidget(self.spin_crop_x2, 3, 0)
        crop_layout.addWidget(self.spin_crop_y2, 3, 1)
        
        layout.addWidget(gb_crop)

        layout.addStretch()

    def set_clip(self, clip_model):
        if not clip_model:
            self.lbl_title.setText("No Selection")
            self.setEnabled(False)
            self.blockSignals(True)
            self.spin_speed.setValue(1.0)
            self.spin_vol.setValue(100)
            self.slider_vol.setValue(100)
            self.lbl_res.setText("Resolution: N/A")
            self.lbl_bitrate.setText("Bitrate: N/A")
            self.spin_crop_x1.setValue(0)
            self.spin_crop_y1.setValue(0)
            self.spin_crop_x2.setValue(1)
            self.spin_crop_y2.setValue(1)
            self.blockSignals(False)
            return
        
        self.lbl_title.setText(f"Clip: {clip_model.name}")
        self.setEnabled(True)
        self.blockSignals(True)
        self.spin_speed.setValue(getattr(clip_model, 'speed', 1.0))
        self.spin_vol.setValue(getattr(clip_model, 'volume', 100.0))
        self.slider_vol.setValue(int(getattr(clip_model, 'volume', 100.0)))
        
        self.spin_crop_x1.setValue(getattr(clip_model, 'crop_x1', 0.0))
        self.spin_crop_y1.setValue(getattr(clip_model, 'crop_y1', 0.0))
        self.spin_crop_x2.setValue(getattr(clip_model, 'crop_x2', 1.0))
        self.spin_crop_y2.setValue(getattr(clip_model, 'crop_y2', 1.0))

        if getattr(clip_model, 'width', 0) > 0:
            self.lbl_res.setText(f"Resolution: {clip_model.width}x{clip_model.height}")
        else:
            self.lbl_res.setText("Resolution: N/A (Audio)")

        bitrate = getattr(clip_model, 'bitrate', 0)
        if bitrate > 0:
            self.lbl_bitrate.setText(f"Bitrate: {bitrate / 1000:.0f} kbps")
        else:
            self.lbl_bitrate.setText("Bitrate: N/A")
            
        self.blockSignals(False)
