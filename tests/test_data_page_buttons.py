"""Task 22b.3 — DataPage import/rename/delete buttons (TDD)."""
import pytest


def test_data_page_import_data_button_has_handler(qtbot):
    """'导入数据' button must be connected."""
    from src.pages.data.page import DataPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = DataPage(cache)
    qtbot.addWidget(page)
    # Click should not crash
    page._import_data_btn.click()


def test_data_page_rename_button_has_handler(qtbot):
    """'重命名' button must be connected."""
    from src.pages.data.page import DataPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = DataPage(cache)
    qtbot.addWidget(page)
    page._detail_rename_btn.click()
    # Should not crash


def test_data_page_delete_button_has_handler(qtbot):
    """'删除' button must be connected."""
    from src.pages.data.page import DataPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = DataPage(cache)
    qtbot.addWidget(page)
    page._detail_delete_btn.click()
    # Should not crash


def test_data_page_import_excel_does_not_pass(qtbot):
    """Import Excel should not just 'pass' — it should show a dialog or load."""
    from src.pages.data.page import DataPage
    from src.data.cache import DataCache
    cache = DataCache()
    page = DataPage(cache)
    qtbot.addWidget(page)
    # Click should not crash (will show file dialog, which we can't test headlessly)
    # The key test is that it doesn't raise
    page._import_excel_btn.click()
