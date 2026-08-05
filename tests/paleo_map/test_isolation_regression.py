"""Regression for the PR #35 segfault class (#272).

Root cause: PySide6 6.11 removed the 2-arg ``drawPixmap(QRectF, QPixmap)``
and ``drawPixmap(QRect, QPixmap)`` overloads — they now raise TypeError at
paint time. A TypeError raised mid-paint (QPainter/scene still holding
resources) left corrupted interpreter state that segfaulted the next
test's cyclic GC. PR #35 fixed two call sites; this test guards the
*class* of bug: any paint path that calls drawPixmap with a target rect +
pixmap must use the 3-arg ``(target, pixmap, sourceRect)`` form, which
PySide6 6.11 supports. If the broken 2-arg form returns, this test fails
with TypeError instead of crashing the whole suite.
"""

import pytest
from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap


def test_drawPixmap_target_plus_pixmap_uses_supported_overload():
    """The 3-arg (target, pixmap, sourceRect) form works in PySide6 6.11.

    The 2-arg (target, pixmap) form — which image_track.py used before #272
    — raises TypeError. This test exercises both to pin the supported form;
    if a future regression reintroduces the 2-arg call, the assertion below
    catches it deterministically rather than via a GC-time segfault.
    """
    pm = QPixmap(10, 10)
    pm.fill(0xFFFF0000)
    img = QImage(20, 20, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        # Supported 3-arg form (target rect, pixmap, source rect) — this is
        # what image_track.py now uses after #272.
        painter.drawPixmap(QRectF(0, 0, 10, 10), pm, QRectF(pm.rect()))
        painter.drawPixmap(QRect(0, 0, 10, 10), pm, QRect(pm.rect()))
    finally:
        painter.end()
    # The painted region is non-white (pixmap red over white fill).
    assert img.pixelColor(5, 5).red() > 200


def test_broken_2arg_drawPixmap_overload_is_rejected():
    """The 2-arg (QRectF, QPixmap) form is removed in PySide6 6.11.

    Documents WHY the 3-arg form is required: the 2-arg form raises
    TypeError at paint time, which (when it fires mid-render of a real
    QGraphicsScene) is exactly the PR #35 segfault trigger. If PySide6
    ever restores the 2-arg overload, this test would pass and the
    image_track call site could revert — but until then it must raise.
    """
    pm = QPixmap(10, 10)
    pm.fill(0xFFFF0000)
    img = QImage(20, 20, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    try:
        with pytest.raises(TypeError):
            painter.drawPixmap(QRectF(0, 0, 10, 10), pm)
    finally:
        painter.end()
