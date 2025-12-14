from datetime import datetime

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QTextDocument

from src.infrastructure.config import get_current_class_data, load_data
from src.infrastructure.signals import signals
from src.presentation.components.rough_box import RoughBoxWidget


class Pastel:
    RED = "#ff5555"
    ORANGE = "#ffb86c"
    GREEN = "#50fa7b"
    GRAY = "#6272a4"
    YELLOW = "#f1fa8c"
    DARK_GREEN = "#006400"
    DARK_YELLOW = "#b58900"


class DeadlineSlide(RoughBoxWidget):
    def __init__(self, slide_config=None):
        super().__init__()
        self.slide_config = slide_config or {}
        self.deadlines = []
        self.parsed_deadlines = []

        # Pagination
        self.current_page = 0
        self.items_per_page = 5
        self.total_pages = 1
        self.page_timer = QTimer(self)
        self.page_timer.timeout.connect(self.next_page)

        # Connect to update signals
        signals.update_data.connect(self.load_specific)
        self.load_specific()

    def load_specific(self):
        cls = get_current_class_data()
        d = load_data()

        # If slide_config has date/title, create a single deadline entry
        if self.slide_config and "date" in self.slide_config:
            self.deadlines = [
                {
                    "date": self.slide_config.get("date", ""),
                    "task": self.slide_config.get("title", "Deadline"),
                }
            ]
        else:
            # Fallback to deadlines list
            self.deadlines = cls.get("deadlines", [])

        vis = d.get("global_config", {}).get("visuals", {})
        self.font_family = vis.get("font_family", "Segoe UI")
        # Request: "Aumente a fonte" - defaulting to 18 instead of 16
        self.font_size = vis.get("font_size", 18)

        # Load color inversion setting
        self.color_inverted = d.get("global_config", {}).get("color_inverted", False)
        self.text_color = "black" if self.color_inverted else "white"

        # Legend intensity from config
        self.rough_legend = vis.get("rough_legend", 0.5)

        # Parse deadlines once
        self.parsed_deadlines = []
        for item in self.deadlines:
            try:
                dt = datetime.strptime(item["date"], "%d/%m/%Y")
                self.parsed_deadlines.append((dt, item["task"]))
            except Exception:
                pass
        self.parsed_deadlines.sort(key=lambda x: x[0])

        # Calculate layout and limit
        available_h = self.height() - 140
        line_height = self.font_size * 2.5  # Rough estimate including padding
        if line_height < 30:
            line_height = 30

        calculated_limit = max(1, int(available_h / line_height))
        self.items_per_page = calculated_limit

        self.total_pages = (
            len(self.parsed_deadlines) + self.items_per_page - 1
        ) // self.items_per_page
        if self.total_pages < 1:
            self.total_pages = 1

        self.current_page = 0

        # Setup rotation
        total_duration = self.slide_config.get("duration", 10)
        if self.total_pages > 1:
            page_duration = max(3, total_duration / self.total_pages)
            self.page_timer.start(int(page_duration * 1000))
        else:
            self.page_timer.stop()

        self.update()

    def next_page(self):
        self.current_page = (self.current_page + 1) % self.total_pages
        self.update()

    def resizeEvent(self, event):
        # Recalculate items per page on resize
        self.load_specific()
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        painter.save()
        painter.setPen(QColor(self.text_color))
        f = QFont(self.font_family, 24, QFont.Weight.Bold)
        painter.setFont(f)

        rect = QRectF(0, 0, w, h)
        title_rect = QRectF(rect.x(), rect.y() + 15, rect.width(), 40)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "Prazos")
        painter.restore()

        table_font_size = int(self.font_size * 0.75)

        html = f"""
        <style>
            body {{ font-family: '{self.font_family}'; font-size: {table_font_size}pt; color: {self.text_color}; }}
            table {{ width: 100%; border-collapse: collapse; border-spacing: 0; margin-top: 10px; }}
            th, td {{ padding: 8px; }}
        </style>
        <body>
        <table align="center">
        <tr>
            <th width="40%" style='border-bottom: 2px solid {self.text_color}; text-align: left;'>Nome</th>
            <th width="30%" style='border-bottom: 2px solid {self.text_color}; text-align: center;'>Data</th>
            <th width="30%" style='border-bottom: 2px solid {self.text_color}; text-align: center;'>Faltam</th>
        </tr>
        """

        if not self.parsed_deadlines:
            return

        today = datetime.now()

        start_idx = self.current_page * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_items = self.parsed_deadlines[start_idx:end_idx]

        for i, (dt, task) in enumerate(page_items):
            days = (dt - today).days + 1

            if days < 0:
                color = Pastel.GRAY
                txt = "Expirado"
            elif days <= 7:
                color = Pastel.RED
                txt = f"{days} dias"
            elif days <= 15:
                color = Pastel.DARK_YELLOW if self.color_inverted else Pastel.ORANGE
                txt = f"{days} dias"
            else:
                color = "#006400" if self.color_inverted else Pastel.GREEN
                txt = f"{days} dias"

            html += f"""
            <tr>
                <td style='border-bottom: 1px solid #555;'>{task}</td>
                <td style='border-bottom: 1px solid #555; text-align: center;'>{dt.strftime("%d/%m/%Y")}</td>
                <td style='border-bottom: 1px solid #555; text-align: center; color:{color}; font-weight:bold'>{txt}</td>
            </tr>
            """

        html += "</table></body>"

        doc = QTextDocument()
        doc.setHtml(html)
        doc.setTextWidth(rect.width() - 60)  # Padding

        painter.save()
        painter.translate(rect.x() + 30, rect.y() + 60)
        doc.drawContents(painter)
        painter.restore()

        legend_y = rect.bottom() - 40
        painter.setFont(QFont("Segoe UI", 12))
        fm = QFontMetrics(painter.font())

        legends = [
            (
                "#006400" if self.color_inverted else Pastel.GREEN,
                ">15d",
            ),
            (
                Pastel.DARK_YELLOW if self.color_inverted else Pastel.ORANGE,
                "15-7d",
            ),
            (Pastel.RED, "<7d"),
            (Pastel.GRAY, "Exp."),
        ]

        icon_size = 20
        gap_icon_text = 8
        gap_items = 25

        total_w = 0
        for _, txt in legends:
            total_w += icon_size + gap_icon_text + fm.horizontalAdvance(txt) + gap_items
        total_w -= gap_items

        start_x = rect.x() + (rect.width() - total_w) / 2

        pen_text = QColor(self.text_color)

        for color, txt in legends:
            sq_rect = QRectF(start_x, legend_y, icon_size, icon_size)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(sq_rect.adjusted(2, 2, -2, -2), 2, 2)

            self.draw_rough_box(
                painter,
                sq_rect,
                fill=False,
                intensity=self.rough_legend,
                color=QColor(color).lighter(120),
                rough=False,
                radius=2,
            )

            start_x += icon_size + gap_icon_text
            painter.setPen(pen_text)
            painter.drawText(int(start_x), int(legend_y + 15), txt)

            start_x += fm.horizontalAdvance(txt) + gap_items

        # Draw Pagination Dots
        if self.total_pages > 1:
            total = self.total_pages
            sx = w / 2 - (total * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(total):
                active = i == self.current_page
                # Apply color inversion to pagination dots
                base_c = QColor("black") if self.color_inverted else QColor("white")
                base_c.setAlpha(255 if active else 80)
                painter.setBrush(base_c)
                painter.drawEllipse(QPointF(sx + i * 20, rect.bottom() - 15), 3, 3)

        painter.end()
