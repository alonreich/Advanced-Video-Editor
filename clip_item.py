import time
import logging
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QPixmap, QPainter, QFont, QPen
from PyQt5.QtCore import Qt, QPointF, QRectF
from model import ClipModel
from clip_painter import ClipPainter
import constants

class ClipItem(QGraphicsRectItem):
    def __init__(self, model: ClipModel, scale=constants.DEFAULT_TIMELINE_SCALE_FACTOR):
        super().__init__(0, 0, model.duration * scale, constants.TRACK_HEIGHT)
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
        self.setPos(self.start * scale, self.track * constants.TRACK_HEIGHT + constants.RULER_HEIGHT)
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
        self.is_colliding = False
        self.handle_width = 20
        self.update_cache()

    def update_handle_rects(self):
        self.left_handle_rect = QRectF(0, 0, self.handle_width, self.rect().height())
        self.right_handle_rect = QRectF(self.rect().width() - self.handle_width, 0, self.handle_width, self.rect().height())

    def hoverEnterEvent(self, event):
        self.setToolTip(f"{self.model.name}\nDuration: {self.model.duration:.2f}s")
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event):
        if self.model.media_type == 'audio':
            self.setCursor(Qt.PointingHandCursor)
            super().hoverMoveEvent(event)
            return
        self.update_handle_rects()
        pos = event.pos()
        if self.left_handle_rect.contains(pos) or self.right_handle_rect.contains(pos):
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.PointingHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        self.setToolTip("")
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.update_cache()
        elif change == QGraphicsItem.ItemSceneChange and not value:
            self.cached_pixmap = None
            self.waveform_pixmap = None
            self.thumbnail_start = None
            self.thumbnail_end = None
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
        is_audio = self.model.media_type == 'audio'
        is_out_of_sync = False
        if self.model.linked_uid and self.scene():
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item.uid == self.model.linked_uid:
                    if abs(item.model.start - self.model.start) > 0.001:
                        is_out_of_sync = True
                        break
        clip_color = getattr(self.model, 'color', '#5D5D5D')
        ClipPainter.draw_base_rect(painter, rect, is_audio, is_out_of_sync, self.is_colliding, clip_color)
        ClipPainter.draw_thumbnails(painter, rect, self.thumbnail_start, self.thumbnail_end, self.model)
        if not is_audio:
            ClipPainter.draw_trim_handles(painter, rect)
        ClipPainter.draw_waveform(painter, rect, self.waveform_pixmap, self.model, self.scale)
        ClipPainter.draw_fades(painter, rect, self.model, self.scale)
        ClipPainter.draw_selection_border(painter, rect, self.isSelected(), is_out_of_sync)
        painter.setPen(QPen(QColor(255, 50, 50) if is_out_of_sync else Qt.white))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        display_name = f"⚠️ {self.name}" if is_out_of_sync else self.name
        painter.drawText(8, 15, display_name)
        painter.end()

    def paint(self, painter, option, widget):
        """Goal 15: Occlusion-aware rendering to save GPU cycles."""
        if not self.isVisible():
            return
        if self.scene() and self.model.media_type == 'video':
            for item in self.scene().items(self.scenePos()):
                if isinstance(item, ClipItem) and item != self:
                    if item.track < self.track and item.model.media_type == 'video':
                        if item.rect().contains(item.mapFromItem(self, self.rect().topLeft())) and \
                           item.rect().contains(item.mapFromItem(self, self.rect().bottomRight())):
                            return
        if not self.cached_pixmap:
            self.update_cache()
        if self.cached_pixmap and not self.cached_pixmap.isNull():
            painter.drawPixmap(0, 0, self.cached_pixmap)

    def mousePressEvent(self, event):
        self._is_interacting = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_interacting = False
        self.update_cache()
        super().mouseReleaseEvent(event)

    def set_speed(self, speed):
        """Goal 2: Change speed with strict bidirectional collision detection.
        Freeze frames are not affected by speed changes."""
        if speed <= 0:
            return
        # Calculate playable duration (excluding freeze frames)
        playable_duration = self.model.duration - self.model.start_freeze - self.model.end_freeze
        if playable_duration <= 0:
            # Only freeze frames, speed change has no effect
            return
        source_playable_duration = playable_duration * self.model.speed
        new_playable_duration = source_playable_duration / speed
        new_duration = new_playable_duration + self.model.start_freeze + self.model.end_freeze
        new_start = self.model.start
        new_end = new_start + new_duration
        if self.scene():
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item != self and item.track == self.track:
                    n_start = item.model.start
                    n_end = n_start + item.model.duration + item.model.start_freeze + item.model.end_freeze
                    if (new_start < n_end - 0.001) and (new_end > n_start + 0.001):
                        self.logger.warning(f"[COLLISION] Speed change blocked. Overlap with '{item.name}' [{n_start:.2f}s - {n_end:.2f}s]")
                        return
        self.speed = speed
        self.model.speed = speed
        self.model.duration = new_duration
        self.duration = new_duration
        self.setRect(0, 0, new_duration * self.scale, constants.TRACK_HEIGHT)
        self.update_cache()

    def set_volume(self, volume):
        self.volume = volume
        self.model.volume = volume
        self.update_cache()
