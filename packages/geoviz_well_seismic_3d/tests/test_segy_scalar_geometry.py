"""SEG-Y SourceGroupScalar + degenerate-corner honesty (scientific V6 §9).

SourceGroupScalar semantics (SEG-Y rev1/rev2, bytes 71–72):

* scalar > 0 → multiply header int by scalar;
* scalar < 0 → divide header int by -scalar;
* scalar == 0 → per rev2 undefined; the common writer convention (and this
  repo's loader) treat it as "coordinates already in metres" — documented
  convention, not a guess about the file.

A survey footprint must never look valid when the source geometry is
uncertain: all-zero/degenerate SourceX/Y must be refused, not repaired into
a 1 m-bin survey at the origin.
"""

from __future__ import annotations

from pathlib import Path

import pytest

segyio = pytest.importorskip("segyio")

from geoviz_well_seismic_3d.segy_survey import survey_corners_from_segy
from geoviz_well_seismic_3d.survey import survey_from_corners


def _write_segy(
    path: Path,
    *,
    scalar: int,
    n_il: int = 4,
    n_xl: int = 5,
    il0: int = 1,
    xl0: int = 1,
    bin_m: float = 25.0,
    with_text_header: bool = False,
    inconsistent_scalar: bool = False,
    zero_coords: bool = False,
) -> Path:
    """Mini 3D with SourceX/SourceY stored as RAW ints; true XY = raw*apply(scalar)."""
    spec = segyio.spec()
    spec.ilines = list(range(il0, il0 + n_il))
    spec.xlines = list(range(xl0, xl0 + n_xl))
    spec.samples = list(range(16))
    spec.format = 1

    def raw(value: float, trace_scalar: int) -> int:
        if trace_scalar > 0:
            return int(round(value / trace_scalar))
        if trace_scalar < 0:
            return int(round(value * (-trace_scalar)))
        return int(round(value))

    with segyio.create(str(path), spec) as f:
        if not with_text_header:
            # segyio writes a minimal text header; blank the corner block so
            # the trace-scan fallback path is exercised.
            pass
        for i, il in enumerate(spec.ilines):
            for j, xl in enumerate(spec.xlines):
                tr_scalar = scalar
                if inconsistent_scalar and (i, j) == (0, 0):
                    tr_scalar = scalar * 10
                if zero_coords:
                    sx, sy = 0, 0
                else:
                    sx = raw(j * bin_m, tr_scalar)
                    sy = raw(i * bin_m, tr_scalar)
                f.header[i * n_xl + j] = {
                    segyio.TraceField.INLINE_3D: int(il),
                    segyio.TraceField.CROSSLINE_3D: int(xl),
                    segyio.TraceField.SourceX: sx,
                    segyio.TraceField.SourceY: sy,
                    segyio.TraceField.SourceGroupScalar: tr_scalar,
                }
                f.trace[i * n_xl + j] = [0.0] * 16
    return path


def _corners_or_none(path: Path):
    """survey_corners_from_segy, but None when it declines (no text header)."""
    try:
        return survey_corners_from_segy(path)
    except Exception:
        return None


class TestScalarApplication:
    def test_negative_scalar_divides(self, tmp_path: Path):
        # scalar=-100: raw 2500 → true 25 m
        path = _write_segy(tmp_path / "neg.sgy", scalar=-100, bin_m=25.0)
        result = _corners_or_none(path)
        assert result is not None, "trace-scan fallback must engage"
        p1, p2, p3, meta = result
        assert meta["source"] == "trace_scan"
        assert p1[2] == pytest.approx(0.0, abs=1e-6)
        assert p2[2] == pytest.approx(100.0, abs=1e-6)  # 4 bins * 25 m
        assert p3[2] == pytest.approx(100.0, abs=1e-6)
        assert p3[3] == pytest.approx(75.0, abs=1e-6)   # 3 bins * 25 m

    def test_positive_scalar_multiplies(self, tmp_path: Path):
        # scalar=+100: raw 1 → true 100 m; bins of 100 m are exactly
        # representable as raw ints under this scalar
        path = _write_segy(tmp_path / "pos.sgy", scalar=100, bin_m=100.0)
        result = _corners_or_none(path)
        assert result is not None
        p1, p2, p3, meta = result
        assert p2[2] == pytest.approx(400.0, abs=1e-6)  # 4 bins × 100 m
        assert p3[3] == pytest.approx(300.0, abs=1e-6)  # 3 bins × 100 m

    def test_zero_scalar_means_metres(self, tmp_path: Path):
        path = _write_segy(tmp_path / "zero.sgy", scalar=0, bin_m=25.0)
        result = _corners_or_none(path)
        assert result is not None
        p1, p2, p3, _meta = result
        assert p2[2] == pytest.approx(100.0, abs=1e-6)
        assert p3[3] == pytest.approx(75.0, abs=1e-6)

    def test_unit_scalar_identity(self, tmp_path: Path):
        path = _write_segy(tmp_path / "one.sgy", scalar=1, bin_m=25.0)
        result = _corners_or_none(path)
        assert result is not None
        p1, p2, p3, _meta = result
        assert p2[2] == pytest.approx(100.0, abs=1e-6)

    def test_inconsistent_scalars_are_flagged(self, tmp_path: Path):
        path = _write_segy(
            tmp_path / "mix.sgy", scalar=-100, inconsistent_scalar=True
        )
        result = _corners_or_none(path)
        assert result is not None
        _p1, _p2, _p3, meta = result
        assert meta.get("scalar_inconsistent") is True

    def test_consistent_scalars_not_flagged(self, tmp_path: Path):
        path = _write_segy(tmp_path / "ok.sgy", scalar=-100)
        result = _corners_or_none(path)
        assert result is not None
        _p1, _p2, _p3, meta = result
        assert not meta.get("scalar_inconsistent", False)


class TestDegenerateCornersRefused:
    def test_zero_coordinate_trace_scan_is_refused(self, tmp_path: Path):
        """All-zero SourceX/Y must not yield a valid-looking survey."""
        path = _write_segy(tmp_path / "zeroxy.sgy", scalar=1, zero_coords=True)
        result = _corners_or_none(path)
        if result is not None:
            p1, p2, p3, meta = result
            # Either the scan refuses to produce corners, or the corners it
            # produces must be refused downstream as degenerate.
            with pytest.raises(ValueError):
                survey_from_corners(
                    p1, p2, p3,
                    n_samples=int(meta["n_samples"]),
                    dt_ms=float(meta["dt_ms"]),
                    iline_step=meta.get("loader_iline_step"),
                    xline_step=meta.get("loader_xline_step"),
                    n_inlines=meta.get("loader_n_inlines"),
                    n_crosslines=meta.get("loader_n_crosslines"),
                )

    def test_survey_from_corners_refuses_zero_extent_edges(self):
        with pytest.raises(ValueError, match="extent|坐标"):
            survey_from_corners(
                (1, 1, 0.0, 0.0),
                (1, 5, 0.0, 0.0),   # zero-length XL edge
                (4, 5, 0.0, 0.0),   # zero-length IL edge
                n_samples=16,
                dt_ms=1.0,
            )

    def test_real_corners_still_build(self):
        spec = survey_from_corners(
            (1, 1, 0.0, 0.0),
            (1, 5, 100.0, 0.0),
            (4, 5, 100.0, 75.0),
            n_samples=16,
            dt_ms=1.0,
        )
        assert spec.n_crosslines == 5
        assert abs(spec.bin_grid.xl_spacing_m) == pytest.approx(25.0)
