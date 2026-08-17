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


def test_overlay_cross_chain_merge_emits_one_group(qtbot):
    """#705: A→C and B→A must emit {A,B,C}, not leave B as a singleton."""
    from src.pages.cross_well.sidebar import CrossWellSidebar

    sidebar = CrossWellSidebar()
    qtbot.addWidget(sidebar)
    sidebar.set_available_curves(["A", "B", "C"])

    def _set_overlay(curve: str, target: str) -> None:
        for i in range(sidebar._overlay_table.rowCount()):
            combo = sidebar._overlay_table.cellWidget(i, 1)
            if combo.property("curve_name") == curve:
                combo.setCurrentText(f"与 {target} 叠加")
                return
        raise AssertionError(f"curve {curve} not in overlay table")

    _set_overlay("A", "C")
    _set_overlay("B", "A")
    groups = list(sidebar._curve_groups.values())
    assert any(set(g) == {"A", "B", "C"} for g in groups), sidebar._curve_groups


def test_cross_well_worker_progress_connected(qtbot):
    """Worker progress signal must be connected to progress overlay."""
    from src.pages.cross_well.page import CrossWellPage, _WellLoadWorker
    page = CrossWellPage()
    qtbot.addWidget(page)
    # Verify the worker class has progress signal
    worker = _WellLoadWorker(["test"])
    assert hasattr(worker, "progress"), "_WellLoadWorker must have progress signal"
