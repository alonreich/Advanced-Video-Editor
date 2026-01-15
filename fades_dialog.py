from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QDoubleSpinBox

class FadesDialog(QDialog):
    def __init__(self, fade_in, fade_out, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Fades")
        layout = QVBoxLayout(self)
        formLayout = QFormLayout()
        self.fadeInSpinBox = QDoubleSpinBox()
        self.fadeInSpinBox.setValue(fade_in)
        self.fadeOutSpinBox = QDoubleSpinBox()
        self.fadeOutSpinBox.setValue(fade_out)
        formLayout.addRow("Fade In:", self.fadeInSpinBox)
        formLayout.addRow("Fade Out:", self.fadeOutSpinBox)
        layout.addLayout(formLayout)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def getFades(self):
        return self.fadeInSpinBox.value(), self.fadeOutSpinBox.value()
