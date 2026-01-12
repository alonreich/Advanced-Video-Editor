from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF, QPixmap, QPainter, QFont
from PyQt5.QtCore import QRectF, QPointF, Qt
import constants

class TimelineGridPainter:

    def __init__(self, ruler_height=constants.RULER_HEIGHT):
        self.ruler_height = ruler_height
        self._cache = None
        self.ms_font = QFont("Consolas", 8)
        self._cached_rect = None
        self._cached_rect = None
        self._cached_scale = 0

    def draw_foreground(self, painter, rect, scale_factor, view_port_info, playhead_pos):
        """Draws the cached static ruler and the dynamic playhead."""
        target_rect = QRectF(rect.left(), 0, rect.width(), self.ruler_height)
        if (self._cache is None or 
            self._cached_rect != target_rect or 
            abs(self._cached_scale - scale_factor) > 0.001):
            self._regenerate_cache(target_rect, scale_factor, view_port_info)
        if self._cache:
            painter.drawPixmap(int(target_rect.left()), 0, self._cache)
        self._draw_playhead(painter, rect, scale_factor, playhead_pos)

    def _regenerate_cache(self, rect, scale_factor, view_port_info):
        """Goal 18: Precision ruler generation with memory-safe allocation."""
        w = min(int(rect.width()), 8000) 
        h = self.ruler_height
        if w <= 0: return
        self._cache = QPixmap(w, h)
        self._cache.fill(QColor(constants.COLOR_BACKGROUND).lighter(150))
        self._cached_rect = rect
        self._cached_scale = scale_factor
        p = QPainter(self._cache)
        try:
            p.translate(-rect.left(), 0)
            p.setPen(QPen(QColor(150, 150, 150), 1))
            start_x, end_x = rect.left(), rect.right()
            p.drawLine(int(start_x), h, int(end_x), h)
            start_sec_raw = max(0, start_x / scale_factor)
            end_sec_raw = end_x / scale_factor
            units = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
            major_step_sec = units[-1]
            for unit in units:
                if (scale_factor * unit) >= 120:
                    major_step_sec = unit
                    break
                    break
            minor_step_sec = major_step_sec / 5.0
            i = int(start_sec_raw / minor_step_sec)
            sec = i * minor_step_sec
            if 'font' in view_port_info:
                p.setFont(view_port_info['font'])
            while sec < end_sec_raw:
                vp_x = sec * scale_factor
                if vp_x >= start_x and vp_x <= end_x:
                    is_major = (sec % major_step_sec) < 0.001
                    tick_h = 15 if is_major else 8
                    color = QColor(220, 220, 220) if is_major else QColor(150, 150, 150)
                    p.setPen(color)
                    p.drawLine(int(vp_x), h - tick_h, int(vp_x), h)
                    if is_major:
                        mins = int(sec // 60)
                        secs = int(sec % 60)
                        ts = f"{mins:02}:{secs:02}"
                        p.drawText(int(vp_x) + 4, 12, ts)
                sec += minor_step_sec
        finally:
            p.end()

    def _draw_playhead(self, painter, rect, scale_factor, playhead_pos):
        """Draws the red playhead line and triangle."""
        playhead_x = playhead_pos * scale_factor
        if playhead_x < rect.left() or playhead_x > rect.right():
            return
        painter.setPen(QPen(QColor(constants.COLOR_ERROR).lighter(50), 1))
        painter.drawLine(int(playhead_x), 0, int(playhead_x), int(rect.height()))
        painter.setFont(self.ms_font)
        ms_text = f"{int((playhead_pos % 1) * 1000):03}ms"
        painter.setPen(QColor(constants.COLOR_TEXT).lighter(100))
        painter.drawText(int(playhead_x) + 10, 25, ms_text)
        painter.setBrush(QBrush(QColor(constants.COLOR_ERROR).lighter(50)))
        poly = QPolygonF([
            QPointF(playhead_x - 7, 0),
            QPointF(playhead_x + 7, 0),
            QPointF(playhead_x, 15)
        ])
        painter.drawPolygon(poly)

    def draw_scene_markers(self, painter, rect, scale_factor, scene_times):
        """Draws high-visibility markers for detected video cuts."""
        painter.save()
        painter.setPen(QPen(QColor(0, 255, 255, 150), 2))
        for t in scene_times:
            x = t * scale_factor
            if rect.left() <= x <= rect.right():
                painter.drawLine(int(x), 0, int(x), self.ruler_height)
        painter.restore()

    def draw_razor_indicator(self, painter, rect, x_pos):
        """Goal 16: High-visibility Magnetic Razor Ghost line."""
        painter.save()
        pen = QPen(QColor(255, 255, 0, 255), 2, Qt.SolidLine)
        painter.setPen(pen)
        painter.drawLine(int(x_pos), 0, int(x_pos), int(rect.height()))
        painter.setBrush(QColor(255, 255, 0))
        painter.drawRect(int(x_pos) - 3, 0, 6, self.ruler_height)
        painter.restore()
        painter.setBrush(QColor(255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.drawRect(int(x_pos) - 1, 0, 2, self.ruler_height)
        painter.restore()