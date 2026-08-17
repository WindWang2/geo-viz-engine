"""#567 / #575 / #576 / #577 regressions: toolbox dialog wiring, CI gate
integrity, well-file binding, LAS loader dispatch."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# --- #567: tool dialogs compute on Execute --------------------------------


def _click_execute(dlg):
    dlg._accept_btn.click()


def test_tvd_dialog_executes_backend_and_shows_result(qtbot, monkeypatch):
    """#567: 计算 TVD must run the backend with parsed rows — not just close."""
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    from src.pages.tools.dialogs import DeviationTVDDialog

    dlg = DeviationTVDDialog()
    qtbot.addWidget(dlg)
    from PySide6.QtWidgets import QTableWidgetItem

    for r, row in enumerate((("0", "0", "0"), ("1000", "30", "90"))):
        for c, val in enumerate(row):
            dlg._table.setItem(r, c, QTableWidgetItem(val))

    calls: list[list] = []
    monkeypatch.setattr(
        dlg, "_compute_min_curvature",
        lambda rows: calls.append(rows) or [(0.0, 0.0, 0.0), (955.3, 0.0, 500.0)],
    )
    boxes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, title, text, *a, **k: boxes.append((title, text)) or QMessageBox.StandardButton.Ok),
    )

    _click_execute(dlg)

    assert calls and len(calls[0]) == 2, "backend must receive the two parsed rows"
    assert calls[0][0] == (0.0, 0.0, 0.0)
    assert boxes and boxes[0][0] == "TVD 计算完成", "a result summary must be shown"
    assert "955.3" in boxes[0][1]


def test_tvd_dialog_rejects_bad_input_without_closing(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    from src.pages.tools.dialogs import DeviationTVDDialog

    dlg = DeviationTVDDialog()
    qtbot.addWidget(dlg)
    from PySide6.QtWidgets import QTableWidgetItem

    dlg._table.setItem(0, 0, QTableWidgetItem("abc"))  # not a number
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda parent, title, text, *a, **k: warned.append(title) or QMessageBox.StandardButton.Ok),
    )
    monkeypatch.setattr(dlg, "accept", lambda: warned.append("ACCEPTED"))

    _click_execute(dlg)
    assert warned and warned[-1] != "ACCEPTED", "invalid input must not close the dialog"


def test_resampler_dialog_requires_path(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    from src.pages.tools.dialogs import LASCurveResamplerDialog

    dlg = LASCurveResamplerDialog()
    qtbot.addWidget(dlg)
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda parent, title, text, *a, **k: warned.append(title) or QMessageBox.StandardButton.Ok),
    )
    _click_execute(dlg)
    assert warned == ["缺少输入"], "empty path must warn and keep the dialog open"


def test_resampler_dialog_runs_backend(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    from src.pages.tools.dialogs import LASCurveResamplerDialog

    las = tmp_path / "w.las"
    las.write_text("~V\nVERS 2.0\n~A\n1000 1\n1001 2\n", encoding="utf-8")

    dlg = LASCurveResamplerDialog()
    qtbot.addWidget(dlg)
    dlg._path_edit.setText(str(las))
    dlg._step_spin.setValue(0.5)

    calls: list[tuple[str, float]] = []
    monkeypatch.setattr(
        dlg, "_do_resample",
        lambda path, step: calls.append((path, step)) or ([1000.0, 1000.5], {"GR": [1.0, 1.5]}),
    )
    boxes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, title, text, *a, **k: boxes.append((title, text)) or QMessageBox.StandardButton.Ok),
    )

    _click_execute(dlg)
    assert calls == [(str(las), 0.5)]
    assert boxes and boxes[0][0] == "降采样完成"


def test_xml_converter_dialog_parses_and_converts(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    from src.pages.tools.dialogs import XMLCoordsConverterDialog

    dlg = XMLCoordsConverterDialog()
    qtbot.addWidget(dlg)
    dlg._coords_edit.setPlainText("116.351,39.984\n116.372，40.001")  # incl. full-width comma

    calls: list[tuple[str, str, list]] = []
    monkeypatch.setattr(
        dlg, "_do_convert",
        lambda s, d, c: calls.append((s, d, c)) or [(0.1, 0.2)],
    )
    boxes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, title, text, *a, **k: boxes.append((title, text)) or QMessageBox.StandardButton.Ok),
    )

    _click_execute(dlg)
    assert calls, "backend must run"
    src_epsg, dst_epsg, coords = calls[0]
    assert coords == [(116.351, 39.984), (116.372, 40.001)]
    assert boxes and boxes[0][0] == "转换完成"


def test_tops_interpolator_dialog_parses_json_and_fills(qtbot, monkeypatch):
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication([])
    from src.pages.tools.dialogs import TopsCompletionDialog

    dlg = TopsCompletionDialog()
    qtbot.addWidget(dlg)
    payload = {"W1": {"H1": 1000.0, "H2": 1200.0}, "W2": {"H1": 1010.0, "H2": None}}
    dlg._tops_edit.setPlainText(json.dumps(payload, ensure_ascii=False))

    calls: list[tuple[dict, str]] = []
    monkeypatch.setattr(
        dlg, "_do_interpolate",
        lambda tops, method="linear": calls.append((tops, method))
        or {"W1": payload["W1"], "W2": {"H1": 1010.0, "H2": 1210.0}},
    )
    boxes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda parent, title, text, *a, **k: boxes.append((title, text)) or QMessageBox.StandardButton.Ok),
    )

    _click_execute(dlg)
    assert calls and calls[0][0] == payload
    assert calls[0][1] == "linear"
    assert boxes and "W2.H2" in boxes[0][1], "filled tops must be reported"


# --- #576: token-bounded well-file binding ---------------------------------


def _catalog_with_files(tmp_path: Path, files: list[str], wells: list[str]):
    from src.data.catalog import WellCatalog

    (tmp_path / "well_coordinates.json").write_text(
        json.dumps(
            {"wells": [{"well_name": w, "longitude": 115.0, "latitude": 31.5} for w in wells]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for name in files:
        (tmp_path / name).write_bytes(b"x")
    return WellCatalog(data_dir=tmp_path)


def test_well_file_binding_uses_token_boundaries(tmp_path):
    """#576: HZ21-1-1 must never bind to HZ21-1-18's file."""
    cat = _catalog_with_files(
        tmp_path,
        ["HZ21-1-18-las.xlsx", "HZ21-1-1-data.xlsx"],
        ["HZ21-1-1", "HZ21-1-18"],
    )
    assert cat.get_well_file("HZ21-1-1").name == "HZ21-1-1-data.xlsx"
    assert cat.get_well_file("HZ21-1-18").name == "HZ21-1-18-las.xlsx"


def test_well_file_binding_most_specific_well_wins(tmp_path):
    """#576: a file for the longer well name must not be stolen by the shorter."""
    cat = _catalog_with_files(
        tmp_path,
        ["HZ21-1-18.xlsx"],  # only the longer well has a file
        ["HZ21-1-1", "HZ21-1-18"],
    )
    assert cat.get_well_file("HZ21-1-1") is None  # token boundary: no match
    assert cat.get_well_file("HZ21-1-18").name == "HZ21-1-18.xlsx"


def test_well_file_binding_deterministic_across_insertion_order(tmp_path):
    # same file names, different creation order → same (alphabetical) binding
    for i, order in enumerate(
        (["b-file-HZ21-1-1.xlsx", "a-file-HZ21-1-1.xlsx"],
         ["a-file-HZ21-1-1.xlsx", "b-file-HZ21-1-1.xlsx"])
    ):
        d = tmp_path / f"dir{i}"
        d.mkdir()
        cat = _catalog_with_files(d, order, ["HZ21-1-1"])
        assert cat.get_well_file("HZ21-1-1").name == "a-file-HZ21-1-1.xlsx"


# --- #577 residual: LAS loader dispatch ------------------------------------


def test_get_loader_entry_dispatches_by_extension(tmp_path):
    """#577 residual: an imported LAS well must get the LAS loader, not Excel."""
    from src.data.catalog import WellCatalog
    from src.data.loaders import load_well_log_from_excel, load_well_log_from_las

    cat = WellCatalog()
    (tmp_path / "legacy.xls").write_bytes(b"x")
    (tmp_path / "parsed.las").write_bytes(b"~V\n")
    cat.register_well_file("XLW", tmp_path / "legacy.xls")
    cat.register_well_file("LASW", tmp_path / "parsed.las")

    xl = cat.get_loader_entry("XLW")
    assert xl is not None and xl[0] is load_well_log_from_excel

    la = cat.get_loader_entry("LASW")
    assert la is not None and la[0] is load_well_log_from_las
    assert Path(la[1]).suffix == ".las"


def test_las_registry_loader_produces_well_data(tmp_path):
    """End-to-end: registry LAS entry loads through the worker contract."""
    from src.data.loaders import load_well_log_from_las

    las = tmp_path / "w.las"
    las.write_text(
        """~VERSION INFORMATION
VERS. 2.0
WRAP. NO
~WELL INFORMATION
STRT.M 1000.0
STOP.M 1002.0
STEP.M 1.0
NULL. -999.25
WELL. REGW
~CURVE INFORMATION
DEPT.M
GR.GAPI
~ASCII
1000 10
1001 20
1002 30
""",
        encoding="utf-8",
    )
    data = load_well_log_from_las(las, well_name="Override")
    assert data.well_name == "Override"
    assert data.curves, "LAS curves must be parsed"
