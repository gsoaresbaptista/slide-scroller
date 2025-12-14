from datetime import datetime

from PyQt6.QtCore import QRectF, Qt
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


class DeadlineSlide(RoughBoxWidget):
    def __init__(self, slide_config=None):
        super().__init__()
        self.slide_config = slide_config or {}
        self.deadlines = []
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

        # Legend intensity from config
        self.rough_legend = vis.get("rough_legend", 0.5)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        painter.save()
        painter.setPen(QColor("white"))
        f = QFont(self.font_family, 24, QFont.Weight.Bold)
        painter.setFont(f)

        rect = QRectF(0, 0, w, h)
        title_rect = QRectF(rect.x(), rect.y() + 15, rect.width(), 40)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "Prazos")
        painter.restore()

        table_font_size = int(self.font_size * 0.75)

        html = f"""
        <style>
            body {{ font-family: '{self.font_family}'; font-size: {table_font_size}pt; color: white; }}
            table {{ width: 100%; border-collapse: collapse; border-spacing: 0; margin-top: 10px; }}
            th, td {{ padding: 8px; }}
        </style>
        <body>
        <table align="center">
        <tr>
            <th width="40%" style='border-bottom: 2px solid white; text-align: left;'>Nome</th>
            <th width="30%" style='border-bottom: 2px solid white; text-align: center;'>Data</th>
            <th width="30%" style='border-bottom: 2px solid white; text-align: center;'>Faltam</th>
        </tr>
        """

        today = datetime.now()
        parsed = []
        for item in self.deadlines:
            try:
                dt = datetime.strptime(item["date"], "%d/%m/%Y")
                parsed.append((dt, item["task"]))
            except Exception:
                pass

        parsed.sort(key=lambda x: x[0])

        for i, (dt, task) in enumerate(parsed):
            if i > 4:
                break  # Show top 5
            days = (dt - today).days + 1

            if days < 0:
                color = Pastel.GRAY
                txt = "Atrasado"
            elif days <= 7:
                color = Pastel.RED
                txt = f"{days} dias"
            elif days <= 15:
                color = Pastel.ORANGE
                txt = f"{days} dias"
            else:
                color = Pastel.GREEN
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
            (Pastel.GREEN, ">15d"),
            (Pastel.ORANGE, "15-7d"),
            (Pastel.RED, "<7d"),
            (Pastel.GRAY, "Exp"),
        ]

        icon_size = 20
        gap_icon_text = 8
        gap_items = 25

        total_w = 0
        for _, txt in legends:
            total_w += icon_size + gap_icon_text + fm.horizontalAdvance(txt) + gap_items
        total_w -= gap_items

        start_x = rect.x() + (rect.width() - total_w) / 2

        pen_white = QColor("white")

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
            painter.setPen(pen_white)
            painter.drawText(int(start_x), int(legend_y + 15), txt)

            start_x += fm.horizontalAdvance(txt) + gap_items
