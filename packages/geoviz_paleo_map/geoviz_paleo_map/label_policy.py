from __future__ import annotations

from PySide6.QtGui import QFont, QFontMetrics


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def region_label_font_size(screen_width: float, screen_height: float, base_size: int, zoom: float) -> int:
    area = max(0.0, screen_width) * max(0.0, screen_height)
    area_boost = 0
    if area >= 24000:
        area_boost = 3
    elif area >= 9000:
        area_boost = 2
    elif area >= 2500:
        area_boost = 1
    zoom_boost = 1 if zoom >= 5.0 else 0
    return _clamp(base_size + area_boost + zoom_boost, 7, 14)


def chrome_font_size(viewport_width: int, viewport_height: int, base_size: int) -> int:
    shortest = min(viewport_width, viewport_height)
    if shortest >= 900:
        boost = 3
    elif shortest >= 640:
        boost = 2
    elif shortest >= 420:
        boost = 1
    else:
        boost = 0
    return _clamp(base_size + boost, 7, 12)


def text_fits(text: str, width: float, height: float, font_px: int, max_lines: int = 1) -> bool:
    font = QFont("Sans Serif")
    font.setPixelSize(font_px)
    metrics = QFontMetrics(font)
    if max_lines <= 1:
        return metrics.horizontalAdvance(text) <= width and metrics.height() <= height
    if metrics.horizontalAdvance(text) <= width and metrics.height() <= height:
        return True
    for split_at in range(1, len(text)):
        first = text[:split_at]
        second = text[split_at:]
        if metrics.horizontalAdvance(first) <= width and metrics.horizontalAdvance(second) <= width:
            return metrics.height() * 2 <= height
    return False
