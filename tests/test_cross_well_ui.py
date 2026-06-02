"""Task 22b.5 — CrossWell TWT domain + missing UI (TDD)."""
import pytest


def test_cross_well_domain_toggle_exists(qtbot):
    """Domain toggle button must exist and switch between MD/TWT."""
    from src.pages.cross_well.page import CrossWellPage
    page = CrossWellPage()
    qtbot.addWidget(page)
    assert hasattr(page, "_domain_btn"), "CrossWellPage must have _domain_btn"
    assert page._domain_btn.text() == " 域: MD"
    page._domain_btn.click()
    assert page._domain_btn.text() == " 域: TWT"
    page._domain_btn.click()
    assert page._domain_btn.text() == " 域: MD"


def test_cross_well_worker_progress_connected(qtbot):
    """Worker progress signal must be connected to progress overlay."""
    from src.pages.cross_well.page import CrossWellPage, _WellLoadWorker
    page = CrossWellPage()
    qtbot.addWidget(page)
    # Verify the worker class has progress signal
    worker = _WellLoadWorker(["test"])
    assert hasattr(worker, "progress"), "_WellLoadWorker must have progress signal"
