import math

from PyQt6.QtCore import QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from src.infrastructure.config import load_data
from src.infrastructure.signals import signals


class RoughBoxWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.offset = 0.0
        self.rough_slide = 1.0

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.animate_border)

        # Cache visuals to avoid reading file in paintEvent
        self.bg_alpha = 150
        self.roughness_base = 1.0

        signals.update_data.connect(self.update_config)
        self.update_config()

    def update_config(self):
        try:
            d = load_data()
            vis = d.get("global_config", {}).get("visuals", {})
            self.bg_alpha = vis.get("bg_alpha", 150)
            self.roughness_base = vis.get("rough_slide", 1.0)
            self.animation_enabled = vis.get("animation_enabled", True)

            if not self.animation_enabled:
                # Pause animation but preserve 'should_animate' state
                if self.anim_timer.isActive():
                    self.anim_timer.stop()
            elif hasattr(self, "should_animate") and self.should_animate:
                self.start_animation()

            self.update()
        except:
            pass

    def start_animation(self):
        self.should_animate = True
        if not hasattr(self, "animation_enabled") or self.animation_enabled:
            if not self.anim_timer.isActive():
                self.anim_timer.start(50)  # 20 FPS

    def stop_animation(self):
        self.should_animate = False
        self.anim_timer.stop()

    border_path_update = pyqtSignal(object)

    def animate_border(self):
        self.offset += 0.5
        # signals.border_frame_update.emit(self.offset) # Disabled as web slide no longer needs it

        # Calculate path for listeners (masking)
        if self.receivers(self.border_path_update) > 0:
            # Increased padding to prevent clipping of the rough border
            rect = QRectF(self.rect().adjusted(5, 5, -5, -5))
            path = RoughBoxWidget.get_rough_path(rect, self.offset, self.roughness_base)
            self.border_path_update.emit(path)

        self.update()

    def cleanup(self):
        self.anim_timer.stop()

    def draw_rough_box(
        self,
        painter,
        rect,
        fill=True,
        intensity=1.0,
        title=None,
        color=None,
        rough=True,
        radius=10,
    ):
        # Use cached values
        bg_alpha = self.bg_alpha
        roughness = self.roughness_base * intensity

        if color is None:
            color = QColor("white")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if fill and not rough:
            painter.setBrush(QColor(0, 0, 0, bg_alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, radius, radius)
        elif not fill:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        if not rough:
            # Just draw smooth border
            painter.setPen(QPen(color, 2))
            painter.drawRoundedRect(rect, radius, radius)

            if title:
                painter.setPen(color)
                font = painter.font()
                font.setBold(True)
                font.setPointSize(12)
                painter.setFont(font)
                painter.drawText(
                    rect.adjusted(10, 10, -10, -10),
                    Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                    title,
                )

            painter.restore()
            return

        # Rough Border Logic
        path = RoughBoxWidget.get_rough_path(rect, self.offset, roughness)

        if fill:
            painter.setBrush(QColor(0, 0, 0, bg_alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        pen = QPen(color, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(path)

        if title:
            painter.setPen(color)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(12)
            painter.setFont(font)
            painter.drawText(
                rect.adjusted(10, 10, -10, -10),
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
                title,
            )

        painter.restore()

    @staticmethod
    def get_rough_path(rect, offset, roughness):
        path = QPainterPath()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        steps = int(max(w, h) / 5)
        path.moveTo(x, y)

        amplitude = 2.0 * roughness
        freq = 0.5

        # Top
        for i in range(steps + 1):
            t = i / steps
            px = x + w * t
            py = y + math.sin(t * 10 + offset * freq) * amplitude
            if i == 0:
                path.moveTo(px, py)
            else:
                path.lineTo(px, py)

        # Right
        for i in range(steps + 1):
            t = i / steps
            py = y + h * t
            px = x + w + math.sin(t * 10 + offset * freq + 2.0) * amplitude
            path.lineTo(px, py)

        # Bottom
        for i in range(steps + 1):
            t = i / steps
            px = x + w - (w * t)
            py = y + h + math.sin(t * 10 + offset * freq + 4.0) * amplitude
            path.lineTo(px, py)

        # Left
        for i in range(steps + 1):
            t = i / steps
            py = y + h - (h * t)
            px = x + math.sin(t * 10 + offset * freq + 6.0) * amplitude
            path.lineTo(px, py)

        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        # Increased padding to prevent clipping
        rect = QRectF(self.rect().adjusted(5, 5, -5, -5))
        self.draw_rough_box(
            painter, rect, fill=True, intensity=1.0, rough=True, radius=10
        )
