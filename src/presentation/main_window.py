import ctypes
import logging
import os
import platform

from PyQt6.QtCore import QFileSystemWatcher, Qt, QTimer
from PyQt6.QtGui import QGuiApplication, QRegion
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from src.infrastructure.config import (
    DATA_FILE,
    get_config_dir,
    get_current_class_data,
    load_data,
    save_data,
)
from src.infrastructure.signals import signals
from src.presentation.components.rough_box import RoughBoxWidget
from src.presentation.components.rough_pill import RoughPillWidget
from src.presentation.components.sliding_stacked_widget import SlidingStackedWidget
from src.presentation.slides import TextInfoSlide, create_slide
from src.presentation.slides.chart_slide import BarChartSlide

PID_FILE = get_config_dir() / "app.pid"


class SlideScrollerApp(QWidget):
    def __init__(self):
        super().__init__()
        # Write PID
        PID_FILE.write_text(str(os.getpid()))

        # Load initial data
        load_data()
        d = load_data()
        cfg = d.get("global_config", {})

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        x = cfg.get("x", 100)
        y = cfg.get("y", 100)
        w = cfg.get("width", 600)
        h = cfg.get("height", 500)

        self.move(x, y)
        self.resize(w, h)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 50, 0, 0)

        self.frame = RoughBoxWidget()
        self.main_layout.addWidget(self.frame)

        self.frame_layout = QVBoxLayout(self.frame)
        self.frame_layout.setContentsMargins(5, 5, 5, 5)

        self.stack = SlidingStackedWidget()
        self.frame_layout.addWidget(self.stack)

        self.frame_layout.setContentsMargins(0, 0, 0, 0)
        self.frame.border_path_update.connect(self.update_mask_shape)

        self.frame.start_animation()

        self.slides_data = []
        self.current_index = 0
        self.locked_slide_index = -1
        self.dock_alignment = "default"
        self._is_docking = False

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_geo)

        self.timer_label = RoughPillWidget(self)
        self.timer_label.show()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.tick)
        self.clock_timer.start(1000)

        self.keep_on_top_timer = QTimer(self)
        self.keep_on_top_timer.timeout.connect(self.force_keep_on_top)
        self.keep_on_top_timer.start(500)

        self.watcher = QFileSystemWatcher(self)
        if DATA_FILE.exists():
            self.watcher.addPath(str(DATA_FILE))
        self.watcher.fileChanged.connect(self.on_file_changed)

        signals.rebuild_slides.connect(self.rebuild)
        signals.update_data.connect(self.update_ui)
        signals.lock_slide.connect(self.set_lock)
        signals.close_app.connect(self.force_close)

        self.rebuild()

        cls = get_current_class_data()
        saved_lock = cls.get("state", {}).get("locked_slide", -1)
        saved_last = cls.get("state", {}).get("last_slide_index", 0)

        if saved_lock != -1:
            self.set_lock(saved_lock)
        elif saved_last < len(self.slides_data):
            self.current_index = saved_last
            if self.stack.count() > self.current_index:
                self.stack.setCurrentIndex(self.current_index)
            self.update_view()

        self.flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        if cfg.get("clickthrough", False):
            self.flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(self.flags)
        self.setGeometry(x, y, w, h)
        self.show()

        QTimer.singleShot(0, lambda: self.move(x, y))
        QTimer.singleShot(0, lambda: self.resize(w, h))

        self._last_event_ts = 0

    def set_lock(self, idx):
        d = load_data()
        cid = d["global_config"]["current_class_id"]
        if "state" not in d["classes"][cid]:
            d["classes"][cid]["state"] = {}
        d["classes"][cid]["state"]["locked_slide"] = idx
        save_data(d)

        self.set_lock_internal(idx)

    def set_lock_internal(self, idx):
        self.locked_slide_index = idx
        if idx != -1 and idx < len(self.slides_data):
            self.current_index = idx
            self.rem_time = self.slides_data[idx]["time"]
            self.stack.slide_to(idx)
            self.update_view()
        self.update_overlay_pos()

    def _cleanup_and_exit(self):
        if PID_FILE.exists():
            PID_FILE.unlink()
        self.save_geo()

    def force_close(self):
        self._cleanup_and_exit()
        os._exit(0)

    def closeEvent(self, event):
        self._cleanup_and_exit()
        event.accept()

    def save_geo(self):
        d = load_data()
        if not d:
            d = {}

        if "global_config" not in d:
            d["global_config"] = {}
        cfg = d["global_config"]

        # Check if changed
        current_x = self.pos().x()
        current_y = self.pos().y()
        current_w = self.width()
        current_h = self.height()

        old_x = cfg.get("x", 100)
        old_y = cfg.get("y", 100)
        old_w = cfg.get("width", 600)
        old_h = cfg.get("height", 500)
        old_last_slide = (
            d.get("classes", {})
            .get(cfg.get("current_class_id", "Geral"), {})
            .get("state", {})
            .get("last_slide_index", 0)
        )

        curr_id = cfg.get("current_class_id", "Geral")
        if "classes" not in d:
            d["classes"] = {}
        if curr_id not in d["classes"]:
            d["classes"][curr_id] = {}
        if "state" not in d["classes"][curr_id]:
            d["classes"][curr_id]["state"] = {}

        # Update values
        cfg["x"] = current_x
        cfg["y"] = current_y
        cfg["width"] = current_w
        cfg["height"] = current_h
        d["classes"][curr_id]["state"]["last_slide_index"] = self.current_index

        # Avoid unnecessary writes if nothing changed (prevents reload loop)
        if (
            current_x == old_x
            and current_y == old_y
            and current_w == old_w
            and current_h == old_h
            and self.current_index == old_last_slide
        ):
            return

        save_data(d)

    def mousePressEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.AltModifier:
            self.drag_pos = e.globalPosition().toPoint()

    def mouseMoveEvent(self, e):
        if hasattr(self, "drag_pos") and self.drag_pos:
            self.move(self.pos() + e.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = e.globalPosition().toPoint()

    def mouseReleaseEvent(self, e):
        self.drag_pos = None

    def on_file_changed(self, path):
        # Debounce or simple reload
        if str(DATA_FILE) not in self.watcher.files() and DATA_FILE.exists():
            self.watcher.addPath(str(DATA_FILE))

        # Load new data to check if we really need to rebuild
        try:
            new_data = load_data()
            new_cls = new_data.get("classes", {}).get(
                new_data.get("global_config", {}).get("current_class_id", "Geral"), {}
            )
            new_slides = new_cls.get("active_slides", [])

            # Compare with current slides structure
            # We reconstruct the simple list of types/durations to compare
            current_slides_config = []
            if hasattr(self, "_last_loaded_slides"):
                current_slides_config = self._last_loaded_slides

            # Check if active_slides changed
            if new_slides != current_slides_config:
                signals.update_data.emit()
                self.rebuild()
            else:
                # If slides didn't change, maybe just global config or state changed.
                # Update UI elements without destroying slides
                signals.update_data.emit()
                self.update_ui_from_config(new_data)

        except Exception as e:
            print(f"Error reloading data: {e}")

    def force_keep_on_top(self):
        try:
            if platform.system() == "Windows":
                ctypes.windll.user32.SetWindowPos(
                    int(self.winId()), -1, 0, 0, 0, 0, 0x0013
                )
            else:
                self.raise_()
        except Exception:
            pass  # Swallow errors to prevent crash

    def rebuild(self):
        cls = get_current_class_data()
        new_slides_config = cls.get("active_slides", [])

        # Access old config
        old_slides_config = []
        if hasattr(self, "_last_loaded_slides"):
            old_slides_config = self._last_loaded_slides

        # Check if we are currently showing the "No Slides" placeholder
        is_placeholder = (not old_slides_config) and (len(self.slides_data) > 0)

        match_count = 0
        if not is_placeholder:
            # Find matching prefix
            for i in range(min(len(new_slides_config), len(old_slides_config))):
                if new_slides_config[i] == old_slides_config[i]:
                    match_count += 1
                else:
                    break

        # 1. Remove non-matching tail
        while len(self.slides_data) > match_count:
            data = self.slides_data.pop()
            w = data["widget"]
            if hasattr(w, "cleanup"):
                w.cleanup()
            self.stack.removeWidget(w)
            w.deleteLater()

        # 2. Add new widgets
        for i in range(match_count, len(new_slides_config)):
            s = new_slides_config[i]
            t = s["type"]
            dur = s.get("duration", 10)
            w = create_slide(t, slide_config=s)
            if w:
                self.stack.addWidget(w)
                self.slides_data.append({"widget": w, "time": dur})

        # 3. Handle Empty Case
        if not self.slides_data:
            w = TextInfoSlide()
            w.messages = [{"content": "# No Slides", "duration": 5}]
            self.stack.addWidget(w)
            self.slides_data.append({"widget": w, "time": 5})

        self._last_loaded_slides = new_slides_config

        # 4. Restore State
        self.locked_slide_index = cls.get("state", {}).get("locked_slide", -1)

        if self.current_index >= len(self.slides_data):
            self.current_index = 0

        # Update view/timer logic
        if self.current_index < len(self.slides_data):
            self.stack.setCurrentIndex(self.current_index)

            if self.current_index >= match_count:
                self.update_view()

        self.update_overlay_pos()

    def update_ui_from_config(self, data):
        # handle updates that don't require full rebuild
        # e.g. check lock state
        global_conf = data.get("global_config", {})
        cid = global_conf.get("current_class_id", "Geral")
        cls = data.get("classes", {}).get(cid, {})
        new_lock = cls.get("state", {}).get("locked_slide", -1)

        # Resize logic
        w = global_conf.get("width", 600)
        h = global_conf.get("height", 500)
        if w != self.width() or h != self.height():
            self.resize(w, h)

        # Click-through logic
        ct = global_conf.get("clickthrough", False)
        current_ct = bool(self.windowFlags() & Qt.WindowType.WindowTransparentForInput)

        if ct != current_ct:
            self.hide()
            self.flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.Tool
                | Qt.WindowType.WindowStaysOnTopHint
            )
            if ct:
                self.flags |= Qt.WindowType.WindowTransparentForInput

            self.setWindowFlags(self.flags)
            self.show()

            # Restore position after reset
            QTimer.singleShot(
                0,
                lambda: self.move(global_conf.get("x", 100), global_conf.get("y", 100)),
            )

        if new_lock != self.locked_slide_index:
            self.set_lock_internal(new_lock)

        self.update_overlay_pos()

        # Check for dock action
        dock_action = global_conf.get("dock_action", {})
        if dock_action:
            ts = dock_action.get("ts", 0)
            # Check if this is a new action we haven't processed yet
            if not hasattr(self, "_last_dock_ts") or ts > self._last_dock_ts:
                self._last_dock_ts = ts
                self.process_dock(
                    dock_action.get("pos"), global_conf.get("dock_margin", 20)
                )

        # Check for margin update on existing dock
        current_margin = global_conf.get("dock_margin", 20)
        # Store last known margin to detect change
        if not hasattr(self, "_last_margin"):
            self._last_margin = current_margin

        if current_margin != self._last_margin:
            self._last_margin = current_margin
            # Only re-dock if we are currently docked
            if self.dock_alignment != "default":
                self.process_dock(self.dock_alignment, current_margin)

        # Check for events (like inc)
        event = global_conf.get("last_event")
        if event:
            ts = event.get("ts", 0)
            if ts > self._last_event_ts:
                self._last_event_ts = ts
                self.process_event(event)

    def process_event(self, event):
        match event.get("type"):
            case "inc":
                # Find chart slide
                chart_idx = -1
                for i, s in enumerate(self.slides_data):
                    if isinstance(s["widget"], BarChartSlide):
                        chart_idx = i
                        break

                if chart_idx != -1:
                    # Switch if needed
                    if self.current_index != chart_idx:
                        self.current_index = chart_idx
                        self.stack.slide_to(chart_idx)
                        self.update_view()

                    # Trigger effect
                    w = self.slides_data[chart_idx]["widget"]
                    w.trigger_increment_effect(event.get("bar_id"), event.get("val"))

    def process_dock(self, pos, margin):
        screen = self.screen()
        if not screen:
            screen = QGuiApplication.primaryScreen()
        if not screen:
            return

        geo = screen.availableGeometry()
        full_geo = screen.geometry()

        logging.info(
            f"Screen Info: Name={screen.name()}, Available={geo}, Full={full_geo}"
        )
        x, y = self.x(), self.y()
        w, h = self.width(), self.height()

        # Get taskbar offset
        d = load_data()
        taskbar_offset = d.get("global_config", {}).get("taskbar_offset", 0)
        logging.info(
            f"Process Dock: pos={pos}, margin={margin}, taskbar_offset={taskbar_offset}"
        )

        match pos:
            case "tl":
                x = geo.left() + margin
                y = geo.top() + margin
            case "tr":
                x = geo.right() - w - margin
                y = geo.top() + margin
            case "bl":
                x = geo.left() + margin
                y = geo.y() + geo.height() - h - margin - taskbar_offset
            case "br":
                x = geo.right() - w - margin
                y = geo.y() + geo.height() - h - margin - taskbar_offset

        logging.info(
            f"Docking {pos}: Screen={screen.name()}, Geo={geo}, Target=({x}, {y})"
        )

        self._is_docking = True
        self.move(x, y)
        self.save_geo()

        # Delayed reset of docking flag to allow WM to settle
        QTimer.singleShot(250, lambda: setattr(self, "_is_docking", False))

        # Update dock alignment state
        self.dock_alignment = pos
        self.update_overlay_pos()
        self.update_margins()

    def moveEvent(self, event):
        # Detect manual moves
        if not self._is_docking:
            # If we are docked and move manually, reset dock state
            if self.dock_alignment != "default":
                self.dock_alignment = "default"
                self.update_overlay_pos()
                self.update_margins()

        # Debounce save
        self.save_timer.start(500)
        super().moveEvent(event)

    def update_margins(self):
        match self.dock_alignment:
            case "tl" | "tr":
                self.main_layout.setContentsMargins(0, 0, 0, 50)
            case "bl" | "br" | "default" | _:
                self.main_layout.setContentsMargins(0, 50, 0, 0)

    def update_mask_shape(self, path):
        region = QRegion(path.toFillPolygon().toPolygon())
        self.stack.setMask(region)
        # Force update/repaint, especially important for WebEngineView
        self.stack.update()
        if self.stack.currentWidget():
            self.stack.currentWidget().update()

    def update_ui(self):
        self.update_overlay_pos()

    def update_overlay_pos(self):
        # Mapping:
        # tl: Top & Left -> Pill Bottom & Left
        # tr: Top & Right -> Pill Bottom & Right
        # bl: Bottom & Left -> Pill Top & Left
        # br: Bottom & Right -> Pill Top & Right
        # default: Top & Right (Standard)

        tgt_x = 0
        tgt_y = 0

        margin_x = 0

        w = self.width()
        h = self.height()
        p_w = self.timer_label.width()
        p_h = self.timer_label.height()

        match self.dock_alignment:
            case "tl":  # Bottom-Left
                tgt_x = margin_x
                tgt_y = h - p_h
            case "tr":  # Bottom-Right
                tgt_x = w - p_w - margin_x
                tgt_y = h - p_h
            case "bl":  # Top-Left
                tgt_x = margin_x
                tgt_y = 0
            case "br":  # Top-Right
                tgt_x = w - p_w - margin_x
                tgt_y = 0
            case _:  # Default (Top-Right)
                tgt_x = w - p_w - margin_x
                tgt_y = 0

        if self.locked_slide_index != -1:
            # LOCKED STATE
            self.timer_label.setText("TRAVADO")
            self.timer_label.setMode("locked")
            self.timer_label.setStyleSheet("background: transparent;")
            self.timer_label.resize(90, 45)
            p_w = 90
            p_h = 45

        else:
            # UNLOCKED (RUNNING) STATE
            self.timer_label.setText(f"Próximo: {self.rem_time}s")
            self.timer_label.setMode("unlocked")
            self.timer_label.setStyleSheet("background: transparent;")
            self.timer_label.resize(110, 45)
            p_w = 110
            p_h = 45

        # Recalculate target with final size
        match self.dock_alignment:
            case "tl":
                tgt_x = margin_x
                tgt_y = h - p_h
            case "tr":
                tgt_x = w - p_w - margin_x
                tgt_y = h - p_h
            case "bl":
                tgt_x = margin_x
                tgt_y = 0
            case "br" | "default" | _:
                tgt_x = w - p_w - margin_x
                tgt_y = 0

        self.timer_label.move(int(tgt_x), int(tgt_y))
        self.timer_label.raise_()

    def update_view(self):
        if not self.slides_data:
            return

        d = self.slides_data[self.current_index]
        self.rem_time = d["time"]
        cw = d["widget"]

        if hasattr(cw, "start_animation"):
            cw.start_animation()

        self.update_overlay_pos()

    def tick(self):
        if self.locked_slide_index != -1:
            return
        self.rem_time -= 1
        self.update_overlay_pos()
        if self.rem_time <= 0:
            self.next_slide()

    def next_slide(self):
        cw = self.slides_data[self.current_index]["widget"]
        if hasattr(cw, "stop_animation"):
            cw.stop_animation()
        self.current_index = (self.current_index + 1) % len(self.slides_data)
        self.stack.slide_to(self.current_index)
        self.update_view()
