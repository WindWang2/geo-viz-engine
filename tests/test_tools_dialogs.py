"""Task 21.2 — ToolsPage 6 工具弹窗闭环 (TDD).

Each of the 6 tool cards must open its dedicated Azurite Dialog when clicked.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QDialog, QApplication

from src.pages.tools.page import ToolsPage
from src.pages.tools.dialogs import (
    SEGYHeaderInspectorDialog,
    LASCurveResamplerDialog,
    DeviationTVDDialog,
    XMLCoordsConverterDialog,
    TopsCompletionDialog,
    CalamineCompilerDialog,
)


@pytest.fixture
def tools_page(qtbot):
    page = ToolsPage()
    qtbot.addWidget(page)
    return page


def _click_card(page: ToolsPage, idx: int):
    """Trigger a left-click on a tool card."""
    card = page._cards[idx]
    handler = page._card_handlers[idx]
    handler()


def test_tools_page_has_six_handlers(tools_page):
    """ToolsPage exposes a click handler for each of the 6 cards."""
    assert hasattr(tools_page, "_card_handlers")
    assert len(tools_page._card_handlers) == 6
    for h in tools_page._card_handlers:
        assert callable(h)


def test_segy_header_inspector_dialog_class():
    """SEGYHeaderInspectorDialog is an Azurite-styled QDialog subclass."""
    assert issubclass(SEGYHeaderInspectorDialog, QDialog)


def test_las_curve_resampler_dialog_class():
    assert issubclass(LASCurveResamplerDialog, QDialog)


def test_deviation_tvd_dialog_class():
    assert issubclass(DeviationTVDDialog, QDialog)


def test_xml_coords_converter_dialog_class():
    assert issubclass(XMLCoordsConverterDialog, QDialog)


def test_tops_completion_dialog_class():
    assert issubclass(TopsCompletionDialog, QDialog)


def test_calamine_compiler_dialog_class():
    assert issubclass(CalamineCompilerDialog, QDialog)


def test_dialog_instantiation_segy(qtbot):
    """Each dialog can be instantiated without exception and has Azurite header."""
    dlg = SEGYHeaderInspectorDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()  # non-empty
    assert dlg.minimumWidth() >= 400


def test_dialog_instantiation_las(qtbot):
    dlg = LASCurveResamplerDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()
    assert dlg.minimumWidth() >= 400


def test_dialog_instantiation_tvd(qtbot):
    dlg = DeviationTVDDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()


def test_dialog_instantiation_xml_coords(qtbot):
    dlg = XMLCoordsConverterDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()


def test_dialog_instantiation_tops(qtbot):
    dlg = TopsCompletionDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()


def test_dialog_instantiation_calamine(qtbot):
    dlg = CalamineCompilerDialog()
    qtbot.addWidget(dlg)
    assert dlg.windowTitle()


def test_card_click_opens_dialog_segy(qtbot, monkeypatch, tools_page):
    """Clicking card index 1 (SEGY) opens a SEGYHeaderInspectorDialog."""
    opened = []
    orig_exec = SEGYHeaderInspectorDialog.exec

    def _capture(self):
        opened.append(self)
        return 0
    monkeypatch.setattr(SEGYHeaderInspectorDialog, "exec", _capture)

    _click_card(tools_page, 1)
    assert len(opened) == 1


def test_card_click_opens_dialog_las(qtbot, monkeypatch, tools_page):
    opened = []
    monkeypatch.setattr(LASCurveResamplerDialog, "exec", lambda self: opened.append(self) or 0)
    _click_card(tools_page, 2)
    assert len(opened) == 1


def test_card_click_opens_dialog_tvd(qtbot, monkeypatch, tools_page):
    opened = []
    monkeypatch.setattr(DeviationTVDDialog, "exec", lambda self: opened.append(self) or 0)
    _click_card(tools_page, 3)
    assert len(opened) == 1


def test_card_click_opens_dialog_xml_coords(qtbot, monkeypatch, tools_page):
    opened = []
    monkeypatch.setattr(XMLCoordsConverterDialog, "exec", lambda self: opened.append(self) or 0)
    _click_card(tools_page, 4)
    assert len(opened) == 1


def test_card_click_opens_dialog_tops(qtbot, monkeypatch, tools_page):
    opened = []
    monkeypatch.setattr(TopsCompletionDialog, "exec", lambda self: opened.append(self) or 0)
    _click_card(tools_page, 5)
    assert len(opened) == 1
