from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import Qt

class CustomTitleBar(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.title)

    def update_title(self, title):
        self.title.setText(title)
