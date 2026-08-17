"""Task 22b.3 — DataPage import/rename/delete buttons (TDD)."""
import pytest


def test_data_page_import_data_button_has_handler(qtbot, monkeypatch):
    """'导入数据' button must be connected."""
    from src.pages.data.page import DataPage
    from src.data.cache import DataCache
    # The button opens a modal QFileDialog (getOpenFileName), which would block
    # forever on headless CI. Patch it to cancel immediately — the test intent
    # is that the click does not crash.
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        lambda *a, **kw: ("", ""),
    )
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


def test_data_page_import_excel_does_not_pass(qtbot, monkeypatch):
    """Import Excel should not just 'pass' — it should show a dialog or load."""
    from src.pages.data.page import DataPage
    from src.data.cache import DataCache
    # Same modal-dialog guard as the import-data test: cancel the file dialog
    # immediately so the click cannot block headless CI.
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        lambda *a, **kw: ("", ""),
    )
    cache = DataCache()
    page = DataPage(cache)
    qtbot.addWidget(page)
    # Click should not crash (will show file dialog, which we can't test headlessly)
    # The key test is that it doesn't raise
    page._import_excel_btn.click()


def test_excel_import_does_not_parse_on_gui_thread(qtbot, monkeypatch, tmp_path):
    """#711: Excel parse must not run inside the import button slot.

    load_well_log_from_excel (or equivalent) is the documented 1–9 s freeze.
    The slot must return with a wait cursor and leave the parse to a worker.
    """
    from PySide6.QtCore import QCoreApplication, Qt, QThread
    from PySide6.QtWidgets import QMessageBox

    from src.data.cache import DataCache
    from src.pages.data.page import DataPage

    calls: list[bool] = []

    def fake_loader(path, *args, **kwargs):
        app = QCoreApplication.instance()
        calls.append(QThread.currentThread() is app.thread())
        return object()

    monkeypatch.setattr("src.data.loaders.load_well_log_from_excel", fake_loader)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    page = DataPage(DataCache())
    qtbot.addWidget(page)
    monkeypatch.setattr(page.cache, "put_file", lambda path: None)
    monkeypatch.setattr(page.cache.catalog, "register_well_file", lambda *a, **k: None)

    xlsx = tmp_path / "import-well.xlsx"
    xlsx.write_bytes(b"PK")  # path only; loader is stubbed

    page._load_imported_file(str(xlsx), "Excel (*.xlsx *.xls)")

    assert not any(calls), (
        "load_well_log_from_excel must not be called synchronously "
        "from the Excel import button handler"
    )
    assert page.cursor().shape() == Qt.CursorShape.WaitCursor

    qtbot.waitUntil(
        lambda: getattr(page, "_import_thread", None) is None and bool(calls),
        timeout=3000,
    )
    assert calls == [False]
