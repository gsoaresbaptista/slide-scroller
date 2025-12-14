from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QPainter, QTextDocument

from src.infrastructure.config import get_current_class_data, load_data, save_data
from src.infrastructure.signals import signals
from src.presentation.components.rough_box import RoughBoxWidget


class TextInfoSlide(RoughBoxWidget):
    def __init__(self, slide_config=None):
        super().__init__()
        self.slide_config = slide_config or {}
        self.messages = []
        self.current_msg_index = 0
        self.next_msg_index = 0
        self.locked_index = -1
        self.content_timer = QTimer(self)
        self.content_timer.timeout.connect(self.next_internal_slide)
        signals.update_data.connect(self.load_specific)
        signals.lock_notice.connect(self.set_lock)

        self.slide_offset = 0.0
        self.is_animating = False
        self.animation = None

        self.load_specific()

    def load_specific(self):
        d = load_data()

        # Get total slide duration
        self.total_duration = (
            self.slide_config.get("duration", 10) if self.slide_config else 10
        )

        # If we have slide_config, use it directly
        if self.slide_config:
            # New format: messages list (just content strings)
            if "messages" in self.slide_config:
                self.messages = [
                    msg.get("content", "") if isinstance(msg, dict) else msg
                    for msg in self.slide_config["messages"]
                ]
            # Old format: single content field (backward compatibility)
            elif "content" in self.slide_config:
                self.messages = [self.slide_config.get("content", "# Vazio")]
            else:
                self.messages = ["# Vazio"]
        else:
            # Fallback to notices for backward compatibility
            cls = get_current_class_data()
            notices = cls.get("notices", [])
            if notices:
                self.messages = [
                    n.get("content", "") if isinstance(n, dict) else n for n in notices
                ]
            else:
                self.messages = ["# Vazio"]

        # Calculate duration per item
        self.item_duration = (
            self.total_duration / len(self.messages)
            if self.messages
            else self.total_duration
        )

        vis = d.get("global_config", {}).get("visuals", {})
        self.font_family = vis.get("font_family", "Segoe UI")
        self.font_size = vis.get("font_size", 16)

        self.locked_index = -1
        self.update_timer()

    def update_timer(self):
        if self.content_timer.isActive():
            self.content_timer.setInterval(int(self.item_duration * 1000))

    def set_lock(self, idx):
        self.locked_index = idx
        d = load_data()
        cid = d["global_config"]["current_class_id"]
        if "state" not in d["classes"][cid]:
            d["classes"][cid]["state"] = {}
        d["classes"][cid]["state"]["locked_notice"] = idx
        save_data(d)

        if idx != -1:
            self.current_msg_index = idx
            self.next_msg_index = idx
            self.slide_offset = 0.0
            self.update_timer()
        self.update()

    def start_animation(self):
        super().start_animation()
        self.content_timer.start(int(self.item_duration * 1000))

    def stop_animation(self):
        super().stop_animation()
        self.content_timer.stop()

    def next_internal_slide(self):
        if self.locked_index != -1 or self.is_animating:
            return

        self.next_msg_index = (self.current_msg_index + 1) % len(self.messages)
        self.start_slide_animation()

    def start_slide_animation(self):
        if self.animation:
            self.animation.stop()

        self.is_animating = True
        self.animation = QPropertyAnimation(self, b"slideOffset")
        self.animation.setDuration(400)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.finished.connect(self.on_animation_finished)
        self.animation.start()

    def on_animation_finished(self):
        self.current_msg_index = self.next_msg_index
        self.slide_offset = 0.0
        self.is_animating = False
        self.update_timer()
        self.update()

    @pyqtProperty(float)
    def slideOffset(self):
        return self.slide_offset

    @slideOffset.setter
    def slideOffset(self, value):
        self.slide_offset = value
        self.update()

    def draw_text_content(self, painter, rect, msg_index, x_offset):
        doc = QTextDocument()
        msg = self.messages[msg_index % len(self.messages)]
        doc.setMarkdown(msg)
        doc.setDefaultStyleSheet(
            f"body {{ color: white; font-family: '{self.font_family}'; font-size: {self.font_size}pt; text-align: center; }} h1 {{ color: #ff007f; margin:0; }} h2 {{ color: #00e5ff; }}"
        )
        doc.setTextWidth(rect.width() - 40)

        y_off = rect.y() + (rect.height() - doc.size().height()) / 2
        painter.save()
        painter.translate(rect.x() + 20 + x_offset, y_off)
        doc.drawContents(painter)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(15, 15, w - 30, h - 30)

        if self.is_animating:
            current_offset = -self.slide_offset * w
            next_offset = (1.0 - self.slide_offset) * w

            self.draw_text_content(
                painter, rect, self.current_msg_index, current_offset
            )
            self.draw_text_content(painter, rect, self.next_msg_index, next_offset)
        else:
            self.draw_text_content(painter, rect, self.current_msg_index, 0)

        if self.messages and self.locked_index == -1:
            total = len(self.messages)
            sx = w / 2 - (total * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(total):
                active_index = (
                    self.next_msg_index if self.is_animating else self.current_msg_index
                )
                painter.setBrush(
                    QColor(
                        255,
                        255,
                        255,
                        255 if i == active_index % total else 80,
                    )
                )
                painter.drawEllipse(QPointF(sx + i * 20, rect.bottom() - 15), 3, 3)
