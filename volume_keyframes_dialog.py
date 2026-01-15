from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QDialogButtonBox

class VolumeKeyframesDialog(QDialog):
    def __init__(self, keyframes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Volume Keyframes")
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Time (s)", "Volume (%)"])
        self.setKeyframes(keyframes)
        layout.addWidget(self.table)
        buttonsLayout = QHBoxLayout()
        addButton = QPushButton("Add")
        addButton.clicked.connect(self.addKeyframe)
        removeButton = QPushButton("Remove")
        removeButton.clicked.connect(self.removeKeyframe)
        buttonsLayout.addWidget(addButton)
        buttonsLayout.addWidget(removeButton)
        layout.addLayout(buttonsLayout)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def setKeyframes(self, keyframes):
        self.table.setRowCount(len(keyframes))
        for i, (time, volume) in enumerate(keyframes):
            self.table.setItem(i, 0, QTableWidgetItem(str(time)))
            self.table.setItem(i, 1, QTableWidgetItem(str(volume)))

    def getKeyframes(self):
        keyframes = []
        for i in range(self.table.rowCount()):
            time = float(self.table.item(i, 0).text())
            volume = float(self.table.item(i, 1).text())
            keyframes.append((time, volume))
        return sorted(keyframes)

    def addKeyframe(self):
        self.table.insertRow(self.table.rowCount())

    def removeKeyframe(self):
        self.table.removeRow(self.table.currentRow())
