import ast
import importlib
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel
from src.pages.tools.page import ToolsPage, ToolCard

_TOOLS_PAGE = Path(__file__).resolve().parents[1] / "src" / "pages" / "tools" / "page.py"


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


def test_tools_page_has_no_module_level_scripts_import():
    """#698: ToolsPage must import without `scripts/` on sys.path."""
    tree = ast.parse(_TOOLS_PAGE.read_text(encoding="utf-8"), filename=str(_TOOLS_PAGE))
    leaked = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("scripts"):
            leaked.append(ast.unparse(node))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts."):
                    leaked.append(ast.unparse(node))
    assert leaked == [], f"module-level scripts import: {leaked}"


def test_tools_page_imports_when_scripts_package_missing():
    """#698: importing the page must not require the top-level scripts package."""
    doomed = [
        name
        for name in list(sys.modules)
        if name == "scripts"
        or name.startswith("scripts.")
        or name.startswith("src.pages.tools")
    ]
    saved = {name: sys.modules[name] for name in doomed}

    class _BlockScripts:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "scripts" or fullname.startswith("scripts."):
                raise ModuleNotFoundError(fullname)
            return None

    blocker = _BlockScripts()
    for name in doomed:
        del sys.modules[name]
    sys.meta_path.insert(0, blocker)
    try:
        module = importlib.import_module("src.pages.tools.page")
        assert hasattr(module, "ToolsPage")
    finally:
        sys.meta_path.remove(blocker)
        for name in list(sys.modules):
            if (
                name == "scripts"
                or name.startswith("scripts.")
                or name.startswith("src.pages.tools")
            ):
                sys.modules.pop(name, None)
        sys.modules.update(saved)
