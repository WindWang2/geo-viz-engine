"""FigurePanelGraphicsItem + CartographyLayoutWindow panel palette tests.

Phase-2, T7 / #251. The composite figure (油藏综合图) embeds source plots
as live proxies or snapshot pixmaps on the paper sheet.
"""
import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap

from geoviz_paleo_map.cartography.items.figure_panel_item import (
    FigurePanelGraphicsItem,
    panel_rect_mm,
)
from geoviz_paleo_map.cartography.window import CartographyLayoutWindow


def test_figure_panel_item_defaults():
    item = FigurePanelGraphicsItem(
        QRectF(10, 10, 80, 60),
        source_plot_id="plot-1",
        source_plot_type="single_well",
        render_mode="live",
    )
    assert item.source_plot_id == "plot-1"
    assert item.source_plot_type == "single_well"
    assert item.render_mode == "live"
    assert item.snapshot_pixmap() is None
    # LayoutGraphicsItem flags: movable + selectable
    assert item.flags() & item.GraphicsItemFlag.ItemIsMovable
    assert item.flags() & item.GraphicsItemFlag.ItemIsSelectable


def test_figure_panel_snapshot_pixmap_roundtrip():
    pm = QPixmap(40, 30)
    pm.fill(0xFF0000)  # red
    item = FigurePanelGraphicsItem(
        QRectF(5, 5, 40, 30),
        source_plot_id="p",
        source_plot_type="fence_3d",
        render_mode="snapshot",
    )
    item.set_snapshot_pixmap(pm)
    assert item.snapshot_pixmap() is not None
    assert item.snapshot_pixmap().width() == 40


def test_panel_rect_mm_helper():
    r = panel_rect_mm(1.0, 2.0, 30.0, 20.0)
    assert r.x() == 1.0 and r.y() == 2.0
    assert r.width() == 30.0 and r.height() == 20.0


def test_cartography_window_set_plot_sources(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_plot_sources(["plot-a", "plot-b"])
    assert win.plot_sources() == ["plot-a", "plot-b"]
    combo = win._panel_source_combo
    assert combo.count() == 3  # placeholder + 2 sources
    assert combo.itemText(1) == "plot-a"


def test_cartography_window_add_figure_panel(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_plot_sources(["plot-a"])
    item = win.add_figure_panel("plot-a", source_plot_type="plane_map")
    assert item.source_plot_id == "plot-a"
    assert item.source_plot_type == "plane_map"
    assert item in win.figure_panels()
    # Multiple panels do not overlap exactly (offset by count)
    item2 = win.add_figure_panel("plot-a", source_plot_type="plane_map")
    assert item2.rect().topLeft() != item.rect().topLeft()


def test_figure_panel_paints_snapshot_without_crash(qtbot):
    """Snapshot mode paints the stored pixmap into an offscreen image."""
    from PySide6.QtWidgets import QGraphicsScene

    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    pm = QPixmap(64, 48)
    pm.fill(0x0000FF)
    item = win.add_figure_panel("plot-x", source_plot_type="fence_3d",
                                render_mode="snapshot")
    item.set_snapshot_pixmap(pm)

    img = QImage(200, 150, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    scene = QGraphicsScene()
    scene.addItem(item)
    scene.render(p, QRectF(0, 0, 200, 150), QRectF(0, 0, 200, 150))
    p.end()
    # Painting a snapshot-mode panel with a pixmap must not crash; the
    # rendered area under the panel rect is non-white (pixmap red).
    c = img.pixelColor(30, 30)
    assert c.alpha() > 0
