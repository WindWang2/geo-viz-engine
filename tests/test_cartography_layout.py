# tests/test_cartography_layout.py
"""Unit tests for publishing cartography & layout engine."""

import pytest
from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QApplication

from geoviz_paleo_map.cartography.scene import PaperGraphicsScene, get_paper_size_mm

@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance

def test_get_paper_size_mm():
    # A4 landscape -> (297, 210)
    w, h = get_paper_size_mm("A4", "landscape")
    assert w == 297.0
    assert h == 210.0

    # A4 portrait -> (210, 297)
    w, h = get_paper_size_mm("A4", "portrait")
    assert w == 210.0
    assert h == 297.0

    # A3 landscape -> (420, 297)
    w, h = get_paper_size_mm("A3", "landscape")
    assert w == 420.0
    assert h == 297.0

def test_paper_graphics_scene(app):
    scene = PaperGraphicsScene(page_size="A4", orientation="landscape", margin_mm=10.0)
    rect = scene.paper_rect()
    assert rect.width() == 297.0
    assert rect.height() == 210.0

    margin_rect = scene.printable_rect()
    assert margin_rect.left() == 10.0
    assert margin_rect.top() == 10.0
    assert margin_rect.width() == 277.0
    assert margin_rect.height() == 190.0

def test_title_block_item(app):
    from geoviz_paleo_map.cartography.items import TitleBlockGraphicsItem
    tb = TitleBlockGraphicsItem(map_title="Test Map Title")
    assert tb.map_title == "Test Map Title"
    assert tb.rect().width() == 120.0
    assert tb.rect().height() == 30.0

def test_template_presets(app):
    from geoviz_paleo_map.cartography import PaperGraphicsScene, apply_template_preset
    scene = PaperGraphicsScene()
    apply_template_preset(scene, "GB_EXPLORATION_SPEC")
    assert len(scene.items()) >= 2

    apply_template_preset(scene, "ACADEMIC_JOURNAL")
    assert len(scene.items()) >= 2


def test_unknown_preset_does_not_clear_scene(app):
    """#677: unknown preset names must not wipe a populated paper scene."""
    from geoviz_paleo_map.cartography import PaperGraphicsScene, apply_template_preset
    from geoviz_paleo_map.cartography.items import TitleBlockGraphicsItem

    scene = PaperGraphicsScene()
    item = TitleBlockGraphicsItem(map_title="keep-me")
    scene.addItem(item)
    before = list(scene.items())
    assert before

    with pytest.raises(ValueError, match="BOGUS"):
        apply_template_preset(scene, "BOGUS")

    assert scene.items() == before
    assert item.scene() is scene

def test_cartography_window_export(app, tmp_path, qtbot):
    from geoviz_paleo_map.cartography import CartographyLayoutWindow
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)

    pdf_file = str(tmp_path / "test_out.pdf")
    svg_file = str(tmp_path / "test_out.svg")

    res_pdf = win.export_pdf(pdf_file)
    assert res_pdf == pdf_file
    assert (tmp_path / "test_out.pdf").exists()
    assert (tmp_path / "test_out.pdf").stat().st_size > 0

    res_svg = win.export_svg(svg_file)
    assert res_svg == svg_file
    assert (tmp_path / "test_out.svg").exists()
    assert (tmp_path / "test_out.svg").stat().st_size > 0


