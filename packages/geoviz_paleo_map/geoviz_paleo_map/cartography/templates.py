# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/templates.py
"""Cartography template presets generator."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from .scene import PaperGraphicsScene
from .items import TitleBlockGraphicsItem, LegendGraphicsItem

def apply_template_preset(scene: PaperGraphicsScene, preset_name: str = "GB_EXPLORATION_SPEC"):
    """Apply preset item layout to paper scene."""
    scene.clear()

    printable = scene.printable_rect()
    p_w = printable.width()
    p_h = printable.height()

    if preset_name == "GB_EXPLORATION_SPEC":
        # Exploration Standard: Title block at bottom right, legend at bottom left
        tb = TitleBlockGraphicsItem(
            rect=QRectF(0, 0, min(140.0, p_w * 0.45), 28.0)
        )
        tb.setPos(printable.right() - tb.rect().width(), printable.bottom() - tb.rect().height())
        scene.addItem(tb)

        leg = LegendGraphicsItem(
            rect=QRectF(0, 0, min(100.0, p_w * 0.35), 45.0),
            columns=2
        )
        leg.setPos(printable.left() + 5.0, printable.bottom() - leg.rect().height())
        scene.addItem(leg)

    elif preset_name == "ACADEMIC_JOURNAL":
        # Academic journal style: Header title top left, legend top right
        tb = TitleBlockGraphicsItem(
            rect=QRectF(0, 0, min(120.0, p_w * 0.4), 24.0),
            map_title="Geological Map of Exploration Region",
            organization="Academic Journal Publication"
        )
        tb.setPos(printable.left() + 5.0, printable.top() + 5.0)
        scene.addItem(tb)

        leg = LegendGraphicsItem(
            rect=QRectF(0, 0, min(90.0, p_w * 0.3), 35.0),
            columns=1
        )
        leg.setPos(printable.right() - leg.rect().width() - 5.0, printable.top() + 5.0)
        scene.addItem(leg)
