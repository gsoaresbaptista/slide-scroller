from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter

from src.presentation.components.rough_box import RoughBoxWidget


class RoughPillWidget(RoughBoxWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.setParent(parent)
        self.text = ""
        self.mode = "unlocked"  # unlocked, locked
        self.custom_color = None

        self.resize(120, 40)
        self.start_animation()

    def setText(self, text):
        self.text = text
        self.update()

    def setMode(self, mode, color_override=None):
        self.mode = mode
        self.custom_color = color_override
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        # Adjust for border
        draw_rect = QRectF(rect).adjusted(2, 2, -2, -2)

        if self.mode == "locked":
            # Red/Black style
            painter.setBrush(QColor(0, 0, 0, 220))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(draw_rect, 5, 5)

            c = QColor("#ff5555")
            self.draw_rough_box(
                painter,
                draw_rect,
                fill=False,
                intensity=0.8,
                color=c,
                rough=False,
                radius=5,
            )

            painter.setPen(c)
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)

        else:
            # Unlocked style ("vazado")
            # If black mode, text/border is black. Transparent fill.

            c = QColor("white")
            if self.custom_color == "black":
                c = QColor("black")

            self.draw_rough_box(
                painter,
                draw_rect,
                fill=False,
                intensity=0.8,
                color=c,
                rough=False,
                radius=5,
            )

            painter.setPen(c)
            font = painter.font()
            font.setBold(True)
            font.setWeight(800)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
