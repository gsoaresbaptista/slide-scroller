import matplotlib
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QVBoxLayout, QWidget

matplotlib.use("QtAgg")
import matplotlib.patheffects as path_effects
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from src.infrastructure.config import get_current_class_data, load_data
from src.infrastructure.signals import signals


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
        self.ax.clear()
        self.ax.set_axis_off()
        self.ax.set_facecolor((0, 0, 0, 0))
        for axis in [self.ax.xaxis, self.ax.yaxis, self.ax.zaxis]:
            axis.set_pane_color((0, 0, 0, 0))

        osc = np.sin(frame * 0.15 + np.arange(self.num_bars))
        h = np.maximum(self.logic_values + (osc * self.intensity), 0.1)
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


class BarChartSlide(QWidget):
    def __init__(self):
        super().__init__()
        self.canvas = BarChartCanvas()
        layout = QVBoxLayout(self)

        # Symmetric padding for centralization
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.canvas)

    def cleanup(self):
        self.canvas.cleanup()

    def start_animation(self):
        self.canvas.start_animation()

    def stop_animation(self):
        self.canvas.stop_animation()
