import hashlib
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QPixmap

matplotlib.use("Agg")


class LaTeXRenderer:
    def __init__(self, cache_dir=None):
        self.cache_dir = (
            cache_dir or Path.home() / ".cache" / "slide-scroller" / "latex"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = {}

    def _get_cache_key(self, latex_str, fontsize, color):
        content = f"{latex_str}_{fontsize}_{color}"
        return hashlib.md5(content.encode()).hexdigest()

    def render_latex(
        self, latex_str, fontsize=16, color="white", dpi=150, max_width=None
    ):
        cache_key = self._get_cache_key(latex_str, fontsize, color)

        if cache_key in self.cache:
            pixmap = self.cache[cache_key]
            if max_width and pixmap.width() > max_width:
                return pixmap.scaledToWidth(max_width)
            return pixmap

        cache_file = self.cache_dir / f"{cache_key}.png"
        if cache_file.exists():
            pixmap = QPixmap(str(cache_file))
            self.cache[cache_key] = pixmap
            if max_width and pixmap.width() > max_width:
                return pixmap.scaledToWidth(max_width)
            return pixmap

        try:
            fig = plt.figure(figsize=(0.01, 0.01), dpi=dpi)
            fig.patch.set_alpha(0.0)

            text = fig.text(
                0,
                0,
                f"${latex_str}$",
                fontsize=fontsize,
                color=color,
                verticalalignment="bottom",
                horizontalalignment="left",
            )

            fig.canvas.draw()
            bbox = text.get_window_extent(fig.canvas.get_renderer())
            bbox_inches = bbox.transformed(fig.dpi_scale_trans.inverted())

            width = bbox_inches.width + 0.1
            height = bbox_inches.height + 0.1

            plt.close(fig)

            fig = plt.figure(figsize=(width, height), dpi=dpi)
            fig.patch.set_alpha(0.0)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.axis("off")
            ax.text(
                0.5,
                0.5,
                f"${latex_str}$",
                fontsize=fontsize,
                color=color,
                verticalalignment="center",
                horizontalalignment="center",
                transform=ax.transAxes,
            )

            buffer = QBuffer()
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)

            fig.savefig(
                buffer,
                format="png",
                dpi=dpi,
                bbox_inches="tight",
                pad_inches=0.05,
                transparent=True,
            )

            plt.close(fig)

            pixmap = QPixmap()
            pixmap.loadFromData(buffer.data(), "PNG")

            pixmap.save(str(cache_file), "PNG")

            self.cache[cache_key] = pixmap

            if max_width and pixmap.width() > max_width:
                return pixmap.scaledToWidth(max_width)
            return pixmap

        except Exception as e:
            print(f"LaTeX rendering error: {e}")
            return None

    def parse_and_render(
        self, text, fontsize=16, color="white", dpi=150, max_width=None
    ):
        """
        Parse text for LaTeX expressions and return a list of segments.
        Each segment is either ('text', str) or ('latex', QPixmap).
        """
        segments = []
        pattern = r"\$\$(.+?)\$\$|\$(.+?)\$"

        last_end = 0
        for match in re.finditer(pattern, text):
            if match.start() > last_end:
                segments.append(("text", text[last_end : match.start()]))

            latex_content = match.group(1) if match.group(1) else match.group(2)
            is_display = match.group(1) is not None

            pixmap = self.render_latex(latex_content, fontsize, color, dpi, max_width)
            if pixmap:
                segments.append(("latex", pixmap, is_display))
            else:
                segments.append(("text", match.group(0)))

            last_end = match.end()

        if last_end < len(text):
            segments.append(("text", text[last_end:]))

        return segments


_global_renderer = None


def get_latex_renderer():
    global _global_renderer
    if _global_renderer is None:
        _global_renderer = LaTeXRenderer()
    return _global_renderer
