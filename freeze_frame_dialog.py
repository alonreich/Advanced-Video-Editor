from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QDoubleSpinBox

class FreezeFrameDialog(QDialog):
    def __init__(self, start_freeze, end_freeze, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Freeze Frame")
        layout = QVBoxLayout(self)
        formLayout = QFormLayout()
        self.startFreezeSpinBox = QDoubleSpinBox()
        self.startFreezeSpinBox.setValue(start_freeze)
        self.endFreezeSpinBox = QDoubleSpinBox()
        self.endFreezeSpinBox.setValue(end_freeze)
        formLayout.addRow("Start Freeze:", self.startFreezeSpinBox)
        formLayout.addRow("End Freeze:", self.endFreezeSpinBox)
        layout.addLayout(formLayout)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def getFreezeFrames(self):
        return self.startFreezeSpinBox.value(), self.endFreezeSpinBox.value()
