from PyQt5.QtWidgets import QGraphicsRectItem, QGraphicsItem, QGraphicsDropShadowEffect
from PyQt5.QtGui import QBrush, QColor, QPen, QFont, QLinearGradient, QPixmap
from PyQt5.QtCore import Qt, QRectF, QPointF
from model import ClipModel

class ClipItem(QGraphicsRectItem):
    def __init__(self, model: ClipModel, scale=50):
        super().__init__(0, 0, model.duration * scale, 30)
        self.model = model
        self.uid = model.uid
        self.name = model.name
        self.start = model.start
        self.duration = model.duration
        self.track = model.track
        self.speed = model.speed
        self.volume = model.volume
        self.scale = scale
        self.setPos(self.start * scale, self.track * 40 + 35)
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

    def paint(self, painter, option, widget):
        rect = self.rect()
        grad = QLinearGradient(0, 0, 0, rect.height())
        if self.isSelected():
            grad.setColorAt(0, QColor(70, 130, 180))
            grad.setColorAt(1, QColor(50, 100, 150))
        else:
            grad.setColorAt(0, QColor(50, 50, 50))
            grad.setColorAt(1, QColor(30, 30, 30))
        painter.setBrush(QBrush(grad))
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 215, 0), 2))
        else:
            painter.setPen(QPen(QColor(10, 10, 10), 1))
        painter.drawRoundedRect(rect, 4, 4)
        if self.model.width > 0 and self.thumbnail_start:
            thumb_h = rect.height()
            thumb_w = int(self.thumbnail_start.width() * (thumb_h / self.thumbnail_start.height()))
            current_x = 0
            while current_x < rect.width():
                target = QRectF(current_x, 0, thumb_w, thumb_h)
                pm = self.thumbnail_start
                if self.thumbnail_end and (int(current_x / thumb_w) % 2 == 1):
                    pm = self.thumbnail_end
                painter.setOpacity(1.0)
                painter.drawPixmap(target, pm, QRectF(pm.rect()))
                current_x += thumb_w
        if self.waveform_pixmap:
            # Calculate the visual width of the ENTIRE source file
            src_dur = getattr(self.model, 'source_duration', self.model.duration)
            # Safety: source_duration cannot be less than current clip duration
            src_dur = max(src_dur, self.model.duration)
            
            full_source_width = src_dur * self.scale
            
            # Shift left based on where we sliced the file
            x_offset = -(self.model.source_in * self.scale)
            
            # Clip the drawing to the item's visible area so it doesn't spill
            painter.save()
            painter.setClipRect(rect)
            painter.setOpacity(0.8)
            
            # Draw the full waveform at the calculated offset
            target_rect = QRectF(x_offset, 0, full_source_width, rect.height())
            painter.drawPixmap(target_rect.toRect(), self.waveform_pixmap)
            
            painter.restore()

        fi_w = self.model.fade_in * self.scale
        if fi_w > 0:
            grad = QLinearGradient(0, 0, fi_w, 0)
            grad.setColorAt(0, QColor(0, 0, 0, 200))
            grad.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(QRectF(0, 0, fi_w, rect.height()), grad)
        fo_w = self.model.fade_out * self.scale
        if fo_w > 0:
            x_start = rect.width() - fo_w
            grad = QLinearGradient(x_start, 0, rect.width(), 0)
            grad.setColorAt(0, QColor(0, 0, 0, 0))
            grad.setColorAt(1, QColor(0, 0, 0, 200))
            painter.fillRect(QRectF(x_start, 0, fo_w, rect.height()), grad)
        # Fade Handles: Red and Distinct
        painter.setPen(QPen(Qt.black, 1))
        painter.setBrush(QColor(255, 30, 30)) # Bright Red
        
        # Increased radius to 6 (12px diameter) for visibility
        painter.drawEllipse(QPointF(fi_w, 6), 6, 6)
        painter.drawEllipse(QPointF(rect.width() - fo_w, 6), 6, 6)
        
        painter.setOpacity(1.0)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        painter.drawText(int(fi_w) + 8, 15, self.name)
        if self.scene():
            my_scene_rect = self.sceneBoundingRect()
            i_am_video = self.model.width > 0
            painter.setBrush(QColor(0, 0, 0, 160))
            painter.setPen(Qt.NoPen)
            for item in self.scene().items():
                if isinstance(item, ClipItem) and item != self and item.track > self.track:
                    them_video = item.model.width > 0
                    if i_am_video != them_video: continue 
                    other_rect = item.sceneBoundingRect()
                    intersect = my_scene_rect.intersected(other_rect)
                    if not intersect.isEmpty():
                        local_intersect = self.mapFromScene(intersect).boundingRect()
                        painter.drawRect(local_intersect)

    def hoverMoveEvent(self, event):
        # Edge detection for trim cursor
        pos = event.pos()
        rect = self.rect()
        margin = 10  # 10px interaction zone
        
        # Check Fade Handles first (priority)
        fi_x = self.model.fade_in * self.scale
        fo_x = rect.width() - (self.model.fade_out * self.scale)
        
        if (abs(pos.x() - fi_x) < 15 and abs(pos.y() - 6) < 15) or \
           (abs(pos.x() - fo_x) < 15 and abs(pos.y() - 6) < 15):
            self.setCursor(Qt.PointingHandCursor)
        elif pos.x() < margin:
            self.setCursor(Qt.SizeHorCursor)  # Trim Start
        elif pos.x() > rect.width() - margin:
            self.setCursor(Qt.SizeHorCursor)  # Trim End
        else:
            self.setCursor(Qt.ArrowCursor)    # Move
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        # Z-Index: Bring to front when clicked
        for item in self.scene().items():
            item.setZValue(0)
        self.setZValue(10)
        
        pos = event.pos()
        rect = self.rect()
        margin = 10
        
        # 0. Check Slip Tool (Alt + Drag on body)
        if event.modifiers() & Qt.AltModifier:
            self.drag_mode = 'slip'
            self.initial_x = event.scenePos().x()
            self.initial_source_in = self.model.source_in
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return

        # 1. Check Fade Handles
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

        # 2. Check Trimming Edges
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
        if self.drag_mode == 'slip':
            # Slip Edit: Keep clip in place, scroll the content
            diff = event.scenePos().x() - self.initial_x
            diff_sec = diff / self.scale
            
            # Inverse: dragging right moves content left (earlier time)
            new_source_in = self.initial_source_in - diff_sec
            
            # Boundary checks
            src_dur = getattr(self.model, 'source_duration', self.model.duration + 100)
            if new_source_in < 0: new_source_in = 0
            if new_source_in + self.model.duration > src_dur:
                new_source_in = src_dur - self.model.duration
            
            self.model.source_in = new_source_in
            self.update() # Redraw waveform
            return

        elif self.drag_mode == 'trim_start':
            delta = event.pos().x()
            max_delta = (self.model.duration - 0.1) * self.scale
            delta = min(delta, max_delta)
            
            new_dur = self.model.duration - (delta / self.scale)
            new_start = self.model.start + (delta / self.scale)
            new_source_in = self.model.source_in + (delta / self.scale)
            
            if new_source_in < 0: return 

            self.setPos(new_start * self.scale, self.y())
            self.setRect(0, 0, new_dur * self.scale, 30)
            self.model.start = new_start
            self.model.duration = new_dur
            self.model.source_in = new_source_in
            self.update()
            
        elif self.drag_mode == 'trim_end':
            new_width = max(5, event.pos().x())
            new_dur = new_width / self.scale
            src_dur = getattr(self.model, 'source_duration', 99999)
            if self.model.source_in + new_dur > src_dur:
                new_dur = src_dur - self.model.source_in
                new_width = new_dur * self.scale
            
            self.setRect(0, 0, new_width, 30)
            self.model.duration = new_dur
            self.update()

        elif self.drag_mode == 'fade_in':
            x = max(0, event.pos().x())
            val = x / self.scale
            self.model.fade_in = min(val, self.model.duration / 2)
            self.update()
        elif self.drag_mode == 'fade_out':
            x = min(self.rect().width(), event.pos().x())
            val = (self.rect().width() - x) / self.scale
            self.model.fade_out = min(val, self.model.duration / 2)
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        
        # 1. Resolve Overlaps (Strict Anti-Collision)
        if self.scene():
            safe = False
            iterations = 0
            while not safe and iterations < 5:
                # Find anyone I am currently overlapping on the same track
                collisions = [i for i in self.scene().items() 
                              if isinstance(i, ClipItem) and i != self 
                              and i.track == self.track and i.collidesWithItem(self)]
                
                if not collisions:
                    safe = True
                else:
                    # I hit someone. Jump to their closest edge (Start or End).
                    obstacle = collisions[0]
                    obs_start = obstacle.x()
                    obs_end = obstacle.x() + obstacle.rect().width()
                    my_center = self.x() + (self.rect().width() / 2)
                    obs_center = obs_start + (obstacle.rect().width() / 2)
                    
                    if my_center > obs_center:
                        # Closer to the right -> Snap to End (Append)
                        self.setX(obs_end)
                    else:
                        # Closer to the left -> Snap to Start (Prepend)
                        # Ensure we don't go below 0
                        new_x = max(0, obs_start - self.rect().width())
                        self.setX(new_x)
                    iterations += 1

        # 2. Finalize Data
        self.start = self.x() / self.scale
        self.model.start = self.start
        self.model.track = self.track
        
        if self.scene() and self.scene().views():
            view = self.scene().views()[0]
            if view.snap_line:
                view.scene.removeItem(view.snap_line)
                view.snap_line = None
            view.fit_to_view()

    def cleanup(self):
        # Memory Leak Fix
        self.waveform_pixmap = None
        self.thumbnail_start = None
        self.thumbnail_end = None

    def set_speed(self, value):
        self.model.speed = value
        self.speed = value

    def set_volume(self, value):
        self.model.volume = value
        self.volume = value
