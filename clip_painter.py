from PyQt5.QtGui import QPainter, QLinearGradient, QColor, QBrush, QPen, QPixmap, QFont
from PyQt5.QtCore import Qt, QRectF

class ClipPainter:
    @staticmethod
    def draw_base_rect(painter, rect, is_audio, is_out_of_sync=False, is_colliding=False):
        """Draws the background fill only."""
        grad = QLinearGradient(0, 0, 0, rect.height())
        if is_colliding:
            grad.setColorAt(0, QColor(255, 60, 60))
            grad.setColorAt(1, QColor(140, 0, 0))
        elif is_out_of_sync:
            grad.setColorAt(0, QColor(180, 40, 40))
            grad.setColorAt(1, QColor(100, 20, 20))
        elif is_audio:
            grad.setColorAt(0, QColor(40, 80, 50))
            grad.setColorAt(1, QColor(20, 50, 30))
        else:
            grad.setColorAt(0, QColor(50, 50, 50))
            grad.setColorAt(1, QColor(30, 30, 30))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, int(rect.width()), int(rect.height()), 4, 4)

    @staticmethod
    def draw_selection_border(painter, rect, is_selected, is_out_of_sync):
        """Draws the border on top of everything else."""
        border_color = QColor(10, 10, 10)
        border_width = 1
        if is_selected:
            border_color = QColor(255, 215, 0)
            border_width = 3
        elif is_out_of_sync:
            border_color = QColor(255, 0, 0)
            border_width = 2
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(border_color, border_width))
        painter.drawRoundedRect(0, 0, int(rect.width()), int(rect.height()), 4, 4)

    @staticmethod
    def draw_waveform(painter, rect, pixmap, model, scale):
        if not pixmap or model.media_type != 'audio': return
        src_dur = getattr(model, 'source_duration', model.duration)
        src_dur = max(src_dur, model.duration)
        full_w = src_dur * scale
        x_offset = -(model.source_in * scale)
        painter.save()

        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setClipRect(0, 0, int(rect.width()), int(rect.height()))
        painter.setOpacity(0.8)
        target = QRectF(x_offset, 0, full_w, rect.height())
        painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))
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

    @staticmethod
    def draw_trim_handles(painter, rect):
        """Goal 8: Split-zone handles. Top=Trim/Freeze, Bottom=Fade."""
        w = 10
        h = int(rect.height())
        half_h = h // 2

        painter.setBrush(QColor(255, 255, 0, 150))
        painter.drawRect(0, 0, w, half_h)
        painter.drawRect(int(rect.width() - w), 0, w, half_h)

        painter.setBrush(QColor(0, 255, 255, 180))
        painter.drawRect(0, half_h, w, half_h)
        painter.drawRect(int(rect.width() - w), half_h, w, half_h)

    @staticmethod
    def draw_proxy_indicator(painter, rect):
        """Draws a Cyan 'P' badge in the top-right corner."""
        size = 16
        margin = 4
        badge_rect = QRectF(rect.width() - size - margin, margin, size, size)
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 255, 255, 180))
        painter.drawRoundedRect(badge_rect, 4, 4)
        painter.setPen(QColor(0, 0, 0))
        f = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(f)
        painter.drawText(badge_rect, Qt.AlignCenter, "P")
        painter.restore()