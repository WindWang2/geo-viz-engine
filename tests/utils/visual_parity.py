"""Reusable visual parity helpers for QWidget renderers.

Pattern: render a widget at a fixed viewport, then compare its pixels against
a previously saved "golden" PNG. Pixels are sampled (every Nth row × column)
and counted as differing when their channel-sum delta exceeds `threshold`.

Used by `tests/test_map_visual_parity.py`. Will be reused by future renderer
migrations (e.g. PaleoMap) so the golden-image workflow stays consistent.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget


def pixel_diff_ratio(a: QImage, b: QImage,
                     *, threshold: int = 30, step: int = 4) -> float:
    """Return the fraction of sampled pixels where |Δr|+|Δg|+|Δb| > threshold.

    `step` controls sampling density (step=4 ⇒ 1/16 of pixels). Increase for
    speed, decrease for stricter coverage.
    """
    assert a.size() == b.size(), f"size mismatch: {a.size()} vs {b.size()}"
    differing = 0
    total = 0
    w, h = a.width(), a.height()
    for y in range(0, h, step):
        for x in range(0, w, step):
            ca = a.pixelColor(x, y)
            cb = b.pixelColor(x, y)
            total += 1
            if (abs(ca.red() - cb.red())
                    + abs(ca.green() - cb.green())
                    + abs(ca.blue() - cb.blue())) > threshold:
                differing += 1
    return differing / max(total, 1)


def render_widget_to_image(widget: QWidget, width: int, height: int,
                            qtbot) -> QImage:
    """Resize, show, wait-exposed, and grab the widget as a QImage (ARGB32)."""
    qtbot.addWidget(widget)
    widget.resize(width, height)
    widget.show()
    qtbot.waitExposed(widget)
    return widget.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)


def load_golden(path: Path) -> QImage:
    """Read a golden PNG. Asserts it exists and converts to ARGB32 for compare."""
    img = QImage(str(path))
    assert not img.isNull(), f"golden image missing: {path}"
    return img.convertToFormat(QImage.Format.Format_ARGB32)


def assert_visual_parity(current: QImage, golden: QImage,
                          *, max_diff: float = 0.01,
                          threshold: int = 30, step: int = 4) -> None:
    """Raise AssertionError if pixel-diff ratio exceeds `max_diff` (default 1%)."""
    ratio = pixel_diff_ratio(current, golden, threshold=threshold, step=step)
    assert ratio < max_diff, (
        f"visual parity diff {ratio * 100:.2f}% exceeds {max_diff * 100:.2f}%"
    )
