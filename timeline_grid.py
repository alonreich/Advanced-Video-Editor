from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF
from PyQt5.QtCore import QRectF, QPointF

class TimelineGridPainter:
    def __init__(self, ruler_height=30):
        self.ruler_height = ruler_height

    def draw_foreground(self, painter, rect, scale_factor, view_port_info, playhead_pos):
        ruler_rect = QRectF(rect.left(), 0, rect.width(), self.ruler_height)
        painter.fillRect(ruler_rect, QColor(25, 25, 25))
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawLine(int(rect.left()), self.ruler_height, int(rect.right()), self.ruler_height)
        start_x, end_x = rect.left(), rect.right()
        start_sec_raw = max(0, start_x / scale_factor)
        end_sec_raw = end_x / scale_factor
        pixels_per_second = scale_factor
        units = [1, 5, 10, 30, 60, 120, 300, 600, 1800, 3600]
        major_step_sec = units[0]
        for unit in units:
            if pixels_per_second * unit > 80:
                major_step_sec = unit
                break
        minor_step_sec = major_step_sec / 5.0
        start_unit = int(start_sec_raw / minor_step_sec) * minor_step_sec
        sec = start_unit
        if 'font' in view_port_info:
            painter.setFont(view_port_info['font'])
        while sec < end_sec_raw:
            vp_x = sec * scale_factor
            if vp_x >= start_x and vp_x <= end_x:
                is_major = (sec % major_step_sec) < 0.001
                tick_h = 15 if is_major else 8
                color = QColor(220, 220, 220) if is_major else QColor(150, 150, 150)
                painter.setPen(color)
                painter.drawLine(int(vp_x), self.ruler_height - tick_h, int(vp_x), self.ruler_height)
                if is_major:
                    mins = int(sec // 60)
                    secs = int(sec % 60)
                    ts = f"{mins:02}:{secs:02}"
                    painter.drawText(int(vp_x) + 4, 12, ts)
            sec += minor_step_sec
        playhead_x = playhead_pos * scale_factor
        if playhead_x >= rect.left() and playhead_x <= rect.right():
            painter.setPen(QPen(QColor(255, 0, 0), 1))
            painter.drawLine(int(playhead_x), 0, int(playhead_x), int(rect.height()))
            painter.setBrush(QBrush(QColor(255, 0, 0)))
            poly = QPolygonF([
                QPointF(playhead_x - 7, 0),
                QPointF(playhead_x + 7, 0),
                QPointF(playhead_x, 15)
            ])
            painter.drawPolygon(poly)
    
    def draw_razor_indicator(self, painter, rect, x_pos):
        """Draws a vertical dashed line at the potential cut point."""
        painter.save()
        pen = QPen(QColor(255, 255, 0, 180), 1, Qt.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(x_pos), 0, int(x_pos), int(rect.height()))
        painter.setBrush(QColor(255, 255, 0))
        painter.setPen(Qt.NoPen)
        painter.drawRect(int(x_pos) - 2, 0, 4, self.ruler_height)
        painter.restore()
