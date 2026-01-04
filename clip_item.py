import time
from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QPixmap, QPainter, QFont, QPen
from PyQt5.QtCore import Qt, QPointF
from model import ClipModel
from clip_painter import ClipPainter

class ClipItem(QGraphicsRectItem):
    def __init__(self, model: ClipModel, scale=50):
        super().__init__(0, 0, model.duration * scale, 30)
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
        self.setPos(self.start * scale, self.track * 40 + 32)
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

    def update_collision_cache(self):
        self.cached_collisions = []
        if not self.scene(): 
            return
        my_scene_rect = self.sceneBoundingRect()
        items = self.scene().items(my_scene_rect, Qt.IntersectsItemShape)
        is_my_type_video = getattr(self.model, 'media_type', 'video') == 'video'
        for item in items:
            if isinstance(item, ClipItem) and item != self and item.track > self.track:
                is_their_type_video = getattr(item.model, 'media_type', 'video') == 'video'
                if is_my_type_video != is_their_type_video: 
                    continue
                other_rect = item.sceneBoundingRect()
                intersect = my_scene_rect.intersected(other_rect)
                if not intersect.isEmpty():
                    local_intersect = self.mapFromScene(intersect).boundingRect()
                    self.cached_collisions.append(local_intersect)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged:
            self.update_cache()
        return super().itemChange(change, value)

    def update_cache(self):
        """Offloads drawing to ClipPainter and caches result."""
        now = time.time()
        if self._is_interacting and (now - self._last_render_time) < 0.033:
            return
        self._last_render_time = now
        rect = self.rect()
        if rect.width() <= 0 or rect.height() <= 0: 
            return
        self.cached_pixmap = QPixmap(int(rect.width()), int(rect.height()))
        self.cached_pixmap.fill(Qt.transparent)
        painter = QPainter(self.cached_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        is_audio = getattr(self.model, 'media_type', 'video') == 'audio'
        ClipPainter.draw_base_rect(painter, rect, self.isSelected(), is_audio)
        if not self._is_interacting:
            ClipPainter.draw_thumbnails(painter, rect, self.thumbnail_start, self.thumbnail_end, self.model)
            ClipPainter.draw_waveform(painter, rect, self.waveform_pixmap, self.model, self.scale)
            ClipPainter.draw_fades(painter, rect, self.model, self.scale)
        is_out_of_sync = False
        if self.model.linked_uid:
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item.uid == self.model.linked_uid:
                    if abs(item.model.start - self.model.start) > 0.001 or \
                        abs(item.model.source_in - self.model.source_in) > 0.001:
                        is_out_of_sync = True
                    break
        painter.setPen(QColor(255, 50, 50) if is_out_of_sync else Qt.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        fi_w = self.model.fade_in * self.scale
        display_name = f"⚠️ {self.name} [OUT OF SYNC]" if is_out_of_sync else self.name
        painter.drawText(int(fi_w) + 8, 15, display_name)
        painter.end()

    def paint(self, painter, option, widget):
        if not self.cached_pixmap:
            self.update_cache()
        if self.cached_pixmap and not self.cached_pixmap.isNull():
            painter.drawPixmap(0, 0, self.cached_pixmap)
        rect = self.rect()
        fi_w = self.model.fade_in * self.scale
        fo_w = self.model.fade_out * self.scale
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QColor(255, 30, 30))
        painter.drawEllipse(QPointF(fi_w, 6), 6, 6)
        painter.drawEllipse(QPointF(rect.width() - fo_w, 6), 6, 6)
        if hasattr(self, 'cached_collisions'):
            painter.setBrush(QColor(0, 0, 0, 128))
            painter.setPen(Qt.NoPen)
            for col_rect in self.cached_collisions:
                painter.drawRect(col_rect)

    def hoverMoveEvent(self, event):
        pos = event.pos()
        rect = self.rect()
        margin = 10
        fi_x = self.model.fade_in * self.scale
        fo_x = rect.width() - (self.model.fade_out * self.scale)
        if (abs(pos.x() - fi_x) < 15 and abs(pos.y() - 6) < 15) or \
            (abs(pos.x() - fo_x) < 15 and abs(pos.y() - 6) < 15):
            self.setCursor(Qt.PointingHandCursor)
        elif pos.x() < margin or pos.x() > rect.width() - margin:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self._is_interacting = True
        for item in self.scene().items():
            item.setZValue(0)
        self.setZValue(10)
        if getattr(self.model, 'locked', False):
            event.ignore()
            return
        pos = event.pos()
        rect = self.rect()
        margin = 10
        if event.modifiers() & Qt.AltModifier:
            self.drag_mode = 'slip'
            self.initial_x = event.scenePos().x()
            self.initial_source_in = self.model.source_in
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        fi_x = self.model.fade_in * self.scale
        fo_x = rect.width() - (self.model.fade_out * self.scale)
        if abs(pos.x() - fi_x) < 15 and abs(pos.y() - 6) < 15:
            self.drag_mode = 'fade_in'
            event.accept()
            return
        elif abs(pos.x() - fo_x) < 15 and abs(pos.y() - 6) < 15:
            self.drag_mode = 'fade_out'
            event.accept()
            return
        if pos.x() < margin:
            self.drag_mode = 'trim_start'
            self.initial_x = self.pos().x()
            self.initial_width = rect.width()
            self.initial_start = self.model.start
            self.initial_dur = self.model.duration
            self.initial_source_in = self.model.source_in
            event.accept()
        elif pos.x() > rect.width() - margin:
            self.drag_mode = 'trim_end'
            self.initial_width = rect.width()
            event.accept()
        else:
            self.drag_mode = 'move'
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        needs_update = False
        if self.drag_mode == 'slip':
            diff = event.scenePos().x() - self.initial_x
            diff_sec = diff / self.scale
            new_source_in = self.initial_source_in - diff_sec
            src_dur = getattr(self.model, 'source_duration', self.model.duration + 100)
            if new_source_in < 0: 
                new_source_in = 0
            if new_source_in + self.model.duration > src_dur:
                new_source_in = src_dur - self.model.duration
            self.model.source_in = new_source_in
            needs_update = True
        elif self.drag_mode == 'trim_start':
            delta = event.pos().x()
            max_delta = (self.model.duration - 0.1) * self.scale
            delta = min(delta, max_delta)
            new_dur = self.model.duration - (delta / self.scale)
            new_start = self.model.start + (delta / self.scale)
            new_source_in = self.model.source_in + (delta / self.scale)
            if new_source_in >= 0:
                self.setPos(new_start * self.scale, self.y())
                self.setRect(0, 0, new_dur * self.scale, 30)
                self.model.start = new_start
                self.model.duration = new_dur
                self.model.source_in = new_source_in
                needs_update = True
        elif self.drag_mode == 'trim_end':
            new_width = max(5, event.pos().x())
            new_dur = new_width / self.scale
            src_dur = getattr(self.model, 'source_duration', 99999)
            if self.model.source_in + new_dur > src_dur:
                new_dur = src_dur - self.model.source_in
                new_width = new_dur * self.scale
            self.setRect(0, 0, new_width, 30)
            self.model.duration = new_dur
            needs_update = True
        elif self.drag_mode == 'fade_in':
            x = max(0, event.pos().x())
            val = x / self.scale
            self.model.fade_in = min(val, self.model.duration / 2)
            needs_update = True
        elif self.drag_mode == 'fade_out':
            x = min(self.rect().width(), event.pos().x())
            val = (self.rect().width() - x) / self.scale
            self.model.fade_out = min(val, self.model.duration / 2)
            needs_update = True
        else:
            old_pos = self.pos()
            super().mouseMoveEvent(event)
            current_track = round((self.y() - 32) / 40)
            my_width = self.rect().width()
            for other in self.scene().items():
                if isinstance(other, ClipItem) and other != self and other.track == current_track:
                    other_rect = other.sceneBoundingRect()
                    if self.sceneBoundingRect().intersects(other_rect):
                        if old_pos.x() + my_width <= other_rect.left():
                            self.setX(other_rect.left() - my_width)
                        elif old_pos.x() >= other_rect.right():
                            self.setX(other_rect.right())
            if self.model.linked_uid:
                delta_x = self.x() - old_pos.x()
                for item in self.scene().items():
                    if isinstance(item, ClipItem) and item.uid == self.model.linked_uid:
                        item.setX(item.x() + delta_x)
                        break
        if needs_update:
            self.update_cache()
            self.update()

    def mouseReleaseEvent(self, event):
        self._is_interacting = False
        super().mouseReleaseEvent(event)
        if self.x() < 10: 
            self.setX(0)
        current_track_idx = round((self.y() - 35) / 40)
        if current_track_idx < 0: 
            current_track_idx = 0
        snapped_y = current_track_idx * 40 + 35
        self.setY(snapped_y)
        self.track = current_track_idx
        if self.scene():
            safe = False
            iterations = 0
            while not safe and iterations < 10:
                collisions = [i for i in self.scene().items() 
                    if isinstance(i, ClipItem) and i != self 
                    and i.track == self.track and i.collidesWithItem(self)]
                if not collisions:
                    safe = True
                else:
                    obstacle = collisions[0]
                    obs_start = obstacle.x()
                    obs_end = obstacle.x() + obstacle.rect().width()
                    my_center = self.x() + (self.rect().width() / 2)
                    obs_center = obs_start + (obstacle.rect().width() / 2)
                    if my_center > obs_center:
                        self.setX(obs_end)
                    else:
                        new_x = max(0, obs_start - self.rect().width())
                        self.setX(new_x)
                    iterations += 1
        self.start = self.x() / self.scale
        self.model.start = self.start
        self.model.track = self.track
        if self.model.linked_uid:
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item.uid == self.model.linked_uid:
                    item.start = item.x() / item.scale
                    item.model.start = item.start
                    item.update_cache()
                    break
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            if view.snap_line:
                view.scene.removeItem(view.snap_line)
                view.snap_line = None
            view.fit_to_view()
            view.compact_lanes()
        self.update_cache()
        self.update_collision_cache()

    def cleanup(self):
        self.waveform_pixmap = None
        self.thumbnail_start = None
        self.thumbnail_end = None
        self.cached_pixmap = None

    def set_speed(self, value):
        self.model.speed = value
        self.speed = value
        self.update_cache()

    def set_volume(self, value):
        self.model.volume = value
        self.volume = value

    def contextMenuEvent(self, event):
        """Right-click menu for track linking and separation."""
        from PyQt5.QtWidgets import QMenu
        menu = QMenu()
        link_action = None
        if self.model.linked_uid:
            link_action = menu.addAction("🔗 Unlink from Partner")
        else:
            link_action = menu.addAction("🔗 Link to Nearby Clip")
            link_action.setEnabled(False)
        action = menu.exec_(event.screenPos())
        if action == link_action and self.model.linked_uid:
            self.scene().views()[0].parent().mw.clip_ctrl.toggle_link(self.model.uid)
