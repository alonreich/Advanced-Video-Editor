from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QBrush, QPen, QPixmap
from PyQt5.QtCore import Qt, QRectF

class ClipPainter:
    @staticmethod
    def draw_base_rect(painter, rect, is_selected, is_audio, is_out_of_sync=False):
        grad = QLinearGradient(0, 0, 0, rect.height())
        if is_out_of_sync:
            grad.setColorAt(0, QColor(180, 40, 40))
            grad.setColorAt(1, QColor(100, 20, 20))
            border = QColor(255, 0, 0)
            width = 2
        elif is_selected:
            grad.setColorAt(0, QColor(70, 130, 180))
            grad.setColorAt(1, QColor(50, 100, 150))
            border = QColor(255, 215, 0)
            width = 2
        elif is_audio:
            grad.setColorAt(0, QColor(40, 80, 50))
            grad.setColorAt(1, QColor(20, 50, 30))
            border = QColor(10, 10, 10)
            width = 1
        else:
            grad.setColorAt(0, QColor(50, 50, 50))
            grad.setColorAt(1, QColor(30, 30, 30))
            border = QColor(10, 10, 10)
            width = 1
        painter.setBrush(QBrush(grad))
        painter.setPen(QPen(border, width))
        painter.drawRoundedRect(0, 0, int(rect.width()), int(rect.height()), 4, 4)
    @staticmethod
    def draw_waveform(painter, rect, pixmap, model, scale):
        if not pixmap or model.media_type != 'audio': return
        src_dur = getattr(model, 'source_duration', model.duration)
        src_dur = max(src_dur, model.duration)
        full_w = src_dur * scale
        x_offset = -(model.source_in * scale)
        painter.save()
        painter.setClipRect(0, 0, int(rect.width()), int(rect.height()))
        painter.setOpacity(0.8)
        painter.drawPixmap(int(x_offset), 0, int(full_w), int(rect.height()), pixmap)
        painter.restore()
    @staticmethod
    def draw_thumbnails(painter, rect, start_pm, end_pm, model):
        if model.media_type != 'video' or not start_pm: return
        thumb_h = rect.height()
        aspect = start_pm.width() / start_pm.height()
        correct_w = thumb_h * aspect
        painter.save()
        painter.setClipRect(0, 0, int(rect.width()), int(rect.height()))
        current_x = 0
        idx = 0
        while current_x < rect.width():
            pm = start_pm
            if end_pm and (idx % 2 == 1): pm = end_pm
            target = QRectF(current_x, 0, correct_w, thumb_h)
            source = QRectF(pm.rect())
            painter.drawPixmap(target, pm, source)
            current_x += correct_w
            idx += 1
        painter.restore()
    @staticmethod
    def draw_fades(painter, rect, model, scale):
        fi_w = model.fade_in * scale
        fo_w = model.fade_out * scale
        if fi_w > 0:
            g = QLinearGradient(0, 0, fi_w, 0)
            g.setColorAt(0, QColor(0,0,0,200))
            g.setColorAt(1, QColor(0,0,0,0))
            painter.fillRect(QRectF(0, 0, fi_w, rect.height()), g)
        if fo_w > 0:
            x_s = rect.width() - fo_w
            g = QLinearGradient(x_s, 0, rect.width(), 0)
            g.setColorAt(0, QColor(0,0,0,0))
            g.setColorAt(1, QColor(0,0,0,200))
            painter.fillRect(QRectF(x_s, 0, fo_w, rect.height()), g)
