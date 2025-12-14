from .chart_slide import BarChartSlide
from .deadline_slide import DeadlineSlide
from .text_slide import TextInfoSlide
from .web_slide import WebSlide

# ImageSlide is not fully used yet but we can add it if needed


def create_slide(slide_type, slide_config=None, **kwargs):
    if slide_config is None:
        slide_config = {}

    if slide_type == "chart":
        return BarChartSlide(slide_config=slide_config)
    elif slide_type == "text":
        return TextInfoSlide(slide_config=slide_config)
    elif slide_type == "deadline":
        return DeadlineSlide(slide_config=slide_config)
    elif slide_type == "web":
        return WebSlide(slide_config=slide_config)
    return None
