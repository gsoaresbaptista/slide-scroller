import matplotlib
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

matplotlib.use("QtAgg")
import math
import random

import matplotlib.patheffects as path_effects
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QBrush, QColor, QPainter, QPixmap

from src.infrastructure.config import get_current_class_data, load_data
from src.infrastructure.signals import signals


class HappyCharacterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 300)

        # Load image
        from pathlib import Path

        assets_dir = Path(__file__).parent.parent.parent / "assets"
        self.pixmap = QPixmap(str(assets_dir / "happy.png"))
        self._rotation_y = 0.0

        # Timer for auto-hide
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide_anim)

        self.hide()

    def get_rotation_y(self):
        return self._rotation_y

    def set_rotation_y(self, angle):
        self._rotation_y = angle
        self.update()

    rotation_y = pyqtProperty(float, get_rotation_y, set_rotation_y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Center point
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        # Calculate scale to simulate Y-axis rotation
        scale_x = abs(math.cos(math.radians(self._rotation_y)))

        painter.translate(cx, cy)

        # Apply Y-rotation (flipping - vertical axis spin)
        painter.scale(scale_x, 1.0)

        painter.translate(-cx, -cy)

        # Scale pixmap to fit widget bounds while preserving aspect ratio
        scaled_pixmap = self.pixmap.scaled(
            w,
            h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        # Center the scaled pixmap
        px = (w - scaled_pixmap.width()) / 2
        py = (h - scaled_pixmap.height()) / 2

        painter.drawPixmap(int(px), int(py), scaled_pixmap)

    def play(self, invert=False):
        self.show()
        self.raise_()

        self._rotation_y = 0.0
        parent_h = self.parent().height()
        start_pos = QPoint(-300, parent_h)
        end_pos = QPoint(50, parent_h - 350)

        # Stop running animations
        if hasattr(self, "anim_pos"):
            self.anim_pos.stop()
        if hasattr(self, "anim_rot_y"):
            self.anim_rot_y.stop()
        if hasattr(self, "out_anim"):
            self.out_anim.stop()

        self.hide_timer.stop()

        self.anim_pos = QPropertyAnimation(self, b"pos")
        self.anim_pos.setDuration(1500)
        self.anim_pos.setStartValue(start_pos)
        self.anim_pos.setEndValue(end_pos)
        self.anim_pos.setEasingCurve(QEasingCurve.Type.OutElastic)

        # Y-Rotation animation (spin 3 times = 1080 degrees)
        self.anim_rot_y = QPropertyAnimation(self, b"rotation_y")
        self.anim_rot_y.setDuration(2000)
        self.anim_rot_y.setStartValue(0.0)
        self.anim_rot_y.setEndValue(720.0)
        self.anim_rot_y.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_pos.start()
        self.anim_rot_y.start()

        # Auto hide after animation
        self.hide_timer.start(4000)

    def hide_anim(self):
        self.out_anim = QPropertyAnimation(self, b"pos")
        self.out_anim.setDuration(1000)
        self.out_anim.setEndValue(QPoint(-300, self.parent().height()))
        self.out_anim.setEasingCurve(QEasingCurve.Type.InBack)
        self.out_anim.finished.connect(self.hide)
        self.out_anim.start()


class BarChartCanvas(FigureCanvas):
    def __init__(self):
        self.fig = Figure(figsize=(5, 5), dpi=100)
        super().__init__(self.fig)
        self.fig.patch.set_alpha(0)

        # FULL CENTERING: No margins on the figure itself
        self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1)

        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.ax = self.fig.add_subplot(111, projection="3d")
        self.ax.dist = 4.0  # Maximum zoom
        self.colors = ["#ff007f", "#00e5ff", "#ffcc00", "#bd93f9", "#50fa7b"]

        self.load_configs()
        signals.update_data.connect(self.load_configs)

        self.anim = None
        self.is_running = False
        self.init_animation()

    def init_animation(self):
        self.anim = FuncAnimation(
            self.fig, self.update_plot, interval=50, cache_frame_data=False
        )
        self.anim.event_source.stop()

    def cleanup(self):
        if self.anim:
            try:
                self.anim.event_source.stop()
            except Exception:
                pass
            self.anim = None

    def load_configs(self):
        cls = get_current_class_data()
        d = load_data()
        self.logic_values = np.array(cls.get("bars", [5.0]), dtype=float)

        # Initialize display values if first run
        if not hasattr(self, "display_values"):
            self.display_values = np.copy(self.logic_values)

        # Ensure shape match if logic_values changed size
        if self.display_values.shape != self.logic_values.shape:
            self.display_values = np.copy(self.logic_values)

        vis = d.get("global_config", {}).get("visuals", {})
        self.intensity = vis.get("breathing_intensity", 0.2)
        self.bar_alpha = vis.get("bar_alpha", 0.85)

        self.num_bars = len(self.logic_values)
        self.x_pos = np.arange(self.num_bars) * 0.6
        self.y_pos = np.zeros(self.num_bars)
        self.z_pos = np.zeros(self.num_bars)
        self.dx_base = 0.4
        self.dy_base = 0.4

    def start_animation(self):
        if not self.is_running and self.anim:
            self.anim.event_source.start()
            self.is_running = True

    def stop_animation(self):
        if self.is_running and self.anim:
            self.anim.event_source.stop()
            self.is_running = False

    def update_plot(self, frame):
        if not self.anim:
            return

        # Smooth interpolation towards logic_values
        # Move 5% of the difference per frame
        diff = self.logic_values - self.display_values
        if np.max(np.abs(diff)) > 0.01:
            self.display_values += diff * 0.05
        else:
            self.display_values = np.copy(self.logic_values)

        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_facecolor((0, 0, 0, 0))
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.set_pane_color((0, 0, 0, 0))

        osc = np.sin(frame * 0.15 + np.arange(self.num_bars))
        h = np.maximum(self.display_values + (osc * self.intensity), 0.1)
        deformation = 1.0 - (osc * 0.1 * self.intensity)
        current_dx = self.dx_base * deformation
        current_dy = self.dy_base * deformation
        shift = (self.dx_base - current_dx) / 2
        current_x = self.x_pos + shift
        current_y = self.y_pos + shift

        cols = [self.colors[i % len(self.colors)] for i in range(self.num_bars)]

        self.ax.bar3d(
            current_x,
            current_y,
            self.z_pos,
            current_dx,
            current_dy,
            h,
            color=cols,
            shade=True,
            edgecolor="white",
            linewidth=1.2,
            alpha=self.bar_alpha,
        )

        for i, val in enumerate(h):
            cx = self.x_pos[i] + self.dx_base / 2
            cy = self.y_pos[i] + self.dy_base / 2

            text = self.ax.text(
                cx,
                cy,
                val + 0.5,
                f"{self.logic_values[i]:.0f}",
                ha="center",
                va="bottom",
                fontsize=16,
                fontweight="bold",
                color=cols[i],
                zorder=20,
            )
            text.set_path_effects(
                [
                    path_effects.withStroke(linewidth=4, foreground="white"),
                    path_effects.Normal(),
                ]
            )

            label = self.ax.text(
                cx,
                cy,
                -0.5,
                f"G{i}",
                ha="center",
                va="top",
                fontsize=14,
                fontweight="bold",
                color=cols[i],
                zorder=20,
            )
            label.set_path_effects(
                [
                    path_effects.withStroke(linewidth=3, foreground="white"),
                    path_effects.Normal(),
                ]
            )

        self.ax.view_init(elev=20, azim=-60)

        # --- TRUE CENTRALIZATION logic ---
        total_width = (self.num_bars * 0.6) - 0.2
        center_x = total_width / 2

        zoom = max(1.0, self.num_bars * 0.4)
        self.ax.set_xlim(center_x - zoom, center_x + zoom)
        self.ax.set_ylim(-zoom, zoom)

        max_h = max(8, np.max(self.logic_values))
        self.ax.set_zlim(0, max_h * 1.1)

    def set_display_values(self, values):
        """Update values for animation without full reload."""
        self.logic_values = np.array(values, dtype=float)


class ConfettiWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.particles = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_particles)
        self.active = False

        self.stop_timer = QTimer(self)
        self.stop_timer.setSingleShot(True)
        self.stop_timer.timeout.connect(self.stop)
        # self.color_mode removed

    def explode(self, invert=False):
        self.active = True
        self.particles = []
        # color_mode ignored, always colorful

        w, h = self.width(), self.height()

        # Create particles
        for _ in range(300):
            self.particles.append(
                {
                    "x": w / 2,
                    "y": h / 2,
                    "vx": (random.random() - 0.5) * 40,
                    "vy": (random.random() - 0.5) * 40 - 10,
                    "size": random.randint(5, 12),
                    "color": self.get_color(),
                    "rotation": random.random() * 360,
                    "rot_speed": (random.random() - 0.5) * 20,
                }
            )

        self.timer.start(16)
        self.show()
        self.raise_()

        # Stop after 3 seconds
        # Stop after 3 seconds (reset timer if already running)
        self.stop_timer.stop()
        self.stop_timer.start(3000)

    def get_color(self):
        # Colorful confetti
        return QColor(
            random.randint(50, 255), random.randint(50, 255), random.randint(50, 255)
        )

    def stop(self):
        self.active = False
        self.timer.stop()
        self.hide()

    def update_particles(self):
        if not self.active:
            return

        w, h = self.width(), self.height()
        keep = []

        for p in self.particles:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vy"] += 0.5  # Gravity
            p["rotation"] += p["rot_speed"]
            p["vx"] *= 0.95  # Drag

            if p["y"] < h + 20 and p["x"] > -20 and p["x"] < w + 20:
                keep.append(p)

        self.particles = keep
        self.update()

        if not self.particles:
            self.stop()

    def paintEvent(self, event):
        if not self.active:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for p in self.particles:
            painter.save()
            painter.translate(p["x"], p["y"])
            painter.rotate(p["rotation"])
            painter.setBrush(QBrush(p["color"]))
            painter.setPen(Qt.PenStyle.NoPen)
            s = p["size"]
            painter.drawRect(int(-s / 2), int(-s / 2), int(s), int(s))
            painter.restore()


class BarChartSlide(QWidget):
    def __init__(self, slide_config=None):
        super().__init__()
        self.slide_config = slide_config or {}
        self.canvas = BarChartCanvas()
        layout = QVBoxLayout(self)

        # Symmetric padding for centralization
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)

        # Overlays
        self.happy = HappyCharacterWidget(self)
        self.confetti = ConfettiWidget(self)

    def cleanup(self):
        self.canvas.cleanup()

    def start_animation(self):
        self.canvas.start_animation()

    def stop_animation(self):
        self.canvas.stop_animation()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.confetti.resize(self.size())
        # Happy widget positions itself during animation

    def trigger_increment_effect(self, bar_id, val):
        from src.infrastructure.config import (
            load_data,
            save_data,
        )

        # 1. Update Persistent Data
        d = load_data()
        cls_id = d.get("global_config", {}).get("current_class_id", "Geral")
        bars = d.get("classes", {}).get(cls_id, {}).get("bars", [])

        if 0 <= bar_id < len(bars):
            bars[bar_id] += val
            save_data(d)
            # This triggers file watch -> load_configs -> update canvas logic_values

            # 2. Trigger Animations
            # Check for invert/dark mode
            inv = d.get("global_config", {}).get("color_inverted", False)

            self.happy.play(invert=inv)
            self.confetti.explode(invert=inv)

        else:
            print(f"Bar ID {bar_id} out of range")
