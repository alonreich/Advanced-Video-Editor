from PyQt5.QtWidgets import QListWidget, QListWidgetItem
from PyQt5.QtCore import Qt, QMimeData, QUrl
from PyQt5.QtGui import QDrag
import os

class MediaPoolWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setStyleSheet("background: #222; color: #eee; border: none;")

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item:
            mime = QMimeData()
            path = item.data(Qt.UserRole)
            mime.setUrls([QUrl.fromLocalFile(path)])
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec_(supportedActions)

    def add_file(self, path):
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        self.addItem(item)