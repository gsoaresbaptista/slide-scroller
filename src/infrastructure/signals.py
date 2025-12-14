from PyQt6.QtCore import QObject, pyqtSignal


class AppSignals(QObject):
    update_data = pyqtSignal()
    rebuild_slides = pyqtSignal()
    resize_window = pyqtSignal(int, int)
    toggle_border = pyqtSignal(bool)
    lock_slide = pyqtSignal(int)
    lock_notice = pyqtSignal(int)
    border_frame_update = pyqtSignal(float)
    close_app = pyqtSignal()


signals = AppSignals()
