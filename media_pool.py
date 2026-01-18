import os
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QMenu, QAction
from PyQt5.QtCore import Qt, QMimeData, QUrl, pyqtSignal
from PyQt5.QtGui import QDrag, QKeySequence

class MediaPoolWidget(QListWidget):
    media_double_clicked = pyqtSignal(str)
    media_removed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setStyleSheet("background: #222; color: #eee; border: none;")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.delete_action = QAction("Delete", self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        self.delete_action.triggered.connect(self._delete_selected)
        self.context_menu = QMenu(self)
        self.context_menu.addAction(self.delete_action)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if item:
            mime = QMimeData()
            path = item.data(Qt.UserRole)
            mime.setUrls([QUrl.fromLocalFile(path)])
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.exec_(supportedActions)

    def mouseDoubleClickEvent(self, event):
        item = self.currentItem()
        if item:
            path = item.data(Qt.UserRole)
            if path:
                self.media_double_clicked.emit(path)
        super().mouseDoubleClickEvent(event)

    def add_file(self, path):
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.UserRole, path)
        self.addItem(item)
    
    def _show_context_menu(self, position):
        """Show context menu at the given position."""
        item = self.itemAt(position)
        if item:
            self.setCurrentItem(item)
            self.context_menu.exec_(self.viewport().mapToGlobal(position))
    
    def _delete_selected(self):
        """Delete the currently selected item."""
        item = self.currentItem()
        if item:
            path = item.data(Qt.UserRole)
            row = self.row(item)
            self.takeItem(row)
            self.media_removed.emit(path)
    
    def keyPressEvent(self, event):
        """Handle key press events, specifically Delete key."""
        if event.key() == Qt.Key_Delete:
            self._delete_selected()
        else:
            super().keyPressEvent(event)
