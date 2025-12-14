import os

os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_OPENGL"] = "software"
os.environ["QT_ENABLE_GBM"] = "0"
os.environ["QT_WEBENGINE_CHROMIUM_FLAGS"] = "--use-vulkan --ignore-gpu-blocklist"

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import QVBoxLayout

try:
    from PyQt6.QtWebEngineCore import QWebEnginePage
    from PyQt6.QtWebEngineWidgets import QWebEngineView

    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

from PyQt6.QtWidgets import QWidget

from src.infrastructure.config import get_current_class_data
from src.infrastructure.signals import signals


class WebSlide(QWidget):
    def __init__(self, slide_config=None):
        super().__init__()
        self.slide_config = slide_config or {}
        self.layout = QVBoxLayout(self)
        self.default_margins = (0, 0, 0, 0)
        self.layout.setContentsMargins(*self.default_margins)
        self.supports_opacity = False

        if HAS_WEBENGINE:
            self.browser = QWebEngineView()

            class SilentWebPage(QWebEnginePage):
                def javaScriptConsoleMessage(self, level, msg, line, sourceID):
                    pass

            self.page = SilentWebPage(self.browser)
            self.browser.setPage(self.page)

            self.browser.setStyleSheet("background: transparent;")
            self.browser.page().setBackgroundColor(Qt.GlobalColor.transparent)
            self.layout.addWidget(self.browser)
        else:
            self.browser = None

        signals.update_data.connect(self.load_url)
        self.load_url()

    def load_url(self):
        if self.browser:
            # Use slide_config if available, otherwise fallback to class data
            if self.slide_config and "url" in self.slide_config:
                u = self.slide_config.get("url", "about:blank")
                zoom = self.slide_config.get("zoom", 1.0)
            else:
                cls = get_current_class_data()
                u = cls.get("web", {}).get("url", "about:blank")
                zoom = cls.get("web", {}).get("zoom", 0.8)

            if not hasattr(self, "_last_loaded_url") or self._last_loaded_url != u:
                self.browser.setUrl(QUrl(u))
                self._last_loaded_url = u

            if self.browser.zoomFactor() != zoom:
                self.browser.setZoomFactor(zoom)
