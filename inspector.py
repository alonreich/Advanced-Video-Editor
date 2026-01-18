from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QDoubleSpinBox, QGroupBox, 
    QSlider, QHBoxLayout, QGridLayout, QComboBox, QToolButton, QSpinBox, QCheckBox, 
    QProgressBar, QPushButton, QSizePolicy, QScrollArea)

from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtCore import pyqtSignal, Qt
import constants

class GatedProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.threshold_pct = 0.0

    def set_threshold(self, value_pct):
        self.threshold_pct = value_pct
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.threshold_pct <= 0: return
        painter = QPainter(self)
        painter.setPen(QPen(Qt.white, 2, Qt.DashLine))
        x = int(self.width() * self.threshold_pct)
        painter.drawLine(x, 0, x, self.height())

class InspectorWidget(QWidget):
    param_changed = pyqtSignal(str, float)
    resolution_changed = pyqtSignal(str)
    track_mute_toggled = pyqtSignal(int, bool)
    crop_toggled = pyqtSignal(bool)

    def __init__(self, main_window=None):
        super().__init__()
        self.mw = main_window
        self.setMinimumWidth(280) 
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{ background-color: {constants.COLOR_BACKGROUND.darker(50).name()}; border: none; }}
            QScrollBar:vertical {{
                border: none;
                background: #2b2b2b;
                width: 14px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #bfbfbf; /* Bright Silver for high visibility */
                min-height: 30px;
                border-radius: 7px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #e0e0e0; /* Almost white on hover */
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
        """)
        self.content_widget = QWidget()
        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setSpacing(10) 
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.content_widget.setStyleSheet(f"""
            QWidget {{ background-color: {constants.COLOR_BACKGROUND.darker(50).name()}; color: {constants.COLOR_TEXT.name()}; font-family: 'Segoe UI'; font-size: 12px; }}
            QGroupBox {{ border: 1px solid {constants.COLOR_BACKGROUND.lighter(50).name()}; border-radius: 4px; margin-top: 15px; font-weight: bold; padding-top: 10px; }}
            QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; color: {constants.COLOR_TEXT.darker(100).name()}; }}
            QAbstractSpinBox {{ background: {constants.COLOR_BACKGROUND.darker(100).name()}; border: 1px solid {constants.COLOR_BACKGROUND.lighter(50).name()}; border-radius: 2px; padding: 2px; color: white; }}
            QCheckBox {{ spacing: 5px; }}
            QCheckBox::indicator {{ width: 13px; height: 13px; background: {constants.COLOR_BACKGROUND.darker(100).name()}; border: 1px solid {constants.COLOR_BACKGROUND.lighter(70).name()}; }}
            QCheckBox::indicator:checked {{ background: {constants.COLOR_PRIMARY.name()}; }}
            QSlider::groove:horizontal {{ border: 1px solid {constants.COLOR_BACKGROUND.darker(70).name()}; height: 4px; background: {constants.COLOR_BACKGROUND.darker(100).name()}; margin: 2px 0; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: #888; border: 1px solid #555; width: 12px; height: 12px; margin: -4px 0; border-radius: 3px; }}
        """)
        self.lbl_title = QLabel("No Selection")
        self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {constants.COLOR_TEXT.lighter(100).name()}; margin-bottom: 5px;")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.lbl_title)
        gb_controls = QGroupBox("Controls")
        ctrl_layout = QVBoxLayout(gb_controls)
        ctrl_layout.setSpacing(5) 
        self.chk_lock_pos = QCheckBox("Lock Position")
        self.chk_lock_pos.toggled.connect(lambda c: self.param_changed.emit("locked", 1.0 if c else 0.0))
        self.chk_mute_track = QCheckBox("Mute Track")
        self.chk_mute_track.toggled.connect(self.on_mute_track_toggled)
        self.chk_main_audio = QCheckBox("Main Audio Source")
        self.chk_main_audio.toggled.connect(self.on_main_audio_toggled)
        self.btn_resync = QPushButton("🔄 Re-Sync Link")
        self.btn_resync.setCursor(Qt.PointingHandCursor)
        self.btn_resync.setToolTip("Snap audio back to its video partner's position")
        self.btn_resync.setStyleSheet(f"background-color: {constants.COLOR_PRIMARY.name()}; color: white; font-weight: bold; padding: 4px;")
        self.btn_resync.clicked.connect(self.on_resync_clicked)
        self.btn_resync.hide()
        # Align checkboxes in a centered column
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(2, 1)
        for i, chk in enumerate([self.chk_lock_pos, self.chk_mute_track, self.chk_main_audio]):
            grid.addWidget(chk, i, 1)
        ctrl_layout.addLayout(grid)
        ctrl_layout.addWidget(self.btn_resync)
        self.mic_meter = GatedProgressBar()
        self.mic_meter.setRange(0, 100)
        self.mic_meter.set_threshold(0.015)
        self.mic_meter.setTextVisible(False)
        self.mic_meter.setFixedHeight(8) 
        self.mic_meter.setStyleSheet(f"""
            QProgressBar {{ background: {constants.COLOR_BACKGROUND.darker(100).name()}; border: 1px solid {constants.COLOR_BACKGROUND.lighter(50).name()}; border-radius: 2px; }}
            QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {constants.COLOR_SUCCESS.name()}, stop:0.8 #ff0, stop:1 {constants.COLOR_ERROR.name()}); }}
        """)
        ctrl_layout.addWidget(QLabel("Mic Level:"))
        ctrl_layout.addWidget(self.mic_meter)
        self.layout.addWidget(gb_controls)
        self.layout.addWidget(self.create_slider_group("Speed", "speed", 0.1, 5.0, 1.0))
        self.layout.addWidget(self.create_slider_group("Volume", "volume", 0.0, 200.0, 100.0))
        self.create_crop_group()
        gb_proj = QGroupBox("Export Resolution")
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
        self.layout.addStretch()
        gb_info = QGroupBox("Info")
        info_l = QVBoxLayout(gb_info)
        info_l.setSpacing(2)
        self.lbl_res = QLabel("Res: N/A")
        self.lbl_bitrate = QLabel("Bitrate: N/A")
        info_l.addWidget(self.lbl_res)
        info_l.addWidget(self.lbl_bitrate)
        self.layout.addWidget(gb_info)
        self.scroll.setWidget(self.content_widget)
        outer_layout.addWidget(self.scroll)
        self.current_clip = None

    def on_res_changed(self, text):
        self.resolution_changed.emit(text)
        is_portrait = "Portrait" in text
        self.lbl_res.setText(f"Mode: {'Vertical' if is_portrait else 'Horizontal'}")

    def on_mute_track_toggled(self, checked):
        if self.current_clip:
            self.track_mute_toggled.emit(self.current_clip.track, checked)
            
    def on_main_audio_toggled(self, checked):
        if self.current_clip:
            self.param_changed.emit("is_main_audio_source", 1.0 if checked else 0.0)

    def create_slider_group(self, title, param_name, min_val, max_val, default):
        gb = QGroupBox(title)
        l = QHBoxLayout(gb)
        l.setContentsMargins(5, 5, 5, 5) 
        slider = QSlider(Qt.Horizontal)
        # For speed slider, adjust range so that default 1.0 is centered
        if param_name == 'speed':
            # Want slider min=0.1, max=1.9 (so that 1.0 is midpoint)
            slider_min = 0.1
            slider_max = 1.9
            slider.setRange(int(slider_min * 100), int(slider_max * 100))
            # Map spin value to slider position
            def spin_to_slider(val):
                if val <= slider_min:
                    return int(slider_min * 100)
                elif val >= slider_max:
                    return int(slider_max * 100)
                else:
                    return int(val * 100)
            def slider_to_spin(pos):
                return pos / 100.0
            # Set initial slider position based on default (should be 1.0)
            slider.setValue(int(default * 100))
        else:
            slider.setRange(int(min_val*100), int(max_val*100))
            slider.setValue(int(default*100))
            spin_to_slider = lambda v: int(v*100)
            slider_to_spin = lambda p: p/100.0
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        spin.setFixedWidth(55) 
        if param_name == 'volume':
            spin.setDecimals(0)
            spin.setSingleStep(1)
        else:
            spin.setSingleStep(0.1)
        # Custom connections for speed
        if param_name == 'speed':
            def on_spin_changed(v):
                slider.setValue(spin_to_slider(v))
                self.param_changed.emit(param_name, v)
            spin.valueChanged.connect(on_spin_changed)
            spin.editingFinished.connect(lambda: self.param_changed.emit(param_name, spin.value()))
            def on_slider_changed(pos):
                spin.blockSignals(True)
                spin.setValue(slider_to_spin(pos))
                spin.blockSignals(False)
            slider.valueChanged.connect(on_slider_changed)
            slider.sliderReleased.connect(lambda: self.param_changed.emit(param_name, slider_to_spin(slider.value())))
        else:
            spin.valueChanged.connect(lambda v: slider.setValue(spin_to_slider(v)))
            spin.editingFinished.connect(lambda: self.param_changed.emit(param_name, spin.value()))
            slider.valueChanged.connect(lambda v: spin.setValue(slider_to_spin(v)))
            slider.sliderReleased.connect(lambda: self.param_changed.emit(param_name, slider_to_spin(slider.value())))
        btn_reset = QToolButton()
        btn_reset.setText("⟲")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setToolTip(f"Reset {title.lower()} to default")
        btn_reset.setFixedSize(20, 20) 
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
        gb.setStyleSheet(f"QGroupBox {{ margin-top: 10px; border: 1px solid {constants.COLOR_BACKGROUND.lighter(50).name()}; padding-top: 5px; }}")
        l = QVBoxLayout(gb)
        l.setSpacing(2) 
        l.setContentsMargins(2, 5, 2, 2)
        self.btn_crop_toggle = QPushButton("Crop Mode")
        self.btn_crop_toggle.setCheckable(True)
        self.btn_crop_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_crop_toggle.setToolTip("Toggle crop mode in the preview window")
        self.btn_crop_toggle.setFixedWidth(100)
        self.btn_crop_toggle.setFixedHeight(22) 
        self.btn_crop_toggle.clicked.connect(self.crop_toggled.emit)
        self.btn_crop_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {constants.COLOR_BACKGROUND.lighter(50).name()}; color: {constants.COLOR_TEXT.darker(20).name()}; font-weight: bold; font-size: 11px;
                border: 2px solid {constants.COLOR_BACKGROUND.darker(100).name()}; border-radius: 4px;
                border-bottom: 3px solid {constants.COLOR_BACKGROUND.darker(150).name()};
            }}
            QPushButton:checked {{
                background-color: #D84315; color: white;
                border-bottom: 1px solid #8f2a0b; margin-top: 2px;
            }}
            QPushButton:hover {{ background-color: {constants.COLOR_BACKGROUND.lighter(70).name()}; }}
            QPushButton:checked:hover {{ background-color: #E64A19; }}
        """)
        # Center the button in the layout
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(self.btn_crop_toggle)
        hbox.addStretch()
        l.addLayout(hbox)
        grid = QGridLayout()
        grid.setSpacing(1)  # Reduced spacing
        grid.setContentsMargins(0, 0, 0, 0)
        self.spin_crop_x1 = self.make_crop_spin()
        self.spin_crop_y1 = self.make_crop_spin()
        self.spin_crop_x2 = self.make_crop_spin()
        self.spin_crop_y2 = self.make_crop_spin()
        self.spin_crop_x1.valueChanged.connect(lambda v: self.param_changed.emit("crop_x1", v/100))
        self.spin_crop_y1.valueChanged.connect(lambda v: self.param_changed.emit("crop_y1", v/100))
        self.spin_crop_x2.valueChanged.connect(lambda v: self.param_changed.emit("crop_x2", v/100))
        self.spin_crop_y2.valueChanged.connect(lambda v: self.param_changed.emit("crop_y2", v/100))

        def lbl(t):
            l = QLabel(t)
            l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            l.setStyleSheet("font-size: 10px;")  # Smaller font
            return l
        grid.addWidget(lbl("X1"), 0, 0)
        grid.addWidget(self.spin_crop_x1, 0, 1)
        grid.addWidget(lbl("Y1"), 0, 2)
        grid.addWidget(self.spin_crop_y1, 0, 3)
        grid.addWidget(lbl("X2"), 1, 0)
        grid.addWidget(self.spin_crop_x2, 1, 1)
        grid.addWidget(lbl("Y2"), 1, 2)
        grid.addWidget(self.spin_crop_y2, 1, 3)
        btn_reset = QToolButton()
        btn_reset.setText("Reset")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setToolTip("Reset crop values to default")
        btn_reset.setStyleSheet(f"background: {constants.COLOR_BACKGROUND.lighter(70).name()}; color: white; border: 1px solid {constants.COLOR_BACKGROUND.lighter(50).name()}; border-radius: 3px; font-size: 10px;")
        btn_reset.setFixedHeight(18)
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
        s.setFixedWidth(35)  # Reduced width
        s.setFixedHeight(20)
        s.setStyleSheet("font-size: 11px; padding: 0px;")
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
        if param == "speed":
            self.spin_speed.setValue(value)
            self.slider_speed.setValue(int(value * 100))
        elif param == "volume":
            self.spin_volume.setValue(value)
            self.slider_volume.setValue(int(value * 100))
        elif param == "crop_x1":
            self.spin_crop_x1.setValue(value * 100)
        elif param == "crop_y1":
            self.spin_crop_y1.setValue(value * 100)
        elif param == "crop_x2":
            self.spin_crop_x2.setValue(value * 100)
        elif param == "crop_y2":
            self.spin_crop_y2.setValue(value * 100)
        self.blockSignals(False)

    def set_clip(self, clip_models, track_muted=False):
        self.blockSignals(True)
        self.current_clip = clip_models
        has_audio = False
        is_main_audio = False
        if clip_models:
            first_clip = clip_models[0]
            has_audio = getattr(first_clip, 'has_audio', False)
            is_main_audio = getattr(first_clip, 'is_main_audio_source', False)
        self.chk_main_audio.setVisible(has_audio)
        if not clip_models:
            self.lbl_title.setText("No Selection")
            for attr in ['spin_speed', 'slider_speed', 'spin_volume', 'slider_volume', 
                         'chk_mute_track', 'chk_lock_pos', 'btn_crop_toggle', 'btn_resync', 'chk_main_audio',
                         'spin_crop_x1', 'spin_crop_y1', 'spin_crop_x2', 'spin_crop_y2']:
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(False)
        else:
            for attr in ['spin_speed', 'slider_speed', 'spin_volume', 'slider_volume', 
                         'chk_mute_track', 'chk_lock_pos', 'btn_crop_toggle', 
                         'spin_crop_x1', 'spin_crop_y1', 'spin_crop_x2', 'spin_crop_y2']:
                if hasattr(self, attr):
                    getattr(self, attr).setEnabled(True)
            self.chk_main_audio.setEnabled(has_audio)
            self.spin_speed.setEnabled(True)
            self.spin_volume.setEnabled(has_audio)
            self.chk_mute_track.setEnabled(True)
            self.chk_lock_pos.setEnabled(True)
            self.btn_crop_toggle.setEnabled(True)
            first_clip = clip_models[0]
            if len(clip_models) > 1:
                self.lbl_title.setText(f"{len(clip_models)} Clips Selected")
            else:
                self.lbl_title.setText(f"Clip: {first_clip.name}")
            self.spin_speed.setValue(getattr(first_clip, 'speed', 1.0))
            self.spin_volume.setValue(int(getattr(first_clip, 'volume', 100.0)))
            self.chk_lock_pos.setChecked(getattr(first_clip, 'locked', False))
            self.chk_mute_track.setChecked(track_muted)
            self.chk_main_audio.setChecked(is_main_audio)
            self.spin_crop_x1.setValue(getattr(first_clip, 'crop_x1', 0.0) * 100)
            self.spin_crop_y1.setValue(getattr(first_clip, 'crop_y1', 0.0) * 100)
            self.spin_crop_x2.setValue(getattr(first_clip, 'crop_x2', 1.0) * 100)
            self.spin_crop_y2.setValue(getattr(first_clip, 'crop_y2', 1.0) * 100)
            w = getattr(first_clip, 'width', 0)
            h = getattr(first_clip, 'height', 0)
            self.lbl_res.setText(f"Res: {w}x{h}" if w > 0 else "Res: N/A")
            self.lbl_bitrate.setText(f"Bitrate: {getattr(first_clip, 'bitrate', 0)//1000} kbps")
        self.blockSignals(False)

    def on_resync_clicked(self):
        """Forces the audio partner to match the video partner's start and source_in."""
        if not self.current_clip or not self.current_clip.linked_uid:
            return
        self.param_changed.emit("resync_partner", 1.0)

    def on_gate_threshold_changed(self, value):
        """Updates the visual line and emits a signal for the recorder."""
        pct = value / 32767.0 
        self.mic_meter.set_threshold(pct)
        self.param_changed.emit("audio_gate_threshold", float(value))
