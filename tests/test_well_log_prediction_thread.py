"""#569: prediction worker.finished must not drop the running QThread."""
from __future__ import annotations

import gc

import pytest
from PySide6.QtCore import QObject, QtMsgType, Signal, qInstallMessageHandler
from PySide6.QtWidgets import QMessageBox

from src.pages.well_log import page as well_log_page
from src.pages.well_log.page import WellLogPage


class _FastPredictionWorker(QObject):
    progress = Signal(int, str)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, well_name, xls_path, current_data):
        super().__init__()
        self.output_path = None

    def run(self):
        self.finished.emit([])


@pytest.fixture
def pred_page(qtbot, monkeypatch):
    monkeypatch.setattr(well_log_page, "PredictionWorker", _FastPredictionWorker)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: None)
    page = WellLogPage()
    qtbot.addWidget(page)
    page._current_well = "W1"
    page._current_xls_path = "dummy.xlsx"
    page._current_data = object()
    return page


def test_prediction_finished_keeps_thread_until_qthread_finished(pred_page, qtbot):
    """worker.finished must not null the QThread while its event loop is alive."""
    held_after_slot = []
    original = pred_page._on_prediction_finished

    def wrapped(records):
        original(records)
        held_after_slot.append(pred_page._pred_thread)

    pred_page._on_prediction_finished = wrapped
    pred_page._run_ai_prediction()
    qtbot.waitUntil(lambda: bool(held_after_slot), timeout=3000)
    assert held_after_slot[0] is not None
    qtbot.waitUntil(lambda: pred_page._pred_thread is None, timeout=3000)


def test_prediction_error_keeps_thread_until_qthread_finished(pred_page, qtbot, monkeypatch):
    class _ErrWorker(_FastPredictionWorker):
        def run(self):
            self.error.emit("boom")

    monkeypatch.setattr(well_log_page, "PredictionWorker", _ErrWorker)
    held_after_slot = []
    original = pred_page._on_prediction_error

    def wrapped(msg):
        original(msg)
        held_after_slot.append(pred_page._pred_thread)

    pred_page._on_prediction_error = wrapped
    pred_page._run_ai_prediction()
    qtbot.waitUntil(lambda: bool(held_after_slot), timeout=3000)
    assert held_after_slot[0] is not None
    qtbot.waitUntil(lambda: pred_page._pred_thread is None, timeout=3000)


def test_prediction_repeated_runs_do_not_destroy_running_thread(pred_page, qtbot):
    messages = []

    def handler(mode, context, message):
        messages.append((mode, str(message)))

    previous = qInstallMessageHandler(handler)
    try:
        for _ in range(50):
            pred_page._run_ai_prediction()
            qtbot.waitUntil(lambda: pred_page._pred_thread is None, timeout=3000)
            gc.collect()
    finally:
        qInstallMessageHandler(previous)

    destroyed = [
        text
        for mode, text in messages
        if "Destroyed while thread is still running" in text
        or mode == QtMsgType.QtFatalMsg
    ]
    assert destroyed == []
