import pytest
from PySide6.QtWidgets import QApplication, QLabel
from src.pages.tools.page import ToolsPage, ToolCard


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_tools_page_has_six_cards(app):
    """Task 20.5: ToolsPage must render 6 Azurite tool cards."""
    page = ToolsPage()
    cards = page.findChildren(ToolCard)
    assert len(cards) == 6, f"Expected 6 ToolCards, found {len(cards)}"


def test_tools_page_title_and_subtitle(app):
    page = ToolsPage()
    labels = page.findChildren(QLabel)
    titles = [l.text() for l in labels]
    assert "工具箱" in titles
    assert "独立小工具集" in titles


def test_tool_cards_have_icons_and_tags(app):
    """Each card must contain an icon, name, tag chip, and description."""
    page = ToolsPage()
    cards = page.findChildren(ToolCard)
    for card in cards:
        labels = card.findChildren(QLabel)
        # icon label + name label + tag label + description label
        assert len(labels) >= 4, f"Card has too few labels: {len(labels)}"
