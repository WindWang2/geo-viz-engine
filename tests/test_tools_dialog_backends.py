"""Task 22b.1 — ToolsPage dialog backends (TDD)."""
import numpy as np
import pytest


# ---------------------------------------------------------------------------
# LASCurveResamplerDialog
# ---------------------------------------------------------------------------

def test_las_resampler_has_resample_method():
    """LASCurveResamplerDialog must have a _do_resample method."""
    from src.pages.tools.dialogs import LASCurveResamplerDialog
    assert hasattr(LASCurveResamplerDialog, "_do_resample"), (
        "LASCurveResamplerDialog must have _do_resample"
    )


def test_las_resampler_accept_does_not_close_without_file(qtbot, monkeypatch):
    """Accept without LAS file should warn, not close."""
    from PySide6.QtWidgets import QDialog, QMessageBox

    from src.pages.tools.dialogs import LASCurveResamplerDialog

    warned = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warned.append(args)
    )
    dlg = LASCurveResamplerDialog()
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg._execute() is False
    dlg._on_accept_clicked()
    assert warned
    assert dlg.isVisible()
    assert dlg.result() != QDialog.DialogCode.Accepted


# ---------------------------------------------------------------------------
# DeviationTVDDialog
# ---------------------------------------------------------------------------

def test_tvd_dialog_has_compute_method():
    """DeviationTVDDialog must have _compute_min_curvature that does real work."""
    from src.pages.tools.dialogs import DeviationTVDDialog
    import inspect
    src = inspect.getsource(DeviationTVDDialog._compute_min_curvature)
    lowered = src.lower()
    assert "tvd" in lowered
    assert "cos(" in lowered or "math.cos" in lowered
    assert src.strip().splitlines()[-1].strip() != "pass"


def test_min_curvature_computes_tvd():
    """Minimum curvature should compute TVD for a simple vertical well."""
    from src.pages.tools.dialogs import DeviationTVDDialog
    dlg = DeviationTVDDialog()
    # Vertical well: MD 0→100, Incl 0°, Azim 0°
    rows = [
        (0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0),
    ]
    result = dlg._compute_min_curvature(rows)
    assert len(result) == 2
    assert abs(result[-1][0] - 100.0) < 0.01  # TVD ≈ MD for vertical


def test_min_curvature_inclined_well():
    """Minimum curvature for a deviated well should give TVD < MD."""
    from src.pages.tools.dialogs import DeviationTVDDialog
    dlg = DeviationTVDDialog()
    rows = [
        (0.0, 0.0, 0.0),
        (141.42, 45.0, 0.0),
    ]
    result = dlg._compute_min_curvature(rows)
    assert len(result) == 2
    # TVD < MD for deviated well, should be ~127 for 0→45° arc
    assert result[-1][0] < 141.42
    assert result[-1][0] > 100.0


# ---------------------------------------------------------------------------
# XMLCoordsConverterDialog
# ---------------------------------------------------------------------------

def test_xml_coords_has_convert_method():
    """XMLCoordsConverterDialog must have _do_convert method."""
    from src.pages.tools.dialogs import XMLCoordsConverterDialog
    assert hasattr(XMLCoordsConverterDialog, "_do_convert"), (
        "XMLCoordsConverterDialog must have _do_convert"
    )


# ---------------------------------------------------------------------------
# TopsCompletionDialog
# ---------------------------------------------------------------------------

def test_tops_completion_has_interpolate_method():
    """TopsCompletionDialog must have _do_interpolate method."""
    from src.pages.tools.dialogs import TopsCompletionDialog
    assert hasattr(TopsCompletionDialog, "_do_interpolate"), (
        "TopsCompletionDialog must have _do_interpolate"
    )


def test_tops_interpolate_linear():
    """Linear interpolation should fill missing tops."""
    from src.pages.tools.dialogs import TopsCompletionDialog
    dlg = TopsCompletionDialog()
    # 3 wells, well 2 missing formation B
    known_tops = {
        "Well_A": {"Formation_X": 100.0, "Formation_Y": 200.0},
        "Well_B": {"Formation_X": None, "Formation_Y": 220.0},
        "Well_C": {"Formation_X": 120.0, "Formation_Y": 240.0},
    }
    result = dlg._do_interpolate(known_tops, method="linear")
    assert "Well_B" in result
    assert result["Well_B"]["Formation_X"] is not None
    # Should be ~110 (midpoint between 100 and 120)
    assert 100 <= result["Well_B"]["Formation_X"] <= 120


# ---------------------------------------------------------------------------
# CalamineCompilerDialog
# ---------------------------------------------------------------------------

def test_calamine_compiler_has_compile_method():
    """CalamineCompilerDialog must have _do_compile method."""
    from src.pages.tools.dialogs import CalamineCompilerDialog
    assert hasattr(CalamineCompilerDialog, "_do_compile"), (
        "CalamineCompilerDialog must have _do_compile"
    )


def test_calamine_compile_valid_expression():
    """Valid Python expression should compile successfully."""
    from src.pages.tools.dialogs import CalamineCompilerDialog
    dlg = CalamineCompilerDialog()
    ok, msg = dlg._do_compile("GR * 0.5 + SP")
    assert ok is True
    assert "成功" in msg or "valid" in msg.lower()


def test_calamine_compile_invalid_expression():
    """Invalid expression should return error."""
    from src.pages.tools.dialogs import CalamineCompilerDialog
    dlg = CalamineCompilerDialog()
    ok, msg = dlg._do_compile("GR @#$ SP")
    assert ok is False


# ---------------------------------------------------------------------------
# SEGYHeaderInspectorDialog (#699)
# ---------------------------------------------------------------------------

def test_segy_header_inspector_shows_text_header_not_trace_header(qtbot, tmp_path):
    """EBCDIC pane must show f.text[0], not the first trace header dict."""
    import segyio

    from src.pages.tools.dialogs import SEGYHeaderInspectorDialog

    sgy_path = tmp_path / "header.sgy"
    spec = segyio.spec()
    spec.sorting = 2
    spec.format = 1
    spec.ilines = [10]
    spec.xlines = [20]
    spec.samples = list(range(4))
    card = "C 1 GEOVIZ TEST EBCDIC HEADER FOR ISSUE 699"
    with segyio.create(str(sgy_path), spec) as f:
        f.text[0] = card
        f.header[0] = {
            segyio.TraceField.INLINE_3D: 10,
            segyio.TraceField.CROSSLINE_3D: 20,
        }
        f.trace[0] = np.zeros(4, dtype=np.float32)

    dlg = SEGYHeaderInspectorDialog()
    qtbot.addWidget(dlg)
    dlg._load_headers(str(sgy_path))
    text = dlg._text_header.toPlainText()
    assert "GEOVIZ TEST EBCDIC HEADER" in text
    assert not text.lstrip().startswith("{")
    bin_text = dlg._bin_header.toPlainText()
    assert "Format" in bin_text or "Interval" in bin_text
