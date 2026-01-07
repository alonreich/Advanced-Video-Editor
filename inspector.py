from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, QGroupBox, 
    QSlider, QHBoxLayout, QGridLayout, QComboBox, QToolButton, QSpinBox, QCheckBox, QProgressBar, QPushButton, QSizePolicy)
from PyQt5.QtCore import pyqtSignal, Qt

class InspectorWidget(QWidget):
    param_changed = pyqtSignal(str, float)
    resolution_changed = pyqtSignal(str)
    track_mute_toggled = pyqtSignal(int, bool)
    crop_toggled = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(250)
        self.setStyleSheet("""
            QWidget { background-color: #2E2E2E; color: #E0E0E0; font-family: 'Segoe UI'; }
            QGroupBox { border: 1px solid #444; border-radius: 4px; margin-top: 20px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; color: #AAA; }
            QAbstractSpinBox { background: #1E1E1E; border: 1px solid #444; border-radius: 2px; padding: 4px; color: white; }
            QCheckBox { spacing: 5px; }
            QCheckBox::indicator { width: 13px; height: 13px; background: #1E1E1E; border: 1px solid #555; }
            QCheckBox::indicator:checked { background: #4A90E2; }
            QSlider::groove:horizontal { border: 1px solid #3A3A3A; height: 6px; background: #1E1E1E; margin: 2px 0; border-radius: 3px; }
            QSlider::handle:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #555, stop:0.4 #555, stop:0.45 #888, stop:0.55 #888, stop:0.6 #555, stop:1 #555);
                border: 1px solid #555; width: 14px; height: 14px; margin: -5px 0; border-radius: 3px;
            }
        """)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)
        self.lbl_title = QLabel("No Selection")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #FFF; margin-bottom: 10px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.lbl_title)
        gb_controls = QGroupBox("Controls")
        ctrl_layout = QVBoxLayout(gb_controls)
        self.chk_lock_pos = QCheckBox("Lock Position on Timeline")
        self.chk_lock_pos.toggled.connect(lambda c: self.param_changed.emit("locked", 1.0 if c else 0.0))
        self.chk_mute_track = QCheckBox("Mute Track")
        self.chk_mute_track.toggled.connect(self.on_mute_track_toggled)
        self.btn_resync = QPushButton("🔄 Re-Sync Link")
        self.btn_resync.setCursor(Qt.PointingHandCursor)
        self.btn_resync.setToolTip("Snap audio back to its video partner's position")
        self.btn_resync.setStyleSheet("background-color: #4A90E2; color: white; font-weight: bold;")
        self.btn_resync.clicked.connect(self.on_resync_clicked)
        self.btn_resync.hide()
        ctrl_layout.addWidget(self.chk_lock_pos)
        ctrl_layout.addWidget(self.chk_mute_track)
        ctrl_layout.addWidget(self.btn_resync)
        self.mic_meter = QProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.setTextVisible(False)
        self.mic_meter.setFixedHeight(10)
        self.mic_meter.setStyleSheet("""
            QProgressBar { background: #111; border: 1px solid #444; border-radius: 2px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f0, stop:0.8 #ff0, stop:1 #f00); }
        """)
        ctrl_layout.addWidget(QLabel("Mic Level:"))
        ctrl_layout.addWidget(self.mic_meter)
        self.layout.addWidget(gb_controls)
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
        self.combo_res.currentTextChanged.connect(self.on_res_changed)
        proj_l.addWidget(QLabel("Output Resolution:"))
        proj_l.addWidget(self.combo_res)
        self.layout.addWidget(gb_proj)
        self.current_clip = None

    def on_res_changed(self, text):
        self.resolution_changed.emit(text)
        is_portrait = "Portrait" in text
        self.lbl_res.setText(f"Mode: {'Vertical' if is_portrait else 'Horizontal'}")

    def on_mute_track_toggled(self, checked):
        if self.current_clip:
            self.track_mute_toggled.emit(self.current_clip.track, checked)

    def create_slider_group(self, title, param_name, min_val, max_val, default):
        gb = QGroupBox(title)
        l = QHBoxLayout(gb)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(int(min_val*100), int(max_val*100))
        slider.setValue(int(default*100))
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        if param_name == 'volume':
            spin.setDecimals(0)
            spin.setSingleStep(1)
        else:
            spin.setSingleStep(0.1)
        spin.valueChanged.connect(lambda v: slider.setValue(int(v*100)))
        spin.editingFinished.connect(lambda: self.param_changed.emit(param_name, spin.value()))
        slider.valueChanged.connect(lambda v: spin.setValue(v/100))
        slider.sliderReleased.connect(lambda: self.param_changed.emit(param_name, slider.value()/100))
        btn_reset = QToolButton()
        btn_reset.setText("\u21BA")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setToolTip(f"Reset {title.lower()} to default")
        btn_reset.clicked.connect(lambda: spin.setValue(default))
        btn_reset.clicked.connect(lambda: self.param_changed.emit(param_name, float(default)))
        setattr(self, f"spin_{param_name}", spin)
        setattr(self, f"slider_{param_name}", slider)
        l.addWidget(slider)
        l.addWidget(spin)
        l.addWidget(btn_reset)
        return gb

    def create_crop_group(self):
        gb = QGroupBox()
        gb.setStyleSheet("QGroupBox { margin-top: 10px; border: 1px solid #444; padding-top: 5px; }")
        l = QVBoxLayout(gb)
        self.btn_crop_toggle = QPushButton("Crop")
        self.btn_crop_toggle.setCheckable(True)
        self.btn_crop_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_crop_toggle.setToolTip("Toggle crop mode in the preview window")
        self.btn_crop_toggle.setFixedHeight(28)
        self.btn_crop_toggle.clicked.connect(self.crop_toggled.emit)
        self.btn_crop_toggle.setStyleSheet("""
            QPushButton {
                background-color: #444; color: #DDD; font-weight: bold; font-size: 12px;
                border: 2px solid #222; border-radius: 4px;
                border-bottom: 3px solid #111;
            }
            QPushButton:checked {
                background-color: #D84315; color: white;
                border-bottom: 1px solid #8f2a0b;
                margin-top: 2px;
            }
            QPushButton:hover { background-color: #555; }
            QPushButton:checked:hover { background-color: #E64A19; }
        """)
        l.addWidget(self.btn_crop_toggle)
        grid = QGridLayout()
        self.spin_crop_x1 = self.make_crop_spin()
        self.spin_crop_y1 = self.make_crop_spin()
        self.spin_crop_x2 = self.make_crop_spin()
        self.spin_crop_y2 = self.make_crop_spin()
        self.spin_crop_x1.valueChanged.connect(lambda v: self.param_changed.emit("crop_x1", v/100))
        self.spin_crop_y1.valueChanged.connect(lambda v: self.param_changed.emit("crop_y1", v/100))
        self.spin_crop_x2.valueChanged.connect(lambda v: self.param_changed.emit("crop_x2", v/100))
        self.spin_crop_y2.valueChanged.connect(lambda v: self.param_changed.emit("crop_y2", v/100))
        grid.addWidget(QLabel("X1:"), 0, 0)
        grid.addWidget(self.spin_crop_x1, 0, 1)
        grid.addWidget(QLabel("Y1:"), 0, 2)
        grid.addWidget(self.spin_crop_y1, 0, 3)
        grid.addWidget(QLabel("X2:"), 1, 0)
        grid.addWidget(self.spin_crop_x2, 1, 1)
        grid.addWidget(QLabel("Y2:"), 1, 2)
        grid.addWidget(self.spin_crop_y2, 1, 3)
        btn_reset = QToolButton()
        btn_reset.setText("Reset Crop")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setToolTip("Reset crop values to default")
        btn_reset.setStyleSheet("background: #333; color: white; border: 1px solid #555; border-radius: 3px;")
        btn_reset.clicked.connect(self.reset_crop)
        grid.addWidget(btn_reset, 2, 0, 1, 4, Qt.AlignCenter)
        l.addLayout(grid)
        self.layout.addWidget(gb)

    def make_crop_spin(self):
        s = QDoubleSpinBox()
        s.setRange(0, 100)
        s.setButtonSymbols(QDoubleSpinBox.NoButtons)
        s.setAlignment(Qt.AlignCenter)
        s.setDecimals(0)
        s.setFixedWidth(60)
        return s

    def reset_crop(self):
        self.spin_crop_x1.setValue(0)
        self.spin_crop_y1.setValue(0)
        self.spin_crop_x2.setValue(100)
        self.spin_crop_y2.setValue(100)

    def update_clip_param(self, param, value):
        """Updates a single parameter on the UI without a full refresh."""
        if not self.current_clip:
            return
        self.blockSignals(True)
        if param == "crop_x1":
            self.spin_crop_x1.setValue(value * 100)
        elif param == "crop_y1":
            self.spin_crop_y1.setValue(value * 100)
        elif param == "crop_x2":
            self.spin_crop_x2.setValue(value * 100)
        elif param == "crop_y2":
            self.spin_crop_y2.setValue(value * 100)
        self.blockSignals(False)

    def set_clip(self, clip_model, track_muted=False):
        self.blockSignals(True)
        self.current_clip = clip_model
        if clip_model:
            self.lbl_title.setText(f"Clip: {clip_model.name}")
            self.spin_speed.setEnabled(True)
            self.spin_volume.setEnabled(True)
            self.chk_mute_track.setEnabled(True)
            self.chk_lock_pos.setEnabled(True)
            self.spin_speed.setValue(getattr(clip_model, 'speed', 1.0))
            self.spin_volume.setValue(int(getattr(clip_model, 'volume', 100.0)))
            self.chk_lock_pos.setChecked(getattr(clip_model, 'locked', False))
            self.chk_mute_track.setChecked(track_muted)
            self.spin_crop_x1.setValue(getattr(clip_model, 'crop_x1', 0.0) * 100)
            self.spin_crop_y1.setValue(getattr(clip_model, 'crop_y1', 0.0) * 100)
            self.spin_crop_x2.setValue(getattr(clip_model, 'crop_x2', 1.0) * 100)
            self.spin_crop_y2.setValue(getattr(clip_model, 'crop_y2', 1.0) * 100)
            w = getattr(clip_model, 'width', 0)
            h = getattr(clip_model, 'height', 0)
            self.lbl_res.setText(f"Resolution: {w}x{h}" if w > 0 else "Resolution: N/A")
            self.lbl_bitrate.setText(f"Bitrate: {getattr(clip_model, 'bitrate', 0)//1000} kbps")
            self.btn_crop_toggle.setEnabled(True)
        else:
            self.lbl_title.setText("No Selection")
            self.spin_speed.setEnabled(False)
            self.spin_volume.setEnabled(False)
            self.chk_mute_track.setEnabled(False)
            self.chk_lock_pos.setEnabled(False)
            self.btn_crop_toggle.setEnabled(False)
        self.blockSignals(False)

    def on_resync_clicked(self):
        """Forces the audio partner to match the video partner's start and source_in."""
        if not self.current_clip or not self.current_clip.linked_uid:
            return
        self.param_changed.emit("resync_partner", 1.0)