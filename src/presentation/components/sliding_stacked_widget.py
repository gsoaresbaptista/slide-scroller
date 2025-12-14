from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
)
from PyQt6.QtWidgets import QStackedLayout, QStackedWidget


class SlidingStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.anim_duration = 500
        self.transition_active = False
        self.layout().setStackingMode(QStackedLayout.StackingMode.StackAll)

    def addWidget(self, widget):
        idx = super().addWidget(widget)
        # In StackAll mode, all widgets are visible by default.
        # We must manually hide them unless it's the current one.
        if idx != self.currentIndex():
            widget.hide()
        return idx

    def setCurrentIndex(self, index):
        # When setting index instantly, we must handle visibility manually due to StackAll
        old_widget = self.currentWidget()
        if old_widget:
            old_widget.hide()

        super().setCurrentIndex(index)

        new_widget = self.currentWidget()
        if new_widget:
            new_widget.show()
            new_widget.raise_()

    def slide_to(self, index):
        current_idx = self.currentIndex()
        if current_idx == index:
            return

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        if not current_widget or not next_widget:
            self.setCurrentIndex(index)
            return

        if self.transition_active:
            try:
                self.anim_group.finished.disconnect()
            except Exception:
                pass
            self.anim_group.stop()
            if hasattr(self, "_next_widget") and self._next_widget:
                try:
                    self._next_widget.hide()
                except RuntimeError:
                    pass  # Object might be deleted
            self.transition_active = False

        self.transition_active = True
        self._next_widget = next_widget

        # Geometry
        width = self.width()
        height = self.height()

        # Direction: Next (Right to Left)
        # Usually slideshows go Forward -> Slide from Right
        # But we can calculate based on index.
        # If we loop (Max -> 0), it should still be "Next".
        # We assume usage implies "Next" unless specified.
        # But for general usage:
        direction = 1  # 1 = Next (Slide Left), -1 = Prev (Slide Right)
        if index < current_idx:
            direction = -1

        # Handling Wrap-around logic (optional, but good for slideshows)
        # If going from Last to First -> Next
        # If going from First to Last -> Prev
        if current_idx == self.count() - 1 and index == 0:
            direction = 1
        elif current_idx == 0 and index == self.count() - 1:
            direction = -1

        # Setup Start Positions
        # Next starts off-screen
        offset_x = width * direction
        next_widget.setGeometry(offset_x, 0, width, height)
        next_widget.show()
        next_widget.raise_()  # Ensure top

        # Current starts at 0,0
        current_widget.setGeometry(0, 0, width, height)
        current_widget.show()

        # Animations
        self.anim_group = QParallelAnimationGroup()

        # Anim Current (0 -> -Width)
        anim_curr = QPropertyAnimation(current_widget, b"pos")
        anim_curr.setDuration(self.anim_duration)
        anim_curr.setStartValue(QPoint(0, 0))
        anim_curr.setEndValue(QPoint(-offset_x, 0))
        anim_curr.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Anim Next (Width -> 0)
        anim_next = QPropertyAnimation(next_widget, b"pos")
        anim_next.setDuration(self.anim_duration)
        anim_next.setStartValue(QPoint(offset_x, 0))
        anim_next.setEndValue(QPoint(0, 0))
        anim_next.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_group.addAnimation(anim_curr)
        self.anim_group.addAnimation(anim_next)

        def on_finished():
            try:
                current_widget.hide()
                current_widget.move(0, 0)
                next_widget.move(0, 0)
                super(SlidingStackedWidget, self).setCurrentIndex(index)
            except RuntimeError:
                pass  # Widget deleted during animation
            except Exception as e:
                print(f"Error in slide animation finish: {e}")
            finally:
                self.transition_active = False
                self._next_widget = None

        self.anim_group.finished.connect(on_finished)
        self.anim_group.start()

    def resizeEvent(self, event):
        # Ensure all widgets resize to fit
        for i in range(self.count()):
            self.widget(i).setGeometry(self.rect())
        super().resizeEvent(event)
