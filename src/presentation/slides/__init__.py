from .chart_slide import BarChartSlide
from .deadline_slide import DeadlineSlide
from .text_slide import TextInfoSlide
from .web_slide import WebSlide

# ImageSlide is not fully used yet but we can add it if needed


def create_slide(slide_type, **kwargs):
    if slide_type == "chart":
        return BarChartSlide()
    elif slide_type == "text":
        return TextInfoSlide()
    elif slide_type == "deadlines":
        return DeadlineSlide()
    elif slide_type == "web":
        return WebSlide()
    return None
