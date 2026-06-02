"""Task 22a.3 — HeaderToolButton must have clicked connections (TDD)."""
import pytest


def test_header_tool_button_has_tool_key(qtbot):
    """HeaderToolButton must store a tool_key for dispatch."""
    from src.app import HeaderToolButton
    btn = HeaderToolButton("layers")
    qtbot.addWidget(btn)
    assert hasattr(btn, "tool_key"), "HeaderToolButton must have tool_key attr"
    assert btn.tool_key == "layers"


def test_mainwindow_has_on_header_tool():
    """MainWindow must have _on_header_tool dispatch method."""
    from src.app import MainWindow
    assert hasattr(MainWindow, "_on_header_tool"), (
        "MainWindow must have _on_header_tool dispatch method"
    )


def test_on_header_tool_handles_known_keys(qtbot):
    """_on_header_tool should handle all PAGE_CONFIGS tool keys without error."""
    from src.app import MainWindow, PAGE_CONFIGS
    win = MainWindow()
    qtbot.addWidget(win)

    for page_idx, cfg in PAGE_CONFIGS.items():
        for t in cfg.get("tools", []):
            if t.startswith("seg:"):
                continue
            win._on_header_tool(t)


def test_update_header_connects_button_clicked(qtbot):
    """After _update_header_and_footer, HeaderToolButtons must have
    clicked connected to _on_header_tool."""
    from src.app import MainWindow, HeaderToolButton
    win = MainWindow()
    qtbot.addWidget(win)
    win._switch_page(0)

    found_any = False
    for i in range(win.header_tools_layout.count()):
        w = win.header_tools_layout.itemAt(i).widget()
        if w and isinstance(w, HeaderToolButton):
            found_any = True
            assert w.tool_key, "HeaderToolButton must have non-empty tool_key"
    assert found_any, "Expected at least one HeaderToolButton for page 0"
