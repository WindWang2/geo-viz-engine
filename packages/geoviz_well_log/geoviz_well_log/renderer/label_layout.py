from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF
from PySide6.QtGui import QFontMetrics


@dataclass(frozen=True)
class LabelPolicy:
    font_px: int
    max_lines: int
    min_label_height: int
    vertical: bool = False


def compute_header_label_policy(rect: QRectF) -> LabelPolicy:
    font_px = 16 if rect.width() < 120 else 17
    max_lines = 2 if rect.height() >= font_px * 2.1 else 1
    min_label_height = int(font_px * (1.75 if max_lines == 2 else 1.25))
    return LabelPolicy(font_px=font_px, max_lines=max_lines, min_label_height=min_label_height)


def compute_label_policy(
    rect: QRectF,
    depth_span: float,
    interval_heights: list[float],
    force_vertical: bool = False,
) -> LabelPolicy:
    visible_heights = [h for h in interval_heights if h > 0]
    vertical = force_vertical or rect.width() < 72
    if not visible_heights or rect.height() <= 0 or depth_span <= 0:
        return LabelPolicy(font_px=11, max_lines=1, min_label_height=16, vertical=vertical)

    px_per_depth = rect.height() / depth_span
    typical_height = sorted(visible_heights)[len(visible_heights) // 2]
    scale_px = 12 + int(max(0.0, min(4.0, (px_per_depth - 1.8) * 1.1)))
    height_px = max(12, min(16, int(typical_height / 4)))
    font_px = max(12, min(16, min(scale_px, height_px)))
    if rect.width() >= 72 and typical_height >= 80:
        font_px = max(font_px, 13)
    max_lines = 1 if vertical else 2 if rect.width() >= 56 and typical_height >= font_px * 2.4 else 1
    min_label_height = int(font_px * (1.8 if max_lines == 2 else 1.35))
    return LabelPolicy(font_px=font_px, max_lines=max_lines, min_label_height=min_label_height, vertical=vertical)


def fit_label_text(text: str, rect: QRectF, policy: LabelPolicy, metrics: QFontMetrics) -> list[str]:
    if rect.height() < policy.min_label_height or rect.width() <= 4:
        return []

    available_width = max(1, int(rect.height() if policy.vertical else rect.width()))
    if metrics.horizontalAdvance(text) <= available_width:
        return [text]

    if policy.vertical:
        return [text]

    if policy.max_lines >= 2:
        lines = _wrap_two_lines(text, available_width, metrics)
        if lines:
            return lines

    elided = metrics.elidedText(text, policy_elide_mode(), available_width)
    return [elided] if elided else []


def policy_elide_mode():
    from PySide6.QtCore import Qt

    return Qt.TextElideMode.ElideRight


def _wrap_two_lines(text: str, width: int, metrics: QFontMetrics) -> list[str]:
    for split_at in range(1, len(text)):
        first = text[:split_at]
        second = text[split_at:]
        if metrics.horizontalAdvance(first) <= width and metrics.horizontalAdvance(second) <= width:
            return [first, second]

    for split_at in range(len(text) - 1, 0, -1):
        first = text[:split_at]
        second = metrics.elidedText(text[split_at:], policy_elide_mode(), width)
        if metrics.horizontalAdvance(first) <= width and second and metrics.horizontalAdvance(second) <= width:
            return [first, second]

    return []
