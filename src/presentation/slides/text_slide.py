from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
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
        self.locked_index = -1
        self.content_timer = QTimer(self)
        self.content_timer.timeout.connect(self.next_internal_slide)
        signals.update_data.connect(self.load_specific)
        signals.lock_notice.connect(self.set_lock)
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
            self.update_timer()
        self.update()

    def start_animation(self):
        super().start_animation()
        self.content_timer.start(int(self.item_duration * 1000))

    def stop_animation(self):
        super().stop_animation()
        self.content_timer.stop()

    def next_internal_slide(self):
        if self.locked_index != -1:
            return
        self.current_msg_index = (self.current_msg_index + 1) % len(self.messages)
        self.update_timer()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        rect = QRectF(15, 15, w - 30, h - 30)

        doc = QTextDocument()
        msg = self.messages[self.current_msg_index % len(self.messages)]
        doc.setMarkdown(msg)
        doc.setDefaultStyleSheet(
            f"body {{ color: white; font-family: '{self.font_family}'; font-size: {self.font_size}pt; text-align: center; }} h1 {{ color: #ff007f; margin:0; }} h2 {{ color: #00e5ff; }}"
        )
        doc.setTextWidth(rect.width() - 40)

        y_off = rect.y() + (rect.height() - doc.size().height()) / 2
        painter.save()
        painter.translate(rect.x() + 20, y_off)
        doc.drawContents(painter)
        painter.restore()

        if self.messages and self.locked_index == -1:
            total = len(self.messages)
            sx = w / 2 - (total * 10)
            painter.setPen(Qt.PenStyle.NoPen)
            for i in range(total):
                painter.setBrush(
                    QColor(
                        255,
                        255,
                        255,
                        255 if i == self.current_msg_index % total else 80,
                    )
                )
                painter.drawEllipse(QPointF(sx + i * 20, rect.bottom() - 15), 3, 3)
