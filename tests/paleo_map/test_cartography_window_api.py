"""CartographyLayoutWindow public API for free graphics + panel read-back (Task 9)."""

from PySide6.QtCore import QRectF

from geoviz_paleo_map.cartography.window import CartographyLayoutWindow


def test_add_free_graphic_returns_id(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    rec = {
        "kind": "rect",
        "geometry": {"x": 20.0, "y": 20.0, "w": 40.0, "h": 20.0},
    }
    item_id = win.add_free_graphic(rec)
    assert item_id is not None
    assert len(win.free_graphics()) == 1
    assert win.free_graphics()[0]["id"] == item_id


def test_add_free_graphic_rejects_bad_record(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    assert win.add_free_graphic({"kind": "blob"}) is None
    assert win.add_free_graphic("not-a-dict") is None
    assert len(win.free_graphics()) == 0


def test_remove_free_graphic(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    item_id = win.add_free_graphic(
        {"kind": "rect", "geometry": {"x": 10.0, "y": 10.0, "w": 30.0, "h": 15.0}}
    )
    assert item_id is not None
    assert win.remove_free_graphic(item_id) is True
    assert len(win.free_graphics()) == 0
    assert win.remove_free_graphic("nonexistent") is False


def test_free_graphics_excludes_panels(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_plot_sources(["p1"])
    win.add_figure_panel("p1")
    win.add_free_graphic({"kind": "text", "geometry": {"x": 5.0, "y": 5.0}, "props": {"text": "X"}})
    recs = win.free_graphics()
    assert len(recs) == 1
    assert recs[0]["kind"] == "text"


def test_panels_read_back(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_plot_sources(["p1"])
    win.add_figure_panel("p1", source_plot_type="section", render_mode="snapshot")
    panels = win.panels()
    assert len(panels) == 1
    p = panels[0]
    assert p["plot_id"] == "p1"
    assert p["source_plot_type"] == "section"
    assert p["render_mode"] == "snapshot"
    assert "rect_mm" in p and len(p["rect_mm"]) == 4


def test_panels_empty(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    assert win.panels() == []
