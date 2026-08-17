"""Task 22a.3 — HeaderToolButton must have clicked connections (TDD)."""
from unittest.mock import Mock, patch


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
    """_on_header_tool must dispatch each PAGE_CONFIGS tool key to the page."""
    from src.app import MainWindow, PAGE_CONFIGS
    win = MainWindow()
    qtbot.addWidget(win)
    page = win.stack.currentWidget()
    assert page is not None

    for _page_idx, cfg in PAGE_CONFIGS.items():
        for t in cfg.get("tools", []):
            if t.startswith("seg:"):
                continue
            handler = Mock(name=f"_on_tool_{t}")
            setattr(page, f"_on_tool_{t}", handler)
            win._on_header_tool(t)
            handler.assert_called_once()
            delattr(page, f"_on_tool_{t}")


def test_update_header_connects_button_clicked(qtbot):
    """After _update_header_and_footer, HeaderToolButtons must have
    clicked connected to _on_header_tool."""
    from src.app import MainWindow, HeaderToolButton
    win = MainWindow()
    qtbot.addWidget(win)
    win._switch_page(0)

    found_any = False
    with patch.object(win, "_on_header_tool") as spy:
        for i in range(win.header_tools_layout.count()):
            w = win.header_tools_layout.itemAt(i).widget()
            if w and isinstance(w, HeaderToolButton):
                found_any = True
                assert w.tool_key, "HeaderToolButton must have non-empty tool_key"
                spy.reset_mock()
                w.click()
                spy.assert_called_once_with(w.tool_key)
    assert found_any, "Expected at least one HeaderToolButton for page 0"
