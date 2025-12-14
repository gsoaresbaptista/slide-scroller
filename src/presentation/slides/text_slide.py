import logging

from PyQt6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
)
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter

from src.infrastructure.config import get_current_class_data, load_data, save_data
from src.infrastructure.signals import signals
from src.presentation.components.latex_renderer import get_latex_renderer
from src.presentation.components.rough_box import RoughBoxWidget

logger = logging.getLogger(__name__)


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

        # Load color inversion setting
        self.color_inverted = d.get("global_config", {}).get("color_inverted", False)
        self.text_color = QColor("black" if self.color_inverted else "white")

        # Text alignment: 'center' or 'left'
        self.text_align = (
            self.slide_config.get("text_align", "center")
            if self.slide_config
            else "center"
        )

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
        msg = self.messages[msg_index % len(self.messages)]

        # Check if message contains a table (lines with | separators)
        if self._is_table_content(msg):
            self.draw_table_content(painter, rect, msg, x_offset)
        elif "$" in msg:
            self.draw_latex_content(painter, rect, msg, x_offset)
        else:
            # Render plain text/markdown with manual alignment
            padding_x = 50
            padding_y = 30

            painter.save()
            painter.translate(rect.x() + x_offset, rect.y())

            content_width = rect.width() - (padding_x * 2)
            content_height = rect.height() - (padding_y * 2)

            lines = msg.split("\n")

            font = QFont(self.font_family, self.font_size)
            fm = QFontMetrics(font)
            line_height = fm.height() * 1.5

            # Calculate total height
            total_height = 0
            line_data = []
            for line in lines:
                if not line.strip():
                    line_data.append(("empty", None, line_height * 0.5))
                    total_height += line_height * 0.5
                elif line.strip().startswith("#"):
                    title = line.strip().lstrip("#").strip()
                    title_font = QFont(self.font_family, int(self.font_size * 1.5))
                    title_font.setBold(True)
                    title_fm = QFontMetrics(title_font)
                    h = title_fm.height() + 10
                    line_data.append(("title", title, h))
                    total_height += h
                else:
                    line_data.append(("text", line, line_height))
                    total_height += line_height

            # Center vertically
            y_pos = padding_y + (content_height - total_height) / 2

            for line_type, text, h in line_data:
                if line_type == "empty":
                    y_pos += h
                    continue

                if line_type == "title":
                    title_font = QFont(self.font_family, int(self.font_size * 1.5))
                    title_font.setBold(True)
                    painter.setFont(title_font)
                    painter.setPen(self.text_color)
                    title_fm = QFontMetrics(title_font)

                    if self.text_align == "center":
                        x = (
                            padding_x
                            + (content_width - title_fm.horizontalAdvance(text)) / 2
                        )
                    else:
                        x = padding_x

                    painter.drawText(int(x), int(y_pos + title_fm.ascent()), text)
                    y_pos += h
                else:
                    painter.setFont(font)
                    painter.setPen(self.text_color)

                    if self.text_align == "center":
                        x = padding_x + (content_width - fm.horizontalAdvance(text)) / 2
                    else:
                        x = padding_x

                    painter.drawText(int(x), int(y_pos + fm.ascent()), text)
                    y_pos += h

            painter.restore()

    def _is_table_content(self, msg):
        """Check if message contains table format (rows with | separators)."""
        lines = msg.strip().split("\n")
        table_lines = [line for line in lines if "|" in line and line.count("|") >= 2]
        return len(table_lines) >= 2

    def _parse_table(self, msg):
        """Parse message for table rows. Returns (title, headers, rows)."""
        lines = msg.strip().split("\n")
        title = None
        headers = []
        rows = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                title = line.lstrip("#").strip()
            elif "|" in line:
                # Skip separator lines (|---|---|)
                if (
                    set(line.replace("|", "").replace("-", "").replace(" ", ""))
                    == set()
                ):
                    continue
                cells = [c.strip() for c in line.split("|") if c.strip()]
                if not headers:
                    headers = cells
                else:
                    rows.append(cells)

        return title, headers, rows

    def draw_table_content(self, painter, rect, msg, x_offset):
        """Draw a table with lines using QPainter."""
        renderer = get_latex_renderer()
        title, headers, rows = self._parse_table(msg)

        padding_x = 50
        padding_y = 30

        painter.save()
        painter.translate(rect.x() + x_offset, rect.y())

        content_width = rect.width() - (padding_x * 2)
        content_height = rect.height() - (padding_y * 2)

        # Calculate base font metrics
        font = QFont(self.font_family, self.font_size)
        fm = QFontMetrics(font)
        min_row_height = fm.height() * 1.5

        # Calculate title height
        title_height = 0
        if title:
            title_font = QFont(self.font_family, int(self.font_size * 1.3))
            title_font.setBold(True)
            title_fm = QFontMetrics(title_font)
            title_height = title_fm.height() + 15

        # Column widths (equal distribution)
        num_cols = len(headers) if headers else 2
        col_width = content_width / num_cols
        max_cell_latex_width = int(col_width * 0.85)

        # Pre-render all LaTeX and calculate row heights
        row_heights = []
        all_row_latex = []  # Store rendered LaTeX for each cell

        # Header row
        header_height = min_row_height
        all_row_latex.append([])  # No LaTeX in headers typically
        row_heights.append(header_height)

        # Data rows
        for row in rows:
            row_latex = []
            max_height = min_row_height
            for cell in row:
                if "$" in cell:
                    segments = renderer.parse_and_render(
                        cell,
                        self.font_size,
                        self.text_color.name(),
                        dpi=150,
                        max_width=max_cell_latex_width,
                    )
                    row_latex.append(segments)
                    # Find max height in this cell
                    for seg in segments:
                        if seg[0] == "latex" and seg[1]:
                            if seg[1].height() + 10 > max_height:
                                max_height = seg[1].height() + 10
                else:
                    row_latex.append(None)
            all_row_latex.append(row_latex)
            row_heights.append(max_height)

        # Calculate total table height
        total_table_height = title_height + sum(row_heights)

        # Scale if needed to fit
        scale_factor = 1.0
        if total_table_height > content_height:
            scale_factor = content_height / total_table_height

        # Apply scale to row heights
        scaled_row_heights = [h * scale_factor for h in row_heights]
        scaled_title_height = title_height * scale_factor

        # Start position (center vertically)
        actual_height = scaled_title_height + sum(scaled_row_heights)
        start_y = padding_y + (content_height - actual_height) / 2

        # Draw title
        y_pos = start_y
        if title:
            title_font = QFont(
                self.font_family, int(self.font_size * 1.3 * scale_factor)
            )
            title_font.setBold(True)
            painter.setFont(title_font)
            painter.setPen(self.text_color)

            title_fm = QFontMetrics(title_font)
            x_title = (
                padding_x + (content_width - title_fm.horizontalAdvance(title)) / 2
            )
            painter.drawText(int(x_title), int(y_pos + title_fm.ascent()), title)
            y_pos += scaled_title_height

        # Draw table border
        table_x = padding_x
        table_y = y_pos
        table_width = content_width
        table_height = sum(scaled_row_heights)

        painter.setPen(self.text_color)
        painter.drawRect(
            int(table_x), int(table_y), int(table_width), int(table_height)
        )

        # Draw header row
        font_size_scaled = max(int(self.font_size * scale_factor), 10)
        header_font = QFont(self.font_family, font_size_scaled)
        header_font.setBold(True)
        painter.setFont(header_font)
        fm_scaled = QFontMetrics(header_font)

        header_row_height = scaled_row_heights[0]
        for i, header in enumerate(headers):
            cell_x = table_x + (i * col_width)
            cell_y = table_y

            # Draw cell border
            painter.drawRect(
                int(cell_x), int(cell_y), int(col_width), int(header_row_height)
            )

            # Draw header text centered
            text_x = cell_x + (col_width - fm_scaled.horizontalAdvance(header)) / 2
            text_y = cell_y + header_row_height / 2 + fm_scaled.ascent() / 3
            painter.drawText(int(text_x), int(text_y), header)

        # Draw data rows
        cell_font = QFont(self.font_family, font_size_scaled)
        painter.setFont(cell_font)

        current_y = table_y + header_row_height
        for row_idx, row in enumerate(rows):
            row_h = scaled_row_heights[row_idx + 1]
            row_latex = all_row_latex[row_idx + 1]

            for col_idx, cell in enumerate(row):
                cell_x = table_x + (col_idx * col_width)

                # Draw cell border
                painter.drawRect(
                    int(cell_x), int(current_y), int(col_width), int(row_h)
                )

                # Check if cell contains LaTeX
                segments = row_latex[col_idx] if col_idx < len(row_latex) else None
                if segments:
                    # Calculate total width for centering
                    total_seg_width = 0
                    max_seg_height = 0
                    for seg in segments:
                        if seg[0] == "text":
                            total_seg_width += fm_scaled.horizontalAdvance(seg[1])
                        elif seg[0] == "latex" and seg[1]:
                            scaled_w = int(seg[1].width() * scale_factor)
                            scaled_h = int(seg[1].height() * scale_factor)
                            total_seg_width += scaled_w
                            if scaled_h > max_seg_height:
                                max_seg_height = scaled_h

                    seg_x = cell_x + (col_width - total_seg_width) / 2
                    seg_y = current_y + row_h / 2

                    for seg in segments:
                        if seg[0] == "text":
                            painter.drawText(
                                int(seg_x), int(seg_y + fm_scaled.ascent() / 3), seg[1]
                            )
                            seg_x += fm_scaled.horizontalAdvance(seg[1])
                        elif seg[0] == "latex" and seg[1]:
                            pixmap = seg[1]
                            scaled_w = int(pixmap.width() * scale_factor)
                            scaled_h = int(pixmap.height() * scale_factor)
                            scaled_pixmap = pixmap.scaled(
                                scaled_w,
                                scaled_h,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                            img_y = seg_y - scaled_h / 2
                            painter.drawPixmap(int(seg_x), int(img_y), scaled_pixmap)
                            seg_x += scaled_w
                elif "$" not in cell:
                    # Plain text
                    text_x = (
                        cell_x + (col_width - fm_scaled.horizontalAdvance(cell)) / 2
                    )
                    text_y = current_y + row_h / 2 + fm_scaled.ascent() / 3
                    painter.drawText(int(text_x), int(text_y), cell)

            current_y += row_h

        painter.restore()

    def _parse_bold(self, text):
        """Parse text for **bold** markdown and return list of (is_bold, text) tuples."""
        import re

        parts = []
        pattern = r"\*\*(.+?)\*\*"
        last_end = 0

        for match in re.finditer(pattern, text):
            if match.start() > last_end:
                parts.append((False, text[last_end : match.start()]))
            parts.append((True, match.group(1)))
            last_end = match.end()

        if last_end < len(text):
            parts.append((False, text[last_end:]))

        if not parts:
            parts = [(False, text)]

        return parts

    def draw_latex_content(self, painter, rect, msg, x_offset):
        renderer = get_latex_renderer()
        lines = msg.split("\n")

        # Padding for borders
        padding_x = 50
        padding_y = 30

        painter.save()
        painter.translate(rect.x() + padding_x + x_offset, rect.y())

        font = QFont(self.font_family, self.font_size)
        painter.setFont(font)
        painter.setPen(self.text_color)

        content_width = rect.width() - (padding_x * 2)
        content_height = rect.height() - (padding_y * 2)

        # First pass: collect all line data and find the smallest scale factor
        all_line_data = []
        min_scale_factor = 1.0

        for line in lines:
            if not line.strip():
                all_line_data.append(("empty", None, None))
                continue

            if line.strip().startswith("#"):
                all_line_data.append(("title", line.strip().lstrip("#").strip(), None))
                continue

            max_latex_width = int(content_width * 0.9)
            segments = renderer.parse_and_render(
                line,
                self.font_size,
                self.text_color.name(),
                dpi=150,
                max_width=max_latex_width,
            )

            total_width = 0
            segment_data = []

            for segment in segments:
                if segment[0] == "text":
                    text = segment[1]
                    text_parts = self._parse_bold(text)
                    for is_bold, part_text in text_parts:
                        if is_bold:
                            bold_font = QFont(self.font_family, self.font_size)
                            bold_font.setBold(True)
                            fm = QFontMetrics(bold_font)
                            text_width = fm.horizontalAdvance(part_text)
                            segment_data.append(
                                ("text", part_text, text_width, fm.height(), True)
                            )
                        else:
                            fm = painter.fontMetrics()
                            text_width = fm.horizontalAdvance(part_text)
                            segment_data.append(
                                ("text", part_text, text_width, fm.height(), False)
                            )
                        total_width += text_width
                elif segment[0] == "latex":
                    pixmap = segment[1]
                    is_display = segment[2]
                    segment_data.append(
                        ("latex", pixmap, pixmap.width(), pixmap.height(), is_display)
                    )
                    total_width += pixmap.width()

            scale_factor = 1.0
            if total_width > content_width:
                scale_factor = content_width / total_width

            if scale_factor < min_scale_factor:
                min_scale_factor = scale_factor

            all_line_data.append(("content", segment_data, total_width))

        # Calculate total content height first
        total_content_height = 0
        line_heights = []
        for line_type, data, total_width in all_line_data:
            if line_type == "empty":
                h = self.font_size
            elif line_type == "title":
                title_font = QFont(self.font_family, int(self.font_size * 1.5))
                fm = QFontMetrics(title_font)
                h = fm.height() + 10
            else:
                segment_data = data
                h = (
                    max(
                        (
                            s[3] * (min_scale_factor if s[0] == "latex" else 1.0)
                            for s in segment_data
                        ),
                        default=self.font_size,
                    )
                    + 8
                )
            line_heights.append(h)
            total_content_height += h

        # Center content vertically
        y_position = padding_y + (content_height - total_content_height) / 2
        if y_position < padding_y:
            y_position = padding_y

        # Second pass: render all lines with uniform scale factor
        for i, (line_type, data, total_width) in enumerate(all_line_data):
            if line_type == "empty":
                y_position += line_heights[i]
                continue

            if line_type == "title":
                title_text = data
                title_font = QFont(self.font_family, int(self.font_size * 1.5))
                title_font.setBold(True)
                painter.save()
                painter.setFont(title_font)
                painter.setPen(self.text_color)

                fm = QFontMetrics(title_font)
                title_width = fm.horizontalAdvance(title_text)

                if self.text_align == "left":
                    x_title = 0
                else:
                    x_title = (content_width - title_width) / 2

                painter.drawText(
                    int(x_title), int(y_position + fm.height() * 0.8), title_text
                )
                y_position += line_heights[i]
                painter.restore()
                continue

            segment_data = data

            # Calculate scaled total width
            scaled_total_width = 0
            for seg in segment_data:
                if seg[0] == "text":
                    scaled_total_width += seg[2]
                else:
                    scaled_total_width += seg[2] * min_scale_factor

            if self.text_align == "left":
                x_position = 0
            else:
                x_position = (content_width - scaled_total_width) / 2
            max_height = max(
                (
                    s[3] * (min_scale_factor if s[0] == "latex" else 1.0)
                    for s in segment_data
                ),
                default=self.font_size,
            )

            for seg in segment_data:
                if seg[0] == "text":
                    text, width, height, is_bold = seg[1], seg[2], seg[3], seg[4]
                    if is_bold:
                        painter.save()
                        bold_font = QFont(self.font_family, self.font_size)
                        bold_font.setBold(True)
                        painter.setFont(bold_font)

                    y_text = y_position + (max_height - height) / 2 + height * 0.8
                    painter.drawText(int(x_position), int(y_text), text)
                    x_position += width

                    if is_bold:
                        painter.restore()
                elif seg[0] == "latex":
                    pixmap, width, height, is_display = seg[1], seg[2], seg[3], seg[4]
                    scaled_width = int(width * min_scale_factor)
                    scaled_height = int(height * min_scale_factor)
                    y_img = y_position + (max_height - scaled_height) / 2

                    scaled_pixmap = pixmap.scaled(
                        scaled_width,
                        scaled_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    painter.drawPixmap(int(x_position), int(y_img), scaled_pixmap)
                    x_position += scaled_pixmap.width()

            y_position += line_heights[i]

        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Content area
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
                # Apply color inversion to pagination dots
                r, g, b = (0, 0, 0) if self.color_inverted else (255, 255, 255)
                painter.setBrush(
                    QColor(
                        r,
                        g,
                        b,
                        255 if i == active_index % total else 80,
                    )
                )
                painter.drawEllipse(QPointF(sx + i * 20, rect.bottom() - 15), 3, 3)

        painter.end()
