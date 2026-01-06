import time
import logging
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QPixmap, QPainter, QFont, QPen
from PyQt5.QtCore import Qt, QPointF
from model import ClipModel
from clip_painter import ClipPainter

class ClipItem(QGraphicsRectItem):

    def __init__(self, model: ClipModel, scale=50):
        super().__init__(0, 0, model.duration * scale, 40)
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.model = model
        self.uid = model.uid
        self._last_render_time = 0
        self._is_interacting = False
        self.name = model.name
        self.start = model.start
        self.duration = model.duration
        self.track = model.track
        self.speed = model.speed
        self.volume = model.volume
        self.scale = scale
        self.cached_pixmap = None
        self.setPos(self.start * scale, self.track * 40 + 30)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(5)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
        self.waveform_pixmap = None
        self.thumbnail_start = None
        self.thumbnail_end = None
        self.drag_mode = None
        self.update_cache()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.update_cache()
        return super().itemChange(change, value)

    def update_cache(self):
        now = time.time()
        if self._is_interacting and (now - self._last_render_time) < 0.033:
            return
        self._last_render_time = now
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0: return
        self.cached_pixmap = QPixmap(int(rect.width()), int(rect.height()))
        self.cached_pixmap.fill(Qt.transparent)
        painter = QPainter(self.cached_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        is_audio = getattr(self.model, 'media_type', 'video') == 'audio'
        is_out_of_sync = False
        if self.model.linked_uid:
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item.uid == self.model.linked_uid:
                    if abs(item.model.start - self.model.start) > 0.001:
                        is_out_of_sync = True
                    break
        ClipPainter.draw_base_rect(painter, rect, is_audio, is_out_of_sync)
        ClipPainter.draw_thumbnails(painter, rect, self.thumbnail_start, self.thumbnail_end, self.model)
        ClipPainter.draw_waveform(painter, rect, self.waveform_pixmap, self.model, self.scale)
        ClipPainter.draw_fades(painter, rect, self.model, self.scale)
        ClipPainter.draw_selection_border(painter, rect, self.isSelected(), is_out_of_sync)
        painter.setPen(QColor(255, 50, 50) if is_out_of_sync else Qt.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        display_name = f"⚠️ {self.name}" if is_out_of_sync else self.name
        painter.drawText(8, 15, display_name)
        painter.end()

    def paint(self, painter, option, widget):
        if not self.cached_pixmap:
            self.update_cache()
        if self.cached_pixmap and not self.cached_pixmap.isNull():
            painter.drawPixmap(0, 0, self.cached_pixmap)

    def mousePressEvent(self, event):
        self._is_interacting = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.logger.debug("ClipItem mouseReleaseEvent executing.")
        self._is_interacting = False
        super().mouseReleaseEvent(event)
        view = self.scene().views()[0]
        self.model.start = self.x() / self.scale
        self.model.track = round((self.y() - 30) / 40)
        view.data_changed.emit()
