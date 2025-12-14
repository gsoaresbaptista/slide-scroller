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
            self.border_radius = vis.get("border_radius", 10.0)
            self.animation_enabled = vis.get("animation_enabled", True)

            # Load color inversion setting
            self.color_inverted = d.get("global_config", {}).get(
                "color_inverted", False
            )

            if not self.animation_enabled:
                if self.anim_timer.isActive():
                    self.anim_timer.stop()
            elif hasattr(self, "should_animate") and self.should_animate:
                self.start_animation()

            self.update()
        except Exception:
            pass

    def start_animation(self):
        self.should_animate = True
        if not hasattr(self, "animation_enabled") or self.animation_enabled:
            if not self.anim_timer.isActive():
                self.anim_timer.start(50)

    def stop_animation(self):
        self.should_animate = False
        self.anim_timer.stop()

    border_path_update = pyqtSignal(object)

    def animate_border(self):
        self.offset += 0.5

        if self.receivers(self.border_path_update) > 0:
            rect = QRectF(self.rect().adjusted(5, 5, -5, -5))
            path = RoughBoxWidget.get_rough_path(
                rect, self.offset, self.roughness_base, radius=self.border_radius
            )
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
        radius=None,
    ):
        bg_alpha = self.bg_alpha
        roughness = self.roughness_base * intensity

        if radius is None:
            radius = getattr(self, "border_radius", 10.0)

        inverted = getattr(self, "color_inverted", False)

        if color is None:
            color = QColor("black" if inverted else "white")

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Invert background color
        bg_color = (
            QColor(255, 255, 255, bg_alpha) if inverted else QColor(0, 0, 0, bg_alpha)
        )

        if fill and not rough:
            painter.setBrush(bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, radius, radius)
        elif not fill:
            painter.setBrush(Qt.BrushStyle.NoBrush)

        if not rough:
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

        path = RoughBoxWidget.get_rough_path(rect, self.offset, roughness, radius)

        if fill:
            painter.setBrush(bg_color)
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
    def get_rough_path(rect, offset, roughness, radius=10):
        path = QPainterPath()
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

        radius = min(radius, w / 2, h / 2)

        amplitude = 2.0 * roughness

        base_spatial_freq = 0.05
        time_freq = 0.5

        perimeter = 2 * (w - 2 * radius) + 2 * (h - 2 * radius) + 2 * math.pi * radius
        target_cycles = max(1, round(perimeter * base_spatial_freq / (2 * math.pi)))
        spatial_freq = (
            (target_cycles * 2 * math.pi) / perimeter
            if perimeter > 0
            else base_spatial_freq
        )

        def get_noise(d):
            return math.sin(d * spatial_freq + offset * time_freq) * amplitude

        current_d = 0.0

        # 1. Top Edge
        start_x = x + radius
        start_y = y
        path.moveTo(start_x, start_y - get_noise(0))

        len_top = w - 2 * radius
        steps_top = max(1, int(len_top / 5))

        for i in range(steps_top + 1):
            ft = i / steps_top
            dist_on_seg = len_top * ft

            noise = get_noise(current_d + dist_on_seg)

            px = start_x + dist_on_seg
            py = start_y - noise
            path.lineTo(px, py)

        current_d += len_top

        # 2. Top-Right Corner
        cx_tr = x + w - radius
        cy_tr = y + radius
        arc_len = math.pi * radius / 2
        steps_corner = max(1, int(arc_len / 3))

        for i in range(steps_corner + 1):
            ft = i / steps_corner
            dist_on_seg = arc_len * ft

            angle_rad = -math.pi / 2 + (math.pi / 2) * ft

            noise = get_noise(current_d + dist_on_seg)
            r_noisy = radius + noise

            px = cx_tr + r_noisy * math.cos(angle_rad)
            py = cy_tr + r_noisy * math.sin(angle_rad)
            path.lineTo(px, py)

        current_d += arc_len

        # 3. Right Edge
        start_y_right = y + radius
        len_right = h - 2 * radius
        steps_right = max(1, int(len_right / 5))

        for i in range(steps_right + 1):
            ft = i / steps_right
            dist_on_seg = len_right * ft

            noise = get_noise(current_d + dist_on_seg)

            px = x + w + noise
            py = start_y_right + dist_on_seg
            path.lineTo(px, py)

        current_d += len_right

        # 4. Bottom-Right Corner
        cx_br = x + w - radius
        cy_br = y + h - radius

        for i in range(steps_corner + 1):
            ft = i / steps_corner
            dist_on_seg = arc_len * ft

            angle_rad = 0 + (math.pi / 2) * ft

            noise = get_noise(current_d + dist_on_seg)
            r_noisy = radius + noise

            px = cx_br + r_noisy * math.cos(angle_rad)
            py = cy_br + r_noisy * math.sin(angle_rad)
            path.lineTo(px, py)

        current_d += arc_len

        # 5. Bottom Edge
        start_x_bottom = x + w - radius
        len_bottom = w - 2 * radius

        for i in range(steps_top + 1):
            ft = i / steps_top
            dist_on_seg = len_bottom * ft

            noise = get_noise(current_d + dist_on_seg)

            px = start_x_bottom - dist_on_seg
            py = y + h + noise
            path.lineTo(px, py)

        current_d += len_bottom

        # 6. Bottom-Left Corner
        cx_bl = x + radius
        cy_bl = y + h - radius

        for i in range(steps_corner + 1):
            ft = i / steps_corner
            dist_on_seg = arc_len * ft

            angle_rad = math.pi / 2 + (math.pi / 2) * ft

            noise = get_noise(current_d + dist_on_seg)
            r_noisy = radius + noise

            px = cx_bl + r_noisy * math.cos(angle_rad)
            py = cy_bl + r_noisy * math.sin(angle_rad)
            path.lineTo(px, py)

        current_d += arc_len

        # 7. Left Edge
        start_y_left = y + h - radius
        len_left = h - 2 * radius

        for i in range(steps_right + 1):
            ft = i / steps_right
            dist_on_seg = len_left * ft

            noise = get_noise(current_d + dist_on_seg)

            px = x - noise
            py = start_y_left - dist_on_seg
            path.lineTo(px, py)

        current_d += len_left

        # 8. Top-Left Corner
        cx_tl = x + radius
        cy_tl = y + radius

        for i in range(steps_corner + 1):
            ft = i / steps_corner
            dist_on_seg = arc_len * ft

            angle_rad = math.pi + (math.pi / 2) * ft

            noise = get_noise(current_d + dist_on_seg)
            r_noisy = radius + noise

            px = cx_tl + r_noisy * math.cos(angle_rad)
            py = cy_tl + r_noisy * math.sin(angle_rad)
            path.lineTo(px, py)

        path.closeSubpath()
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = QRectF(self.rect().adjusted(5, 5, -5, -5))
        self.draw_rough_box(
            painter,
            rect,
            fill=True,
            intensity=1.0,
            rough=True,
            radius=self.border_radius,
        )
