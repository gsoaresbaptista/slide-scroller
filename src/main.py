import logging
import os
import signal
import sys

# Suppress warnings and force Vulkan to avoid GBM fallback
# Suppress warnings and use xcb to avoid GBM issues
os.environ["QT_LOGGING_RULES"] = "qt.accessibility.atspi* = false"
os.environ["QT_QPA_PLATFORM"] = "xcb"
# os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu-compositing"

from PyQt6.QtWidgets import QApplication

from src.infrastructure.config import get_config_dir
from src.presentation.main_window import SlideScrollerApp

LOG_FILE = get_config_dir() / "app.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("matplotlib").setLevel(logging.WARNING)


def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )


sys.excepthook = handle_exception


def main():
    try:
        logging.info("Starting application...")
        app = QApplication(sys.argv)

        logging.info("Initializing MainWindow...")
        window = SlideScrollerApp()

        # Handle SIGTERM/SIGINT for graceful shutdown (saving position)
        def signal_handler(signum, frame):
            logging.info(f"Received signal {signum}, closing...")
            window.force_close()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        logging.info("Entering Event Loop...")
        sys.exit(app.exec())
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
